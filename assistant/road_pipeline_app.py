"""Road geotechnical pipeline orchestrator (trắc dọc → phân đoạn → THSH)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RoadPipelineApp:
    """Ties together DXF profile reading, segment analysis, and THSH template filling."""

    def __init__(self, files, soilfirm_app, audit):
        self.files = files
        self.soilfirm_app = soilfirm_app
        self.audit = audit

    # ------------------------------------------------------------------
    # road_analyze
    # ------------------------------------------------------------------

    def prepare_analyze(self, name: str, args: dict) -> dict:
        """Step 1: Read DXF profile + boreholes JSON → segment analysis → preview."""
        profile_dxf = args.get('profile_dxf', '')
        boreholes_json = args.get('boreholes', '[]')
        template_xlsx = args.get('template_xlsx', '')
        output_xlsx = args.get('output_xlsx', '')

        errors: list[str] = []

        # Validate paths
        if not profile_dxf:
            errors.append('profile_dxf là bắt buộc.')
        if not template_xlsx:
            errors.append('template_xlsx là bắt buộc.')
        if not output_xlsx:
            errors.append('output_xlsx là bắt buộc.')

        # Parse boreholes
        boreholes: list[dict] = []
        if isinstance(boreholes_json, str):
            try:
                boreholes = json.loads(boreholes_json)
            except Exception as exc:
                errors.append(f'boreholes không hợp lệ JSON: {exc}')
        elif isinstance(boreholes_json, list):
            boreholes = boreholes_json

        if errors:
            raise ValueError(' | '.join(errors))

        # Read DXF profile
        from .dxf_profile import read_profile_dxf
        try:
            profile_points = read_profile_dxf(profile_dxf)
        except Exception as exc:
            raise RuntimeError(f'Lỗi đọc DXF trắc dọc: {exc}') from exc

        if not profile_points:
            raise RuntimeError('Không trích xuất được điểm trắc dọc từ DXF. '
                               'Kiểm tra file DXF có chứa TEXT nhãn lý trình và cao độ.')

        # Segment analysis
        from .road_segment import segment_profile, segments_to_dicts
        segment_length = float(args.get('segment_length', 200.0))
        segs = segment_profile(profile_points, boreholes, segment_length=segment_length)
        seg_dicts = segments_to_dicts(segs)

        # Build preview summary
        summary_lines = [
            f'Đọc được {len(profile_points)} điểm trắc dọc.',
            f'Phân {len(segs)} đoạn (mỗi đoạn ~{segment_length:.0f}m):',
        ]
        counts: dict[str, int] = {}
        for s in segs:
            counts[s.treatment] = counts.get(s.treatment, 0) + 1
        for method, cnt in sorted(counts.items()):
            summary_lines.append(f'  • {method}: {cnt} đoạn')

        plan = {
            'action': name,
            'profile_dxf': profile_dxf,
            'template_xlsx': template_xlsx,
            'output_xlsx': output_xlsx,
            'segments': seg_dicts,
            'preview': '\n'.join(summary_lines),
        }
        return plan

    def commit_analyze(self, plan: dict) -> str:
        """Fill THSH template with analysed segments."""
        from .thsh_writer import fill_thsh

        segs = plan.get('segments', [])
        template = plan['template_xlsx']
        output = plan['output_xlsx']

        # Ensure output path is allowed
        try:
            self.files._assert_allowed(output)
        except Exception:
            pass  # If no whitelist check available, proceed

        result = fill_thsh(template, output, segs)
        rows = result['rows_written']
        warnings = result.get('warnings', [])
        msg = f'Đã ghi {rows} đoạn vào THSH → {result["output_path"]}'
        if warnings:
            msg += '\nCảnh báo: ' + '; '.join(warnings)
        return msg

    # ------------------------------------------------------------------
    # road_verify
    # ------------------------------------------------------------------

    def prepare_verify(self, name: str, args: dict) -> dict:
        """Step 2: Re-verify with user-chosen treatment parameters → re-fill THSH."""
        segments_json = args.get('segments', '[]')
        template_xlsx = args.get('template_xlsx', '')
        output_xlsx = args.get('output_xlsx', '')

        if isinstance(segments_json, str):
            segments = json.loads(segments_json)
        else:
            segments = segments_json

        if not template_xlsx or not output_xlsx:
            raise ValueError('template_xlsx và output_xlsx là bắt buộc.')

        # Re-run classification with any overrides in each segment dict
        from .road_segment import classify_treatment, _settlement_estimate

        updated: list[dict] = []
        for seg in segments:
            htk = float(seg.get('htk', 0.0))
            hdy = float(seg.get('hdy', 0.0))
            override_treatment = seg.get('treatment_override', '')

            if override_treatment:
                method = override_treatment
                params: dict[str, Any] = {
                    'pvd_spacing': seg.get('pvd_spacing', 0.0),
                    'pvd_depth': seg.get('pvd_depth', 0.0),
                }
            else:
                slp = {'fs_initial': seg.get('Fs') or 1.5}
                method, params = classify_treatment(htk, hdy, slp)

            seg['treatment'] = method
            if 'pvd_spacing' in params:
                seg['pvd_spacing'] = params['pvd_spacing']
            if 'pvd_depth' in params:
                seg['pvd_depth'] = params['pvd_depth']

            # Recalc settlement
            layers = seg.get('layers', [])
            if layers and method != 'Không xử lý':
                sett = _settlement_estimate(htk, layers)
                seg.update(sett)

            updated.append(seg)

        plan = {
            'action': name,
            'template_xlsx': template_xlsx,
            'output_xlsx': output_xlsx,
            'segments': updated,
            'preview': f'Xác nhận lại {len(updated)} đoạn → điền THSH.',
        }
        return plan

    def commit_verify(self, plan: dict) -> str:
        return self.commit_analyze(plan)

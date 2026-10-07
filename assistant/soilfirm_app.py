"""Read SoilFirm Pro project files and expose soil data for analysis/reporting."""
from __future__ import annotations

import json
import math
from pathlib import Path


_FORMAT = 'saspro-python-1'
_SOIL_FIELDS = {
    'name', 'thickness', 'gamma', 'category', 'state', 'drainage',
    'e0', 'cc', 'cs', 'pc', 'ch_cv', 'co', 'cohesion_c', 'friction_phi',
    'phi_cu_effective', 'cv_constant', 'strength_m', 'spt_n', 'sand_method',
    'ep', 'e', 'cvp', 'cv', 'mvp', 'mv',
}
_PROJECT_SCALAR = {
    'name', 'design_stage', 'work_item', 'station', 'station_from', 'station_to',
    'road_class', 'road_location', 'pavement_type',
    'gamma_fill', 'h_design', 'h_kcad', 'h_bl', 'slope_m', 'height',
    'crest_half_width', 'slope_width',
    'main_treatment', 'main_replacement_depth', 'main_bamboo_depth',
    'main_cajuput_depth', 'main_cdm_depth', 'main_age_days',
    'ground_elevation', 'borehole_name', 'water_depth', 'gamma_water',
    'sublayer', 'limit_ratio', 'settlement_factor', 'method',
    'drain_spacing', 'drain_diameter', 'drain_pattern',
    'smear_ratio', 'permeability_ratio', 'khqw', 'resistance', 'treatment',
    'treatment_group', 'replacement_depth', 'bamboo_depth', 'cajuput_depth',
    'fill_speed_cm_day', 'surcharge_height', 'surcharge_gamma', 'surcharge_days',
    'vacuum_pressure', 'vacuum_days', 'drain_type',
    'residual_limit_cm', 'residual_limit_source',
    'counterweight_height', 'counterweight_width', 'counterweight_m',
    'expansion_side', 'expansion_width', 'expansion_h_design',
    'h_sand_cushion', 'cdm_scope',
}
MAX_FILE = 10 * 1024 * 1024  # 10 MiB


def _finite(v):
    return v if isinstance(v, (int, float)) and math.isfinite(v) else None


def _read_soil(raw: dict) -> dict:
    soil = {}
    for k in _SOIL_FIELDS:
        if k not in raw:
            continue
        v = raw[k]
        if k in {'ep', 'e', 'cvp', 'cv', 'mvp', 'mv'}:
            if isinstance(v, list):
                soil[k] = [_finite(x) for x in v]
        elif k in {'name', 'category', 'state', 'sand_method'}:
            soil[k] = str(v) if v is not None else ''
        elif k == 'drainage':
            soil[k] = int(v) if isinstance(v, (int, float)) else 1
        else:
            soil[k] = _finite(v)
    return soil


def _read_project(raw: dict) -> dict:
    proj = {}
    for k in _PROJECT_SCALAR:
        if k in raw:
            v = raw[k]
            if isinstance(v, str):
                proj[k] = v
            elif isinstance(v, bool):
                proj[k] = v
            elif isinstance(v, (int, float)):
                proj[k] = _finite(v)
    soils = []
    for s in (raw.get('soils') or []):
        if isinstance(s, dict):
            soils.append(_read_soil(s))
    proj['soils'] = soils
    # Include calculation_results if present (read-only summary)
    calc = raw.get('calculation_results')
    if isinstance(calc, dict):
        proj['calculation_results'] = calc
    stages = raw.get('stages') or []
    if isinstance(stages, list) and stages:
        proj['stages'] = [
            {'target_height': s.get('target_height'), 'speed_cm_day': s.get('speed_cm_day'),
             'pause_days': s.get('pause_days')}
            for s in stages if isinstance(s, dict)
        ]
    return proj


class SoilFirmApp:
    def __init__(self, files, audit):
        self.files = files
        self.audit = audit

    def _checked_path(self, raw_path: str, must_exist: bool = True) -> Path:
        return self.files.path(raw_path, exists=must_exist)

    def read_project(self, path: str) -> dict:
        """Read a SoilFirm Pro project file and return structured data."""
        p = self._checked_path(path)
        if p.stat().st_size > MAX_FILE:
            raise ValueError('File dự án vượt 10 MiB.')
        with p.open(encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get('format') != _FORMAT:
            raise ValueError(f'Không phải file SoilFirm Pro ({_FORMAT}).')
        raw = data.get('project')
        if not isinstance(raw, dict):
            raise ValueError('Cấu trúc file không hợp lệ: thiếu project.')
        proj = _read_project(raw)
        n_soils = len(proj.get('soils', []))
        self.audit('soilfirm_project_read', {'path': str(p), 'soils': n_soils})
        return {
            'path': str(p),
            'project': proj,
            'soil_count': n_soils,
            'note': (
                'Đã đọc dự án SoilFirm Pro. Dữ liệu địa chất, thông số thiết kế và kết quả tính '
                '(nếu có) sẵn sàng để lập báo cáo hoặc phân tích tiếp. '
                'Dùng template_fill để điền vào mẫu thuyết minh.'
            ),
        }

    def summary(self, path: str) -> dict:
        """Return a concise summary of a SoilFirm project for display."""
        result = self.read_project(path)
        proj = result['project']
        soils = proj.get('soils', [])
        layers = [
            {
                'no': i + 1,
                'name': s.get('name', ''),
                'thickness': s.get('thickness'),
                'gamma': s.get('gamma'),
                'e0': s.get('e0'),
                'cc': s.get('cc'),
                'cohesion_c': s.get('cohesion_c'),
                'friction_phi': s.get('friction_phi'),
                'category': s.get('category', ''),
            }
            for i, s in enumerate(soils)
        ]
        return {
            'path': result['path'],
            'name': proj.get('name', ''),
            'design_stage': proj.get('design_stage', ''),
            'borehole_name': proj.get('borehole_name', ''),
            'h_design': proj.get('h_design'),
            'gamma_fill': proj.get('gamma_fill'),
            'treatment': proj.get('treatment', proj.get('main_treatment', '')),
            'method': proj.get('method', ''),
            'layers': layers,
            'calculation_results': proj.get('calculation_results', {}),
        }

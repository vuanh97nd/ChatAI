"""Read and write SoilFirm Pro project files; bridge Excel geotechnical data."""
from __future__ import annotations

import json
import math
import uuid
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

_SOIL_CATEGORIES = {'Đất dính', 'Đất rời', 'Đất hữu cơ', 'Đá'}
_SOIL_STATES = {'Quá cố kết', 'Cố kết thường', 'Chưa cố kết xong'}


def _num(v, lo=None, hi=None, nullable=False):
    if v is None:
        if nullable:
            return None
        raise ValueError('Giá trị không được để trống.')
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f'Giá trị phải là số hữu hạn, nhận được: {v!r}')
    v = float(v)
    if lo is not None and v < lo:
        raise ValueError(f'Giá trị {v} nhỏ hơn giới hạn tối thiểu {lo}.')
    if hi is not None and v > hi:
        raise ValueError(f'Giá trị {v} lớn hơn giới hạn tối đa {hi}.')
    return v


def _validate_soil_input(idx: int, raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(f'Lớp {idx+1}: phải là đối tượng JSON.')
    try:
        name = str(raw.get('name', f'Lớp {idx+1}')).strip()[:100]
        thickness = _num(raw.get('thickness', 1.0), lo=0.01, hi=200.0)
        gamma = _num(raw.get('gamma', 0.0), lo=0.0, hi=30.0)
        e0 = _num(raw.get('e0', 0.0), lo=0.0, hi=5.0)
        cc = _num(raw.get('cc', 0.0), lo=0.0, hi=5.0)
        cs = _num(raw.get('cs', 0.0), lo=0.0, hi=2.0)
        pc = _num(raw.get('pc', 0.0), lo=0.0, hi=10000.0)
        cv_constant = _num(raw.get('cv_constant'), nullable=True)
        if cv_constant is not None:
            cv_constant = _num(cv_constant, lo=0.0, hi=100.0)
        co = _num(raw.get('co', 0.0), lo=0.0, hi=500.0)
        cohesion_c = _num(raw.get('cohesion_c', 0.0), lo=0.0, hi=500.0)
        friction_phi = _num(raw.get('friction_phi', 0.0), lo=0.0, hi=60.0)
        phi_cu = _num(raw.get('phi_cu_effective'), nullable=True)
        spt_n = _num(raw.get('spt_n', 0.0), lo=0.0, hi=300.0)
        category = str(raw.get('category', 'Đất dính'))
        if category not in _SOIL_CATEGORIES:
            category = 'Đất dính'
        state = str(raw.get('state', 'Quá cố kết'))
        if state not in _SOIL_STATES:
            state = 'Quá cố kết'
        drainage = int(raw.get('drainage', 1))
        ch_cv = _num(raw.get('ch_cv', 2.0), lo=1.0, hi=20.0)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'Lớp {idx+1} ({raw.get("name","?")!r}): {exc}') from exc
    soil = {
        'no': idx,
        'statistics_id': '',
        'parameter_sources': {},
        'name': name,
        'thickness': thickness,
        'distance': 0.0,
        'gamma': gamma,
        'category': category,
        'state': state,
        'drainage': drainage,
        'ep': [0.0, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0],
        'e': [0.0] * 8,
        'e0': e0,
        'cvp': [0.0625, 0.1875, 0.375, 0.75, 1.5, 3.0, 6.0],
        'cv': [0.0] * 7,
        'mvp': [0.0625, 0.1875, 0.375, 0.75, 1.5, 3.0, 6.0],
        'mv': [0.0] * 7,
        'cc': cc,
        'cs': cs,
        'pc': pc,
        'ch_cv': ch_cv,
        'co': co,
        'cohesion_c': cohesion_c,
        'friction_phi': friction_phi,
        'cv_constant': cv_constant,
        'phi_cu_effective': phi_cu,
        'strength_m': float(raw.get('strength_m', 0.1)),
        'spt_n': spt_n,
        'sand_method': str(raw.get('sand_method', 'De Beer')),
        'weak_indicators': {},
    }
    return soil


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

    def prepare_create(self, name, args):
        """Validate soil data JSON and prepare a SoilFirm project creation plan."""
        project_name = str(args.get('project_name', '')).strip()
        if not project_name or len(project_name) > 200:
            raise ValueError('project_name phải là chuỗi 1–200 ký tự.')
        output_name = str(args.get('output_name', '')).strip()
        if not output_name:
            raise ValueError('output_name là tên file đầu ra (ví dụ: KM32.json).')
        clean = Path(output_name).name
        if clean != output_name or clean.startswith('.'):
            raise ValueError('output_name phải là tên file đơn, không chứa đường dẫn.')
        if not clean.lower().endswith('.json'):
            clean = clean + '.json'
        soils_raw = args.get('soils', '')
        if not isinstance(soils_raw, str) or len(soils_raw) > 200_000:
            raise ValueError('soils phải là chuỗi JSON tối đa 200000 ký tự.')
        try:
            soils_list = json.loads(soils_raw)
        except Exception:
            raise ValueError('soils không phải JSON hợp lệ.')
        if not isinstance(soils_list, list) or not 1 <= len(soils_list) <= 100:
            raise ValueError('soils phải là mảng 1–100 lớp đất.')
        validated = [_validate_soil_input(i, s) for i, s in enumerate(soils_list)]
        # Extra project metadata
        meta = {}
        for k in ('design_stage', 'work_item', 'station', 'borehole_name',
                  'h_design', 'gamma_fill', 'water_depth', 'ground_elevation'):
            if k in args and args[k] is not None:
                meta[k] = args[k]
        if not self.files.roots:
            raise PermissionError('Thêm thư mục lưu file được phép trong Cài đặt.')
        out_path = self.files.path(
            str(self.files.roots[0] / clean), exists=False)
        return {
            'action': 'soilfirm_create',
            'project_name': project_name,
            'output_path': str(out_path),
            'soils': validated,
            'meta': meta,
        }

    def commit_create(self, plan):
        out_path = self.files.path(plan['output_path'], exists=False)
        if out_path.exists():
            raise FileExistsError(f'File đã tồn tại: {out_path}. Chọn tên khác.')
        soils = plan['soils']
        meta = plan.get('meta', {})
        project = {
            'name': plan['project_name'],
            'design_stage': str(meta.get('design_stage', '')),
            'work_item': str(meta.get('work_item', '')),
            'station': str(meta.get('station', '')),
            'borehole_name': str(meta.get('borehole_name', '')),
            'h_design': float(meta.get('h_design', 3.0)),
            'gamma_fill': float(meta.get('gamma_fill', 1.8)),
            'water_depth': float(meta.get('water_depth', 0.0)),
            'ground_elevation': float(meta.get('ground_elevation', 0.0)),
            # Required fields with safe defaults
            'road_class': 'A1 · cao tốc hoặc Vtk ≥ 80 km/h',
            'road_location': 'Nền đắp thông thường',
            'pavement_type': 'Mặt đường mềm',
            'h_kcad': 0.15, 'h_bl': 0.0, 'slope_m': 1.5,
            'crest_half_width': 6.0, 'slope_width': 4.725,
            'expansion_side': 'Không', 'expansion_width': 0.0,
            'expansion_h_design': 0.0,
            'main_treatment': 'Chưa xử lý', 'main_soils': [],
            'main_replacement_depth': 0.0, 'main_bamboo_depth': 0.0,
            'main_cajuput_depth': 0.0, 'main_cdm_depth': 0.0, 'main_age_days': 0.0,
            'counterweight_height': 0.0, 'counterweight_width': 0.0,
            'counterweight_m': 1.0, 'counterweight_slope': 0.0,
            'gamma_water': 0.98, 'sublayer': 1.0, 'limit_ratio': 0.15,
            'settlement_factor': 1.2, 'method': 'Cc/Cs/Pc',
            'drain_spacing': 1.2, 'drain_diameter': 6.62, 'drain_pattern': 'Tam giác',
            'smear_ratio': 2.0, 'permeability_ratio': 3.0, 'khqw': 0.0001,
            'resistance': 0.0, 'treatment': 'PVD', 'treatment_group': 'drainage',
            'replacement_depth': 0.0, 'bamboo_depth': 0.0, 'cajuput_depth': 0.0,
            'mechanical_wait': False, 'mechanical_surcharge': False,
            'fill_speed_cm_day': 10.0, 'stages': [],
            'surcharge_height': 0.0, 'surcharge_gamma': 1.8, 'surcharge_days': 180.0,
            'vacuum_pressure': 8.0, 'vacuum_days': 180.0, 'drain_type': 'Bấc thấm',
            'drain_cw_enabled': False, 'drain_cw_type': 'Bấc thấm',
            'drain_cw_spacing': 0.0, 'drain_cw_diameter': 5.5, 'drain_cw_pattern': 'Tam giác',
            'drain_upper_boundary': True, 'drain_length': 0.0,
            'ignore_uv': False, 'ignore_fs': False, 'ignore_fr': False,
            'legacy_z': 0.0, 'legacy_us': 0.0, 'assessment_days': 0.0,
            'residual_limit_cm': 20.0, 'residual_limit_source': '',
            'horizontal_drain_type': 'Bấc thấm ngang', 'h_sand_cushion': 0.5,
            'cdm_scope': 'Nền đường', 'cdm_inputs': {}, 'alicc_inputs': {},
            'geology_statistics': {}, 'calculation_results': {},
            'ai_ch_cv_default_layers': [],
            'height': float(meta.get('h_design', 3.0)) + 0.15,
            'soils': soils,
        }
        # Compute height from h_design + h_kcad
        project['height'] = project['h_design'] + project['h_kcad']
        payload = json.dumps({'format': _FORMAT, 'project': project},
                             ensure_ascii=False, indent=2)
        import tempfile, os, shutil
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.tmp',
                dir=out_path.parent, delete=False) as tmp:
            tmp_name = tmp.name
            tmp.write(payload)
        try:
            os.replace(tmp_name, out_path)
        except Exception:
            try: os.unlink(tmp_name)
            except OSError: pass
            raise
        self.audit('soilfirm_project_created', {'path': str(out_path), 'soils': len(soils)})
        return {
            'ok': True,
            'path': str(out_path),
            'soils': len(soils),
            'note': f'Đã tạo file dự án SoilFirm Pro. Mở bằng SoilFirm Pro để kiểm tra và tính toán.',
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

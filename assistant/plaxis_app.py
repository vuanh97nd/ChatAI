"""Generate Plaxis 2D/3D Python scripts for geotechnical analysis.

Supports two modes:
1. Generate-only: creates a .py script file for user to run manually.
2. Auto-run: connects to a running Plaxis instance via plxscripting and
   executes the generated commands directly, returning live results.
"""
import json
import uuid
from pathlib import Path

_SUPPORTED_TYPES = {'slope_stability', 'foundation_settlement', 'retaining_wall', 'excavation_pit', 'embankment_stability'}

_PORT = {'2d': 10000, '3d': 10000}


def _num(val, name, lo, hi):
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        raise ValueError(f'{name} phải là số.')
    if not lo <= val <= hi:
        raise ValueError(f'{name} phải trong khoảng [{lo}, {hi}].')
    return float(val)


def _validate_soil_layer(layer, idx):
    prefix = f'Lớp đất {idx}'
    E = _num(layer.get('E', -1), f'{prefix} E', 1.0, 1e9)
    nu = _num(layer.get('nu', -1), f'{prefix} nu', 0.0, 0.499)
    gamma = _num(layer.get('gamma', -1), f'{prefix} gamma', 1.0, 30.0)
    # gamma_sat tuỳ chọn; nếu không có thì dùng gamma + 2
    gamma_sat_raw = layer.get('gamma_sat')
    if gamma_sat_raw is not None:
        gamma_sat = _num(gamma_sat_raw, f'{prefix} gamma_sat', 1.0, 35.0)
    else:
        gamma_sat = gamma + 2.0
    c = _num(layer.get('c', -1), f'{prefix} c', 0.0, 1e6)
    phi = _num(layer.get('phi', -1), f'{prefix} phi', 0.0, 89.0)
    name = layer.get('name', f'Layer{idx}')
    if not isinstance(name, str) or not name or len(name) > 100:
        raise ValueError(f'{prefix} name phải là chuỗi 1-100 ký tự.')
    if any(c in name for c in ('\n', '\r', '\0')):
        raise ValueError(f'{prefix} name chứa ký tự xuống dòng không hợp lệ.')
    thickness = _num(layer.get('thickness', -1), f'{prefix} thickness', 0.01, 1000.0)
    return {'name': name, 'E': E, 'nu': nu, 'gamma': gamma, 'gamma_sat': gamma_sat,
            'c': c, 'phi': phi, 'thickness': thickness}


def _validate_slope_stability(problem):
    slope_angle = _num(problem.get('slope_angle', -1), 'slope_angle', 1.0, 89.0)
    slope_height = _num(problem.get('slope_height', -1), 'slope_height', 0.1, 1000.0)
    analysis = problem.get('analysis', 'Bishop')
    if analysis not in ('Bishop', 'Fellenius'):
        raise ValueError("analysis phải là 'Bishop' hoặc 'Fellenius'.")
    raw_layers = problem.get('soil_layers', [])
    if not isinstance(raw_layers, list) or not raw_layers:
        raise ValueError('slope_stability cần ít nhất một lớp đất trong soil_layers.')
    layers = [_validate_soil_layer(l, i + 1) for i, l in enumerate(raw_layers)]
    return {'type': 'slope_stability', 'slope_angle': slope_angle,
            'slope_height': slope_height, 'analysis': analysis, 'soil_layers': layers}


def _validate_foundation_settlement(problem):
    footing_width = _num(problem.get('footing_width', -1), 'footing_width', 0.1, 100.0)
    footing_depth = _num(problem.get('footing_depth', -1), 'footing_depth', 0.0, 50.0)
    load = _num(problem.get('load', -1), 'load', 0.0, 1e7)
    raw_layers = problem.get('soil_layers', [])
    if not isinstance(raw_layers, list) or not raw_layers:
        raise ValueError('foundation_settlement cần ít nhất một lớp đất trong soil_layers.')
    layers = [_validate_soil_layer(l, i + 1) for i, l in enumerate(raw_layers)]
    return {'type': 'foundation_settlement', 'footing_width': footing_width,
            'footing_depth': footing_depth, 'load': load, 'soil_layers': layers}


def _validate_retaining_wall(problem):
    wall_height = _num(problem.get('wall_height', -1), 'wall_height', 0.1, 200.0)
    wall_thickness = _num(problem.get('wall_thickness', -1), 'wall_thickness', 0.1, 10.0)
    surcharge = _num(problem.get('surcharge', 0), 'surcharge', 0.0, 1e6)
    raw_layers = problem.get('soil_layers', [])
    if not isinstance(raw_layers, list) or not raw_layers:
        raise ValueError('retaining_wall cần ít nhất một lớp đất trong soil_layers.')
    layers = [_validate_soil_layer(l, i + 1) for i, l in enumerate(raw_layers)]
    return {'type': 'retaining_wall', 'wall_height': wall_height,
            'wall_thickness': wall_thickness, 'surcharge': surcharge, 'soil_layers': layers}


def _validate_excavation_pit(problem):
    excavation_depth = _num(problem.get('excavation_depth', -1), 'excavation_depth', 0.5, 100.0)
    excavation_width = _num(problem.get('excavation_width', -1), 'excavation_width', 0.5, 500.0)
    wall_thickness = _num(problem.get('wall_thickness', -1), 'wall_thickness', 0.1, 5.0)
    embedment_depth = _num(problem.get('embedment_depth', 0), 'embedment_depth', 0.0, 50.0)
    surcharge = _num(problem.get('surcharge', 0), 'surcharge', 0.0, 1e6)
    # water_table_depth: độ sâu mực nước dưới mặt đất (dương = bên dưới), 0 = mặt đất
    water_table_raw = problem.get('water_table_depth')
    if water_table_raw is not None:
        water_table_depth = _num(water_table_raw, 'water_table_depth', 0.0, 200.0)
    else:
        water_table_depth = None
    raw_layers = problem.get('soil_layers', [])
    if not isinstance(raw_layers, list) or not raw_layers:
        raise ValueError('excavation_pit cần ít nhất một lớp đất trong soil_layers.')
    layers = [_validate_soil_layer(l, i + 1) for i, l in enumerate(raw_layers)]
    return {
        'type': 'excavation_pit',
        'excavation_depth': excavation_depth,
        'excavation_width': excavation_width,
        'wall_thickness': wall_thickness,
        'embedment_depth': embedment_depth,
        'surcharge': surcharge,
        'water_table_depth': water_table_depth,
        'soil_layers': layers,
    }


def _validate_hs_soil(layer, idx):
    """Validate a Hardening Soil material dict (used by embankment_stability)."""
    prefix = f'Vật liệu {idx}'
    gamma = _num(layer.get('gamma', -1), f'{prefix} gamma', 1.0, 30.0)
    gamma_sat_raw = layer.get('gamma_sat')
    gamma_sat = _num(gamma_sat_raw, f'{prefix} gamma_sat', 1.0, 35.0) if gamma_sat_raw is not None else gamma + 2.0
    E50ref = _num(layer.get('E50ref', -1), f'{prefix} E50ref', 1.0, 1e9)
    Eoedref = _num(layer.get('Eoedref', -1), f'{prefix} Eoedref', 1.0, 1e9)
    Eurref = _num(layer.get('Eurref', -1), f'{prefix} Eurref', 1.0, 1e9)
    m = _num(layer.get('m', 0.5), f'{prefix} m', 0.0, 1.0)
    c_ref = _num(layer.get('c_ref', -1), f'{prefix} c_ref', 0.0, 1e6)
    phi = _num(layer.get('phi', -1), f'{prefix} phi', 0.0, 89.0)
    OCR = _num(layer.get('OCR', 1.0), f'{prefix} OCR', 0.1, 100.0)
    name = layer.get('name', f'Material{idx}')
    if not isinstance(name, str) or not name or len(name) > 100:
        raise ValueError(f'{prefix} name phải là chuỗi 1-100 ký tự.')
    if any(ch in name for ch in ('\n', '\r', '\0')):
        raise ValueError(f'{prefix} name chứa ký tự không hợp lệ.')
    return {'name': name, 'gamma': gamma, 'gamma_sat': gamma_sat,
            'E50ref': E50ref, 'Eoedref': Eoedref, 'Eurref': Eurref,
            'm': m, 'c_ref': c_ref, 'phi': phi, 'OCR': OCR}


_FILL_DEFAULTS = {
    'name': 'Bo dap (Cat)', 'gamma': 16.0, 'gamma_sat': 16.0,
    'E50ref': 15000.0, 'Eoedref': 15000.0, 'Eurref': 45000.0,
    'm': 0.5, 'c_ref': 3.0, 'phi': 30.0, 'OCR': 1.0,
}
_CLAY_DEFAULTS = {
    'name': 'Set (Drained)', 'gamma': 13.0, 'gamma_sat': 13.0,
    'E50ref': 5600.0, 'Eoedref': 5000.0, 'Eurref': 20000.0,
    'm': 1.0, 'c_ref': 10.0, 'phi': 25.0, 'OCR': 1.2,
}


def _validate_embankment_stability(problem):
    embankment_height = _num(problem.get('embankment_height', 4.0), 'embankment_height', 0.5, 100.0)
    embankment_top_width = _num(problem.get('embankment_top_width', 2.0), 'embankment_top_width', 0.1, 100.0)
    clay_thickness = _num(problem.get('clay_thickness', 6.0), 'clay_thickness', 1.0, 100.0)
    slope_left = _num(problem.get('slope_left', 2.0), 'slope_left', 0.5, 10.0)   # H:V ratio
    slope_right = _num(problem.get('slope_right', 3.0), 'slope_right', 0.5, 10.0)

    fill_raw = {**_FILL_DEFAULTS, **(problem.get('fill_material') or {})}
    clay_raw = {**_CLAY_DEFAULTS, **(problem.get('clay_material') or {})}
    fill = _validate_hs_soil(fill_raw, 1)
    clay = _validate_hs_soil(clay_raw, 2)

    return {
        'type': 'embankment_stability',
        'embankment_height': embankment_height,
        'embankment_top_width': embankment_top_width,
        'clay_thickness': clay_thickness,
        'slope_left': slope_left,
        'slope_right': slope_right,
        **({'embankment_length': _num(problem['embankment_length'], 'embankment_length', 0.1, 10000.0)} if 'embankment_length' in problem else {}),
        'fill_material': fill,
        'clay_material': clay,
    }


def _validate_problem(raw):
    if not isinstance(raw, str) or len(raw.encode()) > 50 * 1024:
        raise ValueError('problem phải là chuỗi JSON, tối đa 50KB.')
    try:
        problem = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f'problem không phải JSON hợp lệ: {e}')
    if not isinstance(problem, dict):
        raise ValueError('problem phải là JSON object.')
    ptype = problem.get('type')
    if ptype not in _SUPPORTED_TYPES:
        raise ValueError(f"problem.type phải là một trong: {', '.join(sorted(_SUPPORTED_TYPES))}.")
    if ptype == 'slope_stability':
        return _validate_slope_stability(problem)
    if ptype == 'foundation_settlement':
        return _validate_foundation_settlement(problem)
    if ptype == 'retaining_wall':
        return _validate_retaining_wall(problem)
    if ptype == 'excavation_pit':
        return _validate_excavation_pit(problem)
    return _validate_embankment_stability(problem)


def _script_header(version, port):
    return f"""\
# Script được tạo tự động bởi ChatAI cho Plaxis {version.upper()}
# Chạy bằng: Plaxis > File > Run Script (hoặc Remote Scripting Server)
from plxscripting.easy import new_server

s, g = new_server('localhost', {port}, password='')
"""


def _soil_lines(layers, version):
    lines = []
    for i, layer in enumerate(layers):
        vname = f'soil{i + 1}'
        # Use repr() so any quotes or special chars in name are safely escaped
        safe_name = repr(layer["name"])
        lines.append(f'{vname} = g.soilmat()')
        lines.append(f'{vname}.setproperties("Identification", {safe_name})')
        lines.append(f'{vname}.setproperties("SoilModel", 2)')  # Mohr-Coulomb
        lines.append(f'{vname}.setproperties("Eref", {layer["E"]})')
        lines.append(f'{vname}.setproperties("nu", {layer["nu"]})')
        lines.append(f'{vname}.setproperties("gammaUnsat", {layer["gamma"]})')
        lines.append(f'{vname}.setproperties("gammaSat", {layer["gamma_sat"]})')
        lines.append(f'{vname}.setproperties("cref", {layer["c"]})')
        lines.append(f'{vname}.setproperties("phi", {layer["phi"]})')
        lines.append('')
    return '\n'.join(lines)


def _stratigraphy_lines(layers, version):
    """Create positive-thickness strata and assign each material before meshing."""
    lines=['g.gotosoil()', 'bh = g.borehole(0)' if version=='2d' else 'bh = g.borehole(0, 0)',
           'bh.Head = 0']
    for i,layer in enumerate(layers):
        lines.append(f'g.soillayer({layer["thickness"]!r})')
        lines.append(f'g.setmaterial(g.Soillayers[{i}].Soil, soil{i+1})')
    lines.append('g.gotostructures()')
    return '\n'.join(lines)


def _generate_slope_stability(problem, version, port, project_name):
    angle = problem['slope_angle']
    height = problem['slope_height']
    analysis = problem['analysis']
    layers = problem['soil_layers']

    import math
    base = height / math.tan(math.radians(angle))
    total_width = base + height * 2

    lines = [_script_header(version, port)]
    lines.append(f'# Bài toán: Ổn định mái dốc - {project_name}')
    lines.append(f'# Phương pháp phân tích: {analysis}')
    lines.append(f'# Chiều cao mái dốc: {height} m, Góc nghiêng: {angle} độ')
    lines.append('')
    lines.append('g.gotostructures()')
    lines.append('')
    lines.append('# Vật liệu đất')
    lines.append(_soil_lines(layers, version))

    lines.append('# Địa tầng và gán vật liệu đất')
    lines.append(_stratigraphy_lines(layers, version))
    lines.append('')
    lines.append('# Mái dốc dạng polyline')
    lines.append(f'slope = g.line(({-base:.2f}, 0), (0, 0), (0, {height:.2f}), ({total_width:.2f}, {height:.2f}))')
    lines.append('')
    lines.append('# Lưới phần tử')
    lines.append('g.gotomesh()')
    lines.append('g.mesh(0.06)')
    lines.append('')
    lines.append('# Tính toán')
    lines.append('g.gotostages()')
    lines.append('phase1 = g.phase(g.InitialPhase)')
    lines.append('phase1.Identification = "On dinh mai doc - Safety (c-phi reduction)"')
    lines.append('# PLAXIS tính bằng FEM/Safety; Bishop/Fellenius là phương pháp cân bằng giới hạn khác.')
    lines.append('phase1.DeformCalcType = "Safety"')
    lines.append('phase1.ShouldCalculate = True')
    lines.append('')
    lines.append('g.calculate()')
    lines.append('g.view(phase1)')
    lines.append('print("Da gui lenh phan tich on dinh mai doc bang PLAXIS Safety (c-phi reduction).")')
    return '\n'.join(lines)


def _generate_foundation_settlement(problem, version, port, project_name):
    B = problem['footing_width']
    D = problem['footing_depth']
    load = problem['load']
    layers = problem['soil_layers']

    half_model = max(B * 5, 10.0)
    depth_model = sum(l['thickness'] for l in layers)

    lines = [_script_header(version, port)]
    lines.append(f'# Bài toán: Lún móng nông - {project_name}')
    lines.append(f'# Chiều rộng móng B={B} m, Chiều sâu chôn móng D={D} m, Tải trọng P={load} kN/m')
    lines.append('')
    lines.append('g.gotostructures()')
    lines.append('')
    lines.append('# Vật liệu đất')
    lines.append(_soil_lines(layers, version))
    lines.append('# Hình học mô hình (đối xứng trục, nửa mô hình)')
    lines.append(_stratigraphy_lines(layers, version))
    lines.append('')
    lines.append(f'# Móng (tải tập trung phân bố đều trên bề mặt rộng {B} m)')
    lines.append(f'g.lineload(0, -{D}, {B / 2:.3f}, -{D})')
    lines.append(f'g.lineload_1.qy_start = -{load / B:.2f}')
    lines.append('')
    lines.append('g.gotomesh()')
    lines.append('g.mesh(0.05)')
    lines.append('')
    lines.append('g.gotostages()')
    lines.append('phase1 = g.phase(g.InitialPhase)')
    lines.append('phase1.Identification = "Phan tich lun mong nong"')
    lines.append('phase1.ShouldCalculate = True')
    lines.append('')
    lines.append('g.calculate()')
    lines.append('g.view(phase1)')
    lines.append('print("Hoan thanh phan tich lun mong nong.")')
    return '\n'.join(lines)


def _generate_retaining_wall(problem, version, port, project_name):
    H = problem['wall_height']
    t = problem['wall_thickness']
    q = problem['surcharge']
    layers = problem['soil_layers']

    lines = [_script_header(version, port)]
    lines.append(f'# Bài toán: Tường chắn đất - {project_name}')
    lines.append(f'# Chiều cao tường H={H} m, Bề dày t={t} m, Tải phân bố q={q} kPa')
    lines.append('')
    lines.append('g.gotostructures()')
    lines.append('')
    lines.append('# Vật liệu đất')
    lines.append(_soil_lines(layers, version))
    lines.append(_stratigraphy_lines(layers, version))
    lines.append('# Vật liệu tường (bê tông cốt thép)')
    lines.append('wall_mat = g.platemat()')
    lines.append('wall_mat.setproperties("Identification", "Tuong BTCT")')
    lines.append('wall_mat.setproperties("EA", 2.1e7)')
    lines.append('wall_mat.setproperties("EI", 155000)')
    lines.append('wall_mat.setproperties("w", 5.0)')
    lines.append('wall_mat.setproperties("nu", 0.15)')
    lines.append('')
    lines.append(f'# Tường chắn đứng từ (0,0) đến (0, -{H:.2f})')
    lines.append(f'wall = g.plate((0, 0), (0, -{H:.2f}))')
    lines.append(f'wall.setmaterial(wall_mat)')
    lines.append('')
    if q > 0:
        lines.append(f'# Tải trọng phân bố trên mặt đất sau tường')
        lines.append(f'g.uniformload({t:.3f}, 0, {t + H * 2:.3f}, 0)')
        lines.append(f'g.uniformload_1.qy_start = -{q:.2f}')
        lines.append('')
    lines.append('# Lưới phần tử')
    lines.append('g.gotomesh()')
    lines.append('g.mesh(0.06)')
    lines.append('')
    lines.append('g.gotostages()')
    lines.append('phase1 = g.phase(g.InitialPhase)')
    lines.append('phase1.Identification = "Phan tich tuong chan dat"')
    lines.append('phase1.ShouldCalculate = True')
    lines.append('')
    lines.append('g.calculate()')
    lines.append('g.view(phase1)')
    lines.append('print("Hoan thanh phan tich tuong chan dat.")')
    return '\n'.join(lines)


def _generate_excavation_pit(problem, version, port, project_name):
    H = problem['excavation_depth']
    W = problem['excavation_width']
    t = problem['wall_thickness']
    d = problem['embedment_depth']
    q = problem['surcharge']
    layers = problem['soil_layers']
    wt = problem.get('water_table_depth')  # None hoặc độ sâu (m, dương = xuống)

    total_wall_height = H + d
    model_width = W / 2 + max(H * 3, 20.0)
    model_depth = total_wall_height + max(H * 2, 10.0)

    lines = [_script_header(version, port)]
    lines.append(f'# Bài toán: Hố đào - {project_name}')
    lines.append(f'# Độ sâu hố đào H={H} m, Chiều rộng W={W} m')
    lines.append(f'# Tường vây: bê tông dày t={t} m, chiều sâu chôn d={d} m')
    if wt is not None:
        lines.append(f'# Mực nước ngầm: -{wt} m so với mặt đất')
    if q > 0:
        lines.append(f'# Tải trọng mặt đất: q={q} kPa')
    lines.append('')
    lines.append('g.gotostructures()')
    lines.append('')
    lines.append('# Vật liệu đất')
    lines.append(_soil_lines(layers, version))

    lines.append('# Vật liệu tường vây (bê tông cốt thép)')
    lines.append('wall_mat = g.platemat()')
    lines.append('wall_mat.setproperties("Identification", "Tuong vay BTCT")')
    EA = 3.0e7 * t
    EI = 3.0e7 * (t ** 3) / 12.0
    lines.append(f'wall_mat.setproperties("EA", {EA:.3e})')
    lines.append(f'wall_mat.setproperties("EI", {EI:.3e})')
    lines.append(f'wall_mat.setproperties("w", {25.0 * t:.2f})')
    lines.append('wall_mat.setproperties("nu", 0.15)')
    lines.append('')

    lines.append('# Hình học: mô hình nửa đối xứng (trục đối xứng tại x=0)')
    lines.append(_stratigraphy_lines(layers, version))
    lines.append('')

    if wt is not None:
        lines.append(f'# Mực nước ngầm (groundwater level) tại y = -{wt:.2f} m')
        lines.append(f'g.setwaterlevel(0, -{wt:.2f}, {model_width:.2f}, -{wt:.2f})')
        lines.append('')

    lines.append('# Tường vây bên phải (x = W/2)')
    half_W = W / 2
    lines.append(f'wall = g.plate(({half_W:.3f}, 0), ({half_W:.3f}, -{total_wall_height:.3f}))')
    lines.append('wall.setmaterial(wall_mat)')
    lines.append('')

    if q > 0:
        lines.append('# Tải trọng mặt đất sau tường')
        lines.append(f'g.uniformload({half_W + t:.3f}, 0, {model_width:.3f}, 0)')
        lines.append(f'g.uniformload_1.qy_start = -{q:.2f}')
        lines.append('')

    lines.append('# Lưới phần tử')
    lines.append('g.gotomesh()')
    lines.append('g.mesh(0.06)')
    lines.append('')
    lines.append('g.gotostages()')
    lines.append('')
    lines.append('# Giai đoạn 1: Ứng suất ban đầu')
    lines.append('phase0 = g.InitialPhase')
    lines.append('')
    lines.append('# Giai đoạn 2: Thi công tường vây')
    lines.append('phase1 = g.phase(phase0)')
    lines.append('phase1.Identification = "Thi cong tuong vay"')
    lines.append('phase1.ShouldCalculate = True')
    lines.append('g.activate(wall, phase1)')
    lines.append('')
    lines.append(f'# Giai đoạn 3: Đào đất đến độ sâu {H} m')
    lines.append('phase2 = g.phase(phase1)')
    lines.append('phase2.Identification = "Dao dat"')
    lines.append('phase2.ShouldCalculate = True')
    lines.append(f'excavation_poly = g.polygon((-{half_W:.3f}, 0), ({half_W:.3f}, 0), ({half_W:.3f}, -{H:.3f}), (-{half_W:.3f}, -{H:.3f}))')
    lines.append('g.deactivate(excavation_poly.SoilElements, phase2)')
    lines.append('')
    lines.append('# Giai đoạn 4: Kiểm tra ổn định (Phi-c reduction)')
    lines.append('phase3 = g.phase(phase2)')
    lines.append('phase3.Identification = "Kiem tra on dinh SF"')
    lines.append('phase3.ShouldCalculate = True')
    lines.append('phase3.DeformCalcType = "Safety"')
    lines.append('')
    lines.append('g.calculate()')
    lines.append('g.view(phase2)')
    lines.append('print("Hoan thanh phan tich ho dao.")')
    lines.append(f'print(f"SF = {{phase3.ReachedValue.SumMsf:.3f}}")')
    return '\n'.join(lines)


def _hs_soil_lines(mat, vname, drainage_type='Drained'):
    """Return Plaxis scripting lines for a Hardening Soil material."""
    safe_name = repr(mat['name'])
    return '\n'.join([
        f'{vname} = g.soilmat()',
        f'{vname}.setproperties("Identification", {safe_name})',
        f'{vname}.setproperties("SoilModel", 3)',          # Hardening Soil
        f'{vname}.setproperties("DrainageType", "{drainage_type}")',
        f'{vname}.setproperties("gammaUnsat", {mat["gamma"]})',
        f'{vname}.setproperties("gammaSat", {mat["gamma_sat"]})',
        f'{vname}.setproperties("E50ref", {mat["E50ref"]})',
        f'{vname}.setproperties("Eoedref", {mat["Eoedref"]})',
        f'{vname}.setproperties("Eurref", {mat["Eurref"]})',
        f'{vname}.setproperties("powerm", {mat["m"]})',
        f'{vname}.setproperties("cref", {mat["c_ref"]})',
        f'{vname}.setproperties("phi", {mat["phi"]})',
        f'{vname}.setproperties("psi", 0.0)',
        f'{vname}.setproperties("OCR", {mat["OCR"]})',
        '',
    ])


def _generate_embankment_stability(problem, version, port, project_name):
    H = problem['embankment_height']
    W = problem['embankment_top_width']
    clay_t = problem['clay_thickness']
    sl = problem['slope_left']
    sr = problem['slope_right']
    fill = problem['fill_material']
    clay = problem['clay_material']

    # Embankment polygon vertices — placed on a 50 m wide model
    # Left toe such that the embankment centre is at x=25
    left_slope_h = sl * H
    right_slope_h = sr * H
    total_emb_width = left_slope_h + W + right_slope_h
    domain_width=max(50.0,total_emb_width+20.0)
    x_left_toe = (domain_width - total_emb_width) / 2.0
    x_left_crest = x_left_toe + left_slope_h
    x_right_crest = x_left_crest + W
    x_right_toe = x_right_crest + right_slope_h

    lines = [_script_header(version, port)]
    lines.append(f'# Bài toán: Ổn định bờ đắp - {project_name}')
    lines.append(f'# Bờ đắp cao {H} m, đỉnh rộng {W} m')
    lines.append(f'# Mái trái {sl:.1f}H:1V, mái phải {sr:.1f}H:1V')
    lines.append(f'# Nền sét dày {clay_t} m, Hardening Soil model')
    lines.append('')
    lines.append('g.gotostructures()')
    lines.append('')
    lines.append('# === Vật liệu ===')
    lines.append('# Vật liệu 1: Đất đắp bờ (Hardening Soil, Drained)')
    lines.append(_hs_soil_lines(fill, 'mat_fill', 'Drained'))
    lines.append('# Vật liệu 2: Sét nền - Drained (Hardening Soil, Drained)')
    lines.append(_hs_soil_lines(clay, 'mat_clay_dr', 'Drained'))
    lines.append('# Vật liệu 3: Sét nền - Undrained (sao chép từ Drained, đổi kiểu)')
    clay_ud_name = repr(clay['name'].replace('Drained', 'Undrained').replace('drained', 'undrained') + ' (UD)' if 'rain' not in clay['name'] else clay['name'].replace('Drained', 'Undrained (A)'))
    lines.append(f'mat_clay_ud = g.soilmat()')
    lines.append(f'mat_clay_ud.setproperties("Identification", {clay_ud_name})')
    lines.append(f'mat_clay_ud.setproperties("SoilModel", 3)')
    lines.append(f'mat_clay_ud.setproperties("DrainageType", "Undrained (A)")')
    lines.append(f'mat_clay_ud.setproperties("gammaUnsat", {clay["gamma"]})')
    lines.append(f'mat_clay_ud.setproperties("gammaSat", {clay["gamma_sat"]})')
    lines.append(f'mat_clay_ud.setproperties("E50ref", {clay["E50ref"]})')
    lines.append(f'mat_clay_ud.setproperties("Eoedref", {clay["Eoedref"]})')
    lines.append(f'mat_clay_ud.setproperties("Eurref", {clay["Eurref"]})')
    lines.append(f'mat_clay_ud.setproperties("powerm", {clay["m"]})')
    lines.append(f'mat_clay_ud.setproperties("cref", {clay["c_ref"]})')
    lines.append(f'mat_clay_ud.setproperties("phi", {clay["phi"]})')
    lines.append(f'mat_clay_ud.setproperties("psi", 0.0)')
    lines.append(f'mat_clay_ud.setproperties("OCR", {clay["OCR"]})')
    lines.append('')

    lines.append('# === Hình học ===')
    lines.append('# Địa tầng: lớp sét từ y=0 đến y={:.1f} m'.format(-clay_t))
    lines.append('g.gotosoil()')
    if version=='2d':
        lines.append(f'g.SoilContour.initializerectangular(0, {-clay_t!r}, {domain_width!r}, {H!r})')
    else:
        length=problem['embankment_length']
        lines.append(f'g.SoilContour.initializerectangular(0, 0, {domain_width!r}, {length!r})')
    lines.append('bh = g.borehole(0)' if version=='2d' else 'bh = g.borehole(0, 0)')
    lines.append(f'bh.Head = 0  # Mực nước ngầm tại mặt đất')
    lines.append(f'g.soillayer({clay_t!r})  # Lớp sét')
    lines.append('')
    lines.append('# Đặt vật liệu drained cho nền sét ban đầu')
    lines.append('g.setmaterial(g.Soillayers[0].Soil, mat_clay_dr)')
    lines.append('g.gotostructures()')
    lines.append('')
    if version=='2d':
        lines.append(f'emb_polygon, emb = g.polygon(({x_left_toe:.2f}, 0), ({x_left_crest:.2f}, {H:.2f}), ({x_right_crest:.2f}, {H:.2f}), ({x_right_toe:.2f}, 0))')
        lines.append('g.setmaterial(emb, mat_fill)')
    else:
        lines.append('# Cross-section in X/Z; extrude along Y to create a soil volume.')
        lines.append(f'emb_surface = g.surface(({x_left_toe:.2f}, 0, 0), ({x_left_crest:.2f}, 0, {H:.2f}), ({x_right_crest:.2f}, 0, {H:.2f}), ({x_right_toe:.2f}, 0, 0))')
        lines.append(f'g.extrude(emb_surface, 0, {length!r}, 0)')
        lines.append('emb_volume = g.Volumes[-1]')
        lines.append('emb_polygon = emb_volume')
        lines.append('g.setmaterial(emb_volume.Soil, mat_fill)')
    lines.append('')

    lines.append('# === Lưới phần tử (Fine) ===')
    lines.append('g.gotomesh()')
    lines.append('g.mesh(0.04)  # Fine element distribution (coarseness ~0.04)')
    lines.append('')

    lines.append('# === Các giai đoạn tính toán ===')
    lines.append('g.gotostages()')
    lines.append('')
    lines.append('# Giai đoạn ban đầu: ứng suất K0 (mặc định)')
    lines.append('phase0 = g.InitialPhase')
    lines.append('phase0.Identification = "Ung suat ban dau K0"')
    lines.append('g.deactivate(emb_polygon, phase0)  # Bờ đắp chưa thi công trong Initial phase')
    lines.append('')
    lines.append('# Giai đoạn 1: Thi công bờ đắp, nền DRAINED (ổn định dài hạn)')
    lines.append('phase1 = g.phase(phase0)')
    lines.append('phase1.Identification = "Dap bo (Drained)"')
    lines.append('phase1.DeformCalcType = "Plastic"')
    lines.append('phase1.LoadingType = "Staged construction"')
    lines.append('phase1.ShouldCalculate = True')
    lines.append('g.activate(emb_polygon, phase1)')
    lines.append('')
    lines.append('# Giai đoạn 2: Thi công bờ đắp, nền UNDRAINED (ổn định ngắn hạn)')
    lines.append('phase2 = g.phase(phase0)')
    lines.append('phase2.Identification = "Dap bo (Undrained)"')
    lines.append('phase2.DeformCalcType = "Plastic"')
    lines.append('phase2.LoadingType = "Staged construction"')
    lines.append('phase2.ShouldCalculate = True')
    lines.append('g.activate(emb_polygon, phase2)')
    lines.append('# Resolve current staged soil clusters by their initial material, not Soil-mode layers.')
    lines.append('clay_clusters = [soil for soil in g.Soils if str(soil.Material[phase0].Identification) == str(mat_clay_dr.Identification)]')
    lines.append('if not clay_clusters:')
    lines.append('    raise RuntimeError("Khong tim thay cum dat set Drained trong Staged construction")')
    lines.append('for soil in clay_clusters:')
    lines.append('    g.setmaterial(soil, phase2, mat_clay_ud)')
    lines.append('')
    lines.append('# Giai đoạn 3: Tính hệ số an toàn (Phi-c reduction) từ pha Drained')
    lines.append('phase3 = g.phase(phase1)')
    lines.append('phase3.Identification = "He so an toan SF (Drained)"')
    lines.append('phase3.DeformCalcType = "Safety"')
    lines.append('phase3.ShouldCalculate = True')
    lines.append('')
    lines.append('# Giai đoạn 4: Tính hệ số an toàn từ pha Undrained')
    lines.append('phase4 = g.phase(phase2)')
    lines.append('phase4.Identification = "He so an toan SF (Undrained)"')
    lines.append('phase4.DeformCalcType = "Safety"')
    lines.append('phase4.ShouldCalculate = True')
    lines.append('')
    lines.append('g.calculate()')
    lines.append('g.view(phase1)')
    lines.append('print("Hoan thanh phan tich on dinh bo dap.")')
    lines.append('try:')
    lines.append('    print(f"SF Drained  = {phase3.ReachedValue.SumMsf:.3f}")')
    lines.append('    print(f"SF Undrained = {phase4.ReachedValue.SumMsf:.3f}")')
    lines.append('except Exception as e:')
    lines.append('    print(f"Chua doc duoc SF: {e}")')
    return '\n'.join(lines)


def _generate_script(problem, version, port, project_name):
    ptype = problem['type']
    if version=='3d':
        if ptype!='embankment_stability':
            raise ValueError('Mẫu PLAXIS 3D hiện hỗ trợ bờ đắp; bài toán này cần hình học và tải trọng 3D riêng, không dùng script 2D.')
        if 'embankment_length' not in problem:
            raise ValueError('PLAXIS 3D cần embankment_length (chiều dài dọc tuyến, m); không tự suy đoán từ đề 2D.')
    if ptype == 'slope_stability':
        return _generate_slope_stability(problem, version, port, project_name)
    if ptype == 'foundation_settlement':
        return _generate_foundation_settlement(problem, version, port, project_name)
    if ptype == 'retaining_wall':
        return _generate_retaining_wall(problem, version, port, project_name)
    if ptype == 'excavation_pit':
        return _generate_excavation_pit(problem, version, port, project_name)
    return _generate_embankment_stability(problem, version, port, project_name)


class PlaxisApp:
    def __init__(self, files, audit):
        self.files = files
        self.audit = audit

    def prepare(self, name, args):
        project_name = args.get('project_name', '')
        if not isinstance(project_name, str) or not project_name.strip():
            raise ValueError('project_name là bắt buộc.')
        if len(project_name) > 100:
            raise ValueError('project_name tối đa 100 ký tự.')
        if any(c in project_name for c in '/\\:'):
            raise ValueError('project_name không được chứa ký tự phân cách đường dẫn (/, \\, :).')
        project_name = project_name.strip()

        version = args.get('version', '')
        if version not in ('2d', '3d'):
            raise ValueError("version phải là '2d' hoặc '3d'.")

        problem = _validate_problem(args.get('problem', ''))

        _generate_script(problem, version, _PORT[version], project_name)  # Reject missing 3D geometry before preview.

        if not self.files.roots:
            raise PermissionError('Thêm thư mục lưu script được phép trong Cài đặt.')

        safe_name = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in project_name)
        filename = f'Plaxis_{safe_name}_{uuid.uuid4().hex[:8]}.py'
        path = self.files.path(str(self.files.roots[0] / filename), exists=False)

        auto_run = bool(args.get('auto_run', False))

        return {
            'action': 'plaxis_generate_script',
            'path': str(path),
            'project_name': project_name,
            'version': version,
            'problem': problem,
            'auto_run': auto_run,
        }

    def commit(self, plan):
        problem = plan['problem']
        version = plan['version']
        project_name = plan['project_name']
        port = _PORT[version]

        script = _generate_script(problem, version, port, project_name)

        path = self.files.path(plan['path'], exists=False)
        if path.exists():
            raise FileExistsError('Không ghi đè script đã có.')

        path.write_text(script, encoding='utf-8')

        self.audit('plaxis_script_generated', {
            'path': str(path),
            'version': version,
            'problem_type': problem['type'],
            'project_name': project_name,
        })

        result = {
            'ok': True,
            'path': str(path),
            'files': [str(path)],
            'version': version,
            'problem_type': problem['type'],
        }

        if plan.get('auto_run'):
            run_result = self._run_on_plaxis(script, version, port)
            result['executed'] = run_result['executed']
            result['output'] = run_result.get('output', '')
            if run_result['executed']:
                result['note'] = 'Script đã chạy trực tiếp trên Plaxis ' + version.upper() + '. File script cũng được lưu tại: ' + str(path)
            else:
                result['note'] = run_result.get('error', '') + ' Script đã lưu tại: ' + str(path) + ' — bạn có thể chạy thủ công bằng File > Run Script.'
        else:
            result['executed'] = False
            result['note'] = 'Mở Plaxis, chạy script bằng File > Run Script hoặc Remote Scripting Server.'

        return result

    @staticmethod
    def _run_on_plaxis(script, version, port):
        """Try to connect to a running Plaxis instance and execute the script."""
        try:
            from plxscripting.easy import new_server
        except ImportError:
            from .plaxis_dependency import missing_scripting_message
            return {'executed': False, 'error': missing_scripting_message()}

        try:
            s, g = new_server('localhost', port, password='')
            s.new()
        except Exception as e:
            return {'executed': False,
                    'error': f'Không kết nối được Plaxis {version.upper()} (port {port}). '
                             f'Hãy mở Plaxis và bật Remote Scripting Server (Expert > Configure remote scripting server). Lỗi: {e}'}

        output_lines = []
        import io, contextlib
        buf = io.StringIO()
        # Execute each line except the import/connection boilerplate (first 3 lines)
        exec_lines = []
        skip_header = True
        for line in script.splitlines():
            if skip_header:
                if line.startswith('s, g = new_server') or line.startswith('from plxscripting'):
                    continue
                if line.startswith('#') and not exec_lines:
                    continue
                skip_header = False
            exec_lines.append(line)

        exec_code = '\n'.join(exec_lines)
        try:
            with contextlib.redirect_stdout(buf):
                exec(exec_code, {'s': s, 'g': g, '__builtins__': __builtins__})
            output_lines.append(buf.getvalue())
            return {'executed': True, 'output': '\n'.join(output_lines).strip()}
        except Exception as e:
            return {'executed': False,
                    'error': f'Script lỗi khi chạy trên Plaxis: {e}',
                    'output': buf.getvalue()}

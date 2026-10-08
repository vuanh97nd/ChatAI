"""Generate Plaxis 2D/3D Python scripts for geotechnical analysis.

Supports two modes:
1. Generate-only: creates a .py script file for user to run manually.
2. Auto-run: connects to a running Plaxis instance via plxscripting and
   executes the generated commands directly, returning live results.
"""
import json
import uuid
from pathlib import Path

_SUPPORTED_TYPES = {'slope_stability', 'foundation_settlement', 'retaining_wall'}

_PORT = {'2d': 10000, '3d': 10001}


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
    c = _num(layer.get('c', -1), f'{prefix} c', 0.0, 1e6)
    phi = _num(layer.get('phi', -1), f'{prefix} phi', 0.0, 89.0)
    name = layer.get('name', f'Layer{idx}')
    if not isinstance(name, str) or not name or len(name) > 100:
        raise ValueError(f'{prefix} name phải là chuỗi 1-100 ký tự.')
    if any(c in name for c in ('\n', '\r', '\0')):
        raise ValueError(f'{prefix} name chứa ký tự xuống dòng không hợp lệ.')
    thickness = _num(layer.get('thickness', -1), f'{prefix} thickness', 0.01, 1000.0)
    return {'name': name, 'E': E, 'nu': nu, 'gamma': gamma, 'c': c, 'phi': phi, 'thickness': thickness}


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
    return _validate_retaining_wall(problem)


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
        lines.append(f'{vname}.setproperties("MaterialName", {safe_name})')
        lines.append(f'{vname}.setproperties("SoilModel", 2)')  # Mohr-Coulomb
        lines.append(f'{vname}.setproperties("Eref", {layer["E"]})')
        lines.append(f'{vname}.setproperties("nu", {layer["nu"]})')
        lines.append(f'{vname}.setproperties("gammaUnsat", {layer["gamma"]})')
        lines.append(f'{vname}.setproperties("gammaSat", {layer["gamma"] + 2.0})')
        lines.append(f'{vname}.setproperties("cref", {layer["c"]})')
        lines.append(f'{vname}.setproperties("phi", {layer["phi"]})')
        lines.append('')
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

    # Geometry: simple slope polygon
    lines.append('# Hình học mái dốc')
    lines.append(f'g.borehole(0)')
    depth = sum(l['thickness'] for l in layers)
    lines.append(f'g.borehole(0).Head = 0')
    cum = 0.0
    for i, layer in enumerate(layers):
        cum += layer['thickness']
        lines.append(f'g.soillayer({i})')

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
    lines.append(f'phase1.Identification = "Phan tich on dinh mai doc - {analysis}"')
    lines.append('phase1.ShouldCalculate = True')
    lines.append('')
    lines.append('g.calculate()')
    lines.append('g.view(phase1)')
    lines.append(f'print("Hoan thanh phan tich on dinh mai doc bang {analysis}.")')
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
    lines.append(f'g.borehole(0)')
    for i, layer in enumerate(layers):
        lines.append(f'g.soillayer({i})  # {layer["name"]}, dày {layer["thickness"]} m')
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
    lines.append('# Vật liệu tường (bê tông cốt thép)')
    lines.append('wall_mat = g.platemat()')
    lines.append('wall_mat.setproperties("MaterialName", "Tuong BTCT")')
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


def _generate_script(problem, version, port, project_name):
    ptype = problem['type']
    if ptype == 'slope_stability':
        return _generate_slope_stability(problem, version, port, project_name)
    if ptype == 'foundation_settlement':
        return _generate_foundation_settlement(problem, version, port, project_name)
    return _generate_retaining_wall(problem, version, port, project_name)


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
            return {'executed': False, 'error': 'Chưa cài plxscripting. Chạy: pip install plxscripting'}

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

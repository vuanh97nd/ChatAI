"""PLAXIS file/runtime adapter; calculations use the restored historical engine."""
import json
import uuid
from pathlib import Path
from .plaxis_calculation import (
    _SUPPORTED_TYPES,
    _PORT,
    _num,
    _validate_soil_layer,
    _validate_slope_stability,
    _validate_foundation_settlement,
    _validate_retaining_wall,
    _validate_excavation_pit,
    _validate_hs_soil,
    _FILL_DEFAULTS,
    _CLAY_DEFAULTS,
    _validate_embankment_stability,
    _validate_problem,
    _script_header,
    _soil_lines,
    _stratigraphy_lines,
    _generate_slope_stability,
    _generate_foundation_settlement,
    _generate_retaining_wall,
    _generate_excavation_pit,
    _hs_soil_lines,
    _generate_embankment_stability,
    _generate_script,
)

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

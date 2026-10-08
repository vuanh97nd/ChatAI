"""Plaxis 2D Remote Scripting integration for ChatAI.

Connects to a running Plaxis 2D instance via its Remote Scripting Server,
executes geotechnical analyses, and returns structured numerical results
(settlements, stresses, safety factors).

Prerequisites (on the user's machine):
  1. pip install plxscripting
  2. Plaxis 2D → Expert menu → Configure remote scripting server → Start
     Input port: 10000, Output port: 10001

This module is the "run and read results" layer; script generation is handled
by plaxis_app.py. The tool exposed here is plaxis_run_problem.
"""
import json
import logging
import textwrap

logger = logging.getLogger(__name__)

_INPUT_PORT = {'2d': 10000, '3d': 10000}
_OUTPUT_PORT = {'2d': 10001, '3d': 10001}
_VERSION_LABEL = {'2d': 'PLAXIS 2D', '3d': 'PLAXIS 3D'}


# ── Connection helpers ────────────────────────────────────────────────────────

def _connect(port, label):
    """Connect to a Plaxis Remote Scripting Server and return (server, globals)."""
    try:
        from plxscripting.easy import new_server
    except ImportError:
        raise RuntimeError(
            'Chưa cài plxscripting. Chạy: pip install plxscripting\n'
            'Sau đó khởi động lại ChatAI.'
        )
    try:
        s, g = new_server('localhost', port, password='')
        return s, g
    except Exception as exc:
        raise RuntimeError(
            f'Không thể kết nối {label} tại localhost:{port}.\n'
            f'Hãy mở Plaxis và bật Remote Scripting Server:\n'
            f'  Expert → Configure remote scripting server → Start\n'
            f'Lỗi gốc: {exc}'
        ) from exc


# ── Result extraction ─────────────────────────────────────────────────────────

def _safe_list(obj):
    """Convert a plxscripting result object to a plain Python list of floats."""
    try:
        return [float(v) for v in obj]
    except Exception:
        return []


def _extract_results(g_out, phases, problem_type):
    """Extract settlement, stress, and safety-factor results from Plaxis Output.

    Returns a dict with keys: max_settlement_mm, max_stress_kpa, safety_factor,
    phase_results (list of per-phase summary dicts), raw_summary (human text).
    """
    results = {
        'max_settlement_mm': None,
        'max_horizontal_displacement_mm': None,
        'max_stress_kpa': None,
        'safety_factor': None,
        'phase_results': [],
        'raw_summary': '',
    }
    summary_lines = []

    for phase in phases:
        phase_id = _phase_name(phase)
        phase_entry = {'phase': phase_id}

        # Settlement (Uy – vertical displacement, negative = downward)
        try:
            uy_vals = _safe_list(
                g_out.getresults(phase, g_out.ResultTypes.Soil.Deformations.Uy, 'node')
            )
            if uy_vals:
                max_set = abs(min(uy_vals))  # most negative = largest settlement
                phase_entry['max_settlement_mm'] = round(max_set * 1000, 2)
                if results['max_settlement_mm'] is None or max_set > results['max_settlement_mm']:
                    results['max_settlement_mm'] = round(max_set * 1000, 2)
        except Exception:
            pass

        # Horizontal displacement (Ux)
        try:
            ux_vals = _safe_list(
                g_out.getresults(phase, g_out.ResultTypes.Soil.Deformations.Ux, 'node')
            )
            if ux_vals:
                max_horiz = max(abs(v) for v in ux_vals)
                phase_entry['max_horizontal_displacement_mm'] = round(max_horiz * 1000, 2)
                if (results['max_horizontal_displacement_mm'] is None
                        or max_horiz > results['max_horizontal_displacement_mm']):
                    results['max_horizontal_displacement_mm'] = round(max_horiz * 1000, 2)
        except Exception:
            pass

        # Effective mean stress (p')
        try:
            stress_vals = _safe_list(
                g_out.getresults(
                    phase,
                    g_out.ResultTypes.Soil.Stresses.EffectiveMeanStress,
                    'node'
                )
            )
            if stress_vals:
                max_s = max(abs(v) for v in stress_vals)
                phase_entry['max_stress_kpa'] = round(max_s, 1)
                if results['max_stress_kpa'] is None or max_s > results['max_stress_kpa']:
                    results['max_stress_kpa'] = round(max_s, 1)
        except Exception:
            pass

        # Safety factor (SumMsf — phi-c reduction phases only)
        try:
            sf = float(phase.Reached.SumMsf)
            if sf > 0.1:
                phase_entry['safety_factor'] = round(sf, 3)
                results['safety_factor'] = round(sf, 3)
        except Exception:
            pass

        results['phase_results'].append(phase_entry)
        parts = [f"Giai đoạn: {phase_id}"]
        if 'max_settlement_mm' in phase_entry:
            parts.append(f"Lún max: {phase_entry['max_settlement_mm']} mm")
        if 'max_horizontal_displacement_mm' in phase_entry:
            parts.append(f"Chuyển vị ngang max: {phase_entry['max_horizontal_displacement_mm']} mm")
        if 'safety_factor' in phase_entry:
            parts.append(f"SF: {phase_entry['safety_factor']}")
        summary_lines.append(' | '.join(parts))

    results['raw_summary'] = '\n'.join(summary_lines)
    return results


def _phase_name(phase):
    try:
        return str(phase.Identification)
    except Exception:
        return str(phase)


# ── Script execution ──────────────────────────────────────────────────────────

def _exec_script_on_server(script_text, s_in, g_in):
    """Execute a generated Plaxis script on the already-connected Input server.

    Strips the connection boilerplate (new_server lines) then runs the rest
    in a namespace that has s=s_in, g=g_in already bound.
    """
    import io
    import contextlib

    exec_lines = []
    skip = True
    for line in script_text.splitlines():
        if skip:
            # Skip header comment lines and the new_server import/call
            if line.startswith('from plxscripting') or line.startswith('s, g = new_server'):
                continue
            if not line.strip() or line.startswith('#'):
                if not exec_lines:
                    continue
            skip = False
        exec_lines.append(line)

    code = '\n'.join(exec_lines)
    buf = io.StringIO()
    ns = {'s': s_in, 'g': g_in, '__builtins__': __builtins__}
    with contextlib.redirect_stdout(buf):
        exec(code, ns)  # noqa: S102
    return buf.getvalue().strip()


# ── Core public API ───────────────────────────────────────────────────────────

def _remote_scripting_available(version='2d'):
    """Quick TCP probe: True if the Plaxis Input port is accepting connections."""
    import socket
    port = _INPUT_PORT.get(version, 10000)
    try:
        with socket.create_connection(('localhost', port), timeout=1.5):
            return True
    except OSError:
        return False


def run_plaxis_problem(script_text, version='2d', problem_type='excavation_pit',
                       ui_fallback=False, ui_script_dir=None,
                       ui_screenshot_path=None, plaxis_exe=None):
    """Connect to Plaxis, run script_text, read results from Output server.

    When the Remote Scripting Server is unreachable and ui_fallback=True,
    automatically falls back to UI Control (File > Run Script).

    Returns a dict:
      executed: bool
      mode: 'remote_scripting' | 'ui_control'
      output: stdout captured during script execution
      results: structured result dict (settlements, stresses, SF) or {}
      error: error message string if executed=False
      screenshot: path to PNG screenshot (ui_control mode only)
    """
    version = version.lower()
    label = _VERSION_LABEL.get(version, 'PLAXIS')
    in_port = _INPUT_PORT[version]
    out_port = _OUTPUT_PORT[version]

    # ── Try Remote Scripting first ─────────────────────────────────────────
    try:
        s_in, g_in = _connect(in_port, f'{label} Input')
    except RuntimeError as exc:
        if ui_fallback:
            logger.info('Remote Scripting unavailable (%s); falling back to UI control.', exc)
            return _ui_control_fallback(
                script_text, version, problem_type,
                ui_script_dir, ui_screenshot_path, plaxis_exe,
            )
        return {'executed': False, 'output': '', 'results': {}, 'mode': 'remote_scripting',
                'screenshot': None, 'error': str(exc)}

    try:
        s_in.new()
    except Exception as exc:
        return {
            'executed': False, 'output': '', 'results': {}, 'mode': 'remote_scripting',
            'screenshot': None, 'error': f'Không thể tạo dự án mới trên {label}: {exc}'
        }

    try:
        stdout = _exec_script_on_server(script_text, s_in, g_in)
    except Exception as exc:
        return {
            'executed': False, 'output': '', 'results': {}, 'mode': 'remote_scripting',
            'screenshot': None, 'error': f'Lỗi khi chạy script trên {label}: {exc}'
        }

    # Extract results from Output server
    structured = {}
    try:
        s_out, g_out = _connect(out_port, f'{label} Output')
        phases = list(s_out.Phases)
        if phases:
            structured = _extract_results(g_out, phases, problem_type)
        else:
            structured = {'raw_summary': 'Không có giai đoạn nào sau khi tính toán.'}
    except Exception as exc:
        logger.warning('Không đọc được kết quả từ Output server: %s', exc)
        structured = {'raw_summary': f'Script đã chạy nhưng không đọc được kết quả số: {exc}'}

    return {
        'executed': True,
        'mode': 'remote_scripting',
        'output': stdout,
        'results': structured,
        'screenshot': None,
        'error': '',
    }


def _ui_control_fallback(script_text, version, problem_type,
                         script_dir, screenshot_path, plaxis_exe):
    """Delegate to plaxis_ui_control.run_via_ui and normalise return shape."""
    from .plaxis_ui_control import run_via_ui
    import tempfile, os

    if not script_dir:
        script_dir = tempfile.gettempdir()
    if not screenshot_path:
        import uuid as _uuid
        screenshot_path = os.path.join(str(script_dir), f'plaxis_{_uuid.uuid4().hex[:8]}.png')

    ui_result = run_via_ui(
        script_text=script_text,
        script_dir=script_dir,
        screenshot_path=screenshot_path,
        plaxis_exe=plaxis_exe,
    )
    return {
        'executed': ui_result['executed'],
        'mode': 'ui_control',
        'output': '',
        'results': {},
        'screenshot': ui_result.get('screenshot'),
        'error': ui_result.get('error', ''),
    }


# ── ChatAI Tool interface ─────────────────────────────────────────────────────

class PlaxisRemoteApp:
    """ChatAI tool: generate + run + read results from Plaxis Remote Scripting Server."""

    def __init__(self, plaxis_app):
        self._app = plaxis_app  # PlaxisApp instance for script generation

    def prepare(self, name, args):
        version = args.get('version', '')
        if version not in ('2d', '3d'):
            raise ValueError("version phải là '2d' hoặc '3d'.")

        from .plaxis_app import _validate_problem, _generate_script, _PORT
        problem = _validate_problem(args.get('problem', ''))
        port = _PORT[version]
        project_name = args.get('project_name', 'PlaxisRemote')
        if not isinstance(project_name, str) or not project_name.strip():
            raise ValueError('project_name là bắt buộc.')
        if len(project_name) > 100:
            raise ValueError('project_name tối đa 100 ký tự.')
        project_name = project_name.strip()

        plaxis_exe = args.get('plaxis_exe', '') or None
        if plaxis_exe and len(plaxis_exe) > 4096:
            raise ValueError('plaxis_exe đường dẫn quá dài.')

        script = _generate_script(problem, version, port, project_name)

        return {
            'action': 'plaxis_run_problem',
            'version': version,
            'problem_type': problem['type'],
            'project_name': project_name,
            'plaxis_exe': plaxis_exe,
            'script': script,
        }

    def commit(self, plan):
        # Determine where to save temp files for UI fallback
        ui_script_dir = None
        ui_screenshot_path = None
        if self._app.files.roots:
            import uuid as _uuid
            ui_script_dir = self._app.files.roots[0]
            ui_screenshot_path = ui_script_dir / f'Plaxis_UI_{_uuid.uuid4().hex[:8]}.png'

        result = run_plaxis_problem(
            plan['script'],
            version=plan['version'],
            problem_type=plan['problem_type'],
            ui_fallback=True,
            ui_script_dir=ui_script_dir,
            ui_screenshot_path=ui_screenshot_path,
            plaxis_exe=plan.get('plaxis_exe'),
        )

        if not result['executed']:
            return {
                'ok': False,
                'error': result['error'],
                'note': result['error'],
            }

        mode = result.get('mode', 'remote_scripting')
        res = result.get('results', {})
        lines = [
            f"Phân tích {plan['problem_type']} ({plan['version'].upper()}) hoàn tất "
            f"[{mode.replace('_', ' ')}].",
        ]

        if mode == 'ui_control':
            shot = result.get('screenshot')
            if shot:
                lines.append(f"Ảnh chụp kết quả: {shot}")
            else:
                lines.append('Script đã chạy qua UI Control. Xem kết quả trong Plaxis.')
        else:
            if res.get('max_settlement_mm') is not None:
                lines.append(f"Lún lớn nhất: {res['max_settlement_mm']} mm")
            if res.get('max_horizontal_displacement_mm') is not None:
                lines.append(f"Chuyển vị ngang lớn nhất: {res['max_horizontal_displacement_mm']} mm")
            if res.get('safety_factor') is not None:
                lines.append(f"Hệ số an toàn (SF): {res['safety_factor']}")
            if res.get('raw_summary'):
                lines.append('')
                lines.append('Chi tiết các giai đoạn:')
                lines.append(res['raw_summary'])
            if result.get('output'):
                lines.append('')
                lines.append('Output Plaxis:')
                lines.append(textwrap.indent(result['output'], '  '))

        out = {
            'ok': True,
            'executed': True,
            'mode': mode,
            'max_settlement_mm': res.get('max_settlement_mm'),
            'max_horizontal_displacement_mm': res.get('max_horizontal_displacement_mm'),
            'safety_factor': res.get('safety_factor'),
            'phase_results': res.get('phase_results', []),
            'note': '\n'.join(lines),
        }
        if result.get('screenshot'):
            out['screenshot'] = result['screenshot']
            out['files'] = [result['screenshot']]
        return out

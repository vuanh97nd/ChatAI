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
        from .plaxis_dependency import missing_scripting_message
        raise RuntimeError(missing_scripting_message()) from None
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
                g_out.getresults(phase, g_out.ResultTypes.Soil.Uy, 'node')
            )
            if uy_vals:
                max_set = abs(min(uy_vals))  # most negative = largest settlement
                phase_entry['max_settlement_mm'] = round(max_set * 1000, 2)
                if results['max_settlement_mm'] is None or max_set * 1000 > results['max_settlement_mm']:
                    results['max_settlement_mm'] = round(max_set * 1000, 2)
        except Exception:
            pass

        # Horizontal displacement (Ux)
        try:
            ux_vals = _safe_list(
                g_out.getresults(phase, g_out.ResultTypes.Soil.Ux, 'node')
            )
            if ux_vals:
                max_horiz = max(abs(v) for v in ux_vals)
                phase_entry['max_horizontal_displacement_mm'] = round(max_horiz * 1000, 2)
                if (results['max_horizontal_displacement_mm'] is None
                        or max_horiz * 1000 > results['max_horizontal_displacement_mm']):
                    results['max_horizontal_displacement_mm'] = round(max_horiz * 1000, 2)
        except Exception:
            pass

        # Effective mean stress (p')
        try:
            stress_vals = _safe_list(
                g_out.getresults(
                    phase,
                    g_out.ResultTypes.Soil.MeanEffStress,
                    'stress point'
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

def phase_diagnostics(globals_object):
    """Read actual Input calculation status; a returned calculate command is not success."""
    try:phases=list(globals_object.Phases)
    except Exception:return []
    rows=[]
    for phase in phases[:20]:
        try:
            raw=phase.CalculationResult
            status=int(getattr(raw,'value',raw))
        except Exception:continue
        try:
            value=phase.LogInfo
            log=str(getattr(value,'value',value))[:2000]
        except Exception:log=''
        rows.append({'name':_phase_name(phase),'status':status,'log':log})
    return rows


def run_plaxis_problem(script_text, version='2d', problem_type='excavation_pit'):
    """Connect to Plaxis, run script_text, read results from Output server.

    Returns a dict:
      executed: bool
      output: stdout captured during script execution
      results: structured result dict (settlements, stresses, SF) or {}
      error: error message string if executed=False
    """
    version = version.lower()
    label = _VERSION_LABEL.get(version, 'PLAXIS')
    in_port = _INPUT_PORT[version]
    out_port = _OUTPUT_PORT[version]

    try:
        s_in, g_in = _connect(in_port, f'{label} Input')
    except RuntimeError as exc:
        return {'executed': False, 'output': '', 'results': {}, 'error': str(exc)}

    try:
        s_in.new()
    except Exception as exc:
        return {
            'executed': False, 'output': '', 'results': {},
            'error': f'Không thể tạo dự án mới trên {label}: {exc}'
        }

    try:
        stdout = _exec_script_on_server(script_text, s_in, g_in)
    except Exception as exc:
        return {
            'executed': False, 'output': '', 'results': {},
            'error': f'Lỗi khi chạy script trên {label}: {exc}',
            'phase_diagnostics': phase_diagnostics(g_in)
        }

    diagnostics=phase_diagnostics(g_in)
    failed=[row for row in diagnostics if row['status'] in (2,3)]
    if failed:
        return {'executed':False,'output':stdout,'results':{},'phase_diagnostics':diagnostics,
                'error':'Phase tính toán chưa thành công: '+ '; '.join(row['name']+': '+(row['log'] or 'CalculationResult='+str(row['status'])) for row in failed)}

    # Extract results from Output server
    structured = {}
    try:
        s_out, g_out = _connect(out_port, f'{label} Output')
        phases = list(g_out.Phases)
        if phases:
            structured = _extract_results(g_out, phases, problem_type)
        else:
            structured = {'raw_summary': 'Không có giai đoạn nào sau khi tính toán.'}
    except Exception as exc:
        logger.warning('Không đọc được kết quả từ Output server: %s', exc)
        structured = {'raw_summary': f'Script đã chạy nhưng không đọc được kết quả số: {exc}'}

    return {
        'executed': True,
        'output': stdout,
        'results': structured,
        'error': '',
        'phase_diagnostics':diagnostics,
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

        # Reuse PlaxisApp validation — but we don't need a file path
        # We still call _validate_problem from plaxis_app
        from .plaxis_app import _validate_problem, _generate_script, _PORT
        problem = _validate_problem(args.get('problem', ''))
        port = _PORT[version]
        project_name = args.get('project_name', 'PlaxisRemote')
        if not isinstance(project_name, str) or not project_name.strip():
            raise ValueError('project_name là bắt buộc.')
        if len(project_name) > 100:
            raise ValueError('project_name tối đa 100 ký tự.')
        project_name = project_name.strip()

        script = _generate_script(problem, version, port, project_name)

        return {
            'action': 'plaxis_run_problem',
            'version': version,
            'problem_type': problem['type'],
            'project_name': project_name,
            'script': script,
        }

    def commit(self, plan):
        result = run_plaxis_problem(
            plan['script'],
            version=plan['version'],
            problem_type=plan['problem_type'],
        )

        if not result['executed']:
            return {
                'ok': False,
                'error': result['error'],
                'note': result['error'],
                'phase_diagnostics':result.get('phase_diagnostics',[]),
            }

        res = result.get('results', {})
        if not any(res.get(k) is not None for k in ('max_settlement_mm','max_horizontal_displacement_mm','safety_factor')):
            return {'ok':False,'executed':True,'results_unavailable':True,
                    'error':res.get('raw_summary') or 'Chưa đọc được kết quả số từ Output.',
                    'note':'Đã gửi lệnh chạy nhưng chưa xác nhận kết quả tính toán. '+str(res.get('raw_summary',''))}
        lines = [
            f"Phân tích {plan['problem_type']} ({plan['version'].upper()}) hoàn tất.",
        ]
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

        return {
            'ok': True,
            'executed': True,
            'max_settlement_mm': res.get('max_settlement_mm'),
            'max_horizontal_displacement_mm': res.get('max_horizontal_displacement_mm'),
            'safety_factor': res.get('safety_factor'),
            'phase_results': res.get('phase_results', []),
            'note': '\n'.join(lines),
        }

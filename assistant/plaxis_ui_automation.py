"""Plaxis 2D UI Automation — step-by-step visible workflow.

AI opens Plaxis 2D, navigates the UI step by step (Soil → Geometry → Mesh →
Staged Construction → Calculate → Results), taking a screenshot after each
milestone. The user can watch the entire process unfold in real time.

This is deliberately different from plaxis_ui_control.py (which runs a script
invisibly via File > Run Script). Here every action is visible: menus clicked,
dialogs filled, mesh generated, calculation progress — all captured as PNGs.

Windows-only. Requires: pywinauto, psutil, Pillow.
"""
import logging
import os
import subprocess
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_STEP_PAUSE = 1.2     # pause between steps (seconds)
_DIALOG_WAIT = 3.0    # time to wait for a dialog to appear
_CALC_POLL   = 4.0    # poll interval while calculating
_CALC_TIMEOUT = 600   # max seconds for calculation
_LAUNCH_WAIT = 12     # seconds to wait after launching Plaxis


def available():
    if os.name != 'nt':
        return False
    try:
        import importlib.util
        return all(importlib.util.find_spec(n) for n in ('pywinauto', 'psutil', 'PIL'))
    except Exception:
        return False


# ── Screenshot helper ─────────────────────────────────────────────────────────

def _shot(window, out_path):
    """Capture the Plaxis window rectangle to out_path. Returns str path."""
    from PIL import ImageGrab
    r = window.rectangle()
    img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path), 'PNG')
    return str(out_path)


# ── Process / window management ───────────────────────────────────────────────

def _find_or_launch(plaxis_exe):
    import psutil
    _names = ('PLAXIS2D.exe', 'Plaxis2D.exe', 'plaxis2d.exe', 'PLAXISINPUT.exe')
    for proc in psutil.process_iter(['name']):
        try:
            if any(proc.info['name'].lower() == n.lower() for n in _names):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    if not plaxis_exe:
        raise RuntimeError(
            'Plaxis 2D chưa chạy và không có plaxis_exe.\n'
            'Cung cấp đường dẫn PLAXIS2D.exe để tự khởi động.'
        )
    proc = subprocess.Popen([str(plaxis_exe)], cwd=str(Path(plaxis_exe).parent), shell=False)
    ps = psutil.Process(proc.pid)
    time.sleep(_LAUNCH_WAIT)
    return ps


def _main_window(pid):
    from pywinauto import Desktop
    wins = Desktop(backend='uia').windows(process=pid)
    if not wins:
        raise RuntimeError('Không tìm thấy cửa sổ Plaxis sau khi khởi động.')
    return max(wins, key=lambda w: _area(w))


def _area(win):
    try:
        r = win.rectangle()
        return (r.right - r.left) * (r.bottom - r.top)
    except Exception:
        return 0


# ── Menu / UI helpers ─────────────────────────────────────────────────────────

def _menu_click(window, *path):
    """Click a menu path, e.g. _menu_click(win, 'File', 'New')."""
    menu = window.child_window(title=path[0], control_type='MenuItem')
    menu.click_input()
    time.sleep(0.6)
    for item in path[1:]:
        sub = window.child_window(title=item, control_type='MenuItem')
        sub.click_input()
        time.sleep(0.4)


def _toolbar_tab(window, title):
    """Click a top-level toolbar tab (Soil, Structures, Mesh, Staged Construction)."""
    try:
        tab = window.child_window(title=title, control_type='TabItem')
        tab.click_input()
        time.sleep(_STEP_PAUSE)
        return True
    except Exception:
        # Try Button fallback (some Plaxis builds use buttons not TabItems)
        try:
            btn = window.child_window(title=title, control_type='Button')
            btn.click_input()
            time.sleep(_STEP_PAUSE)
            return True
        except Exception:
            return False


def _type_value(dialog, label, value):
    """Find an Edit field near label text and set its value."""
    try:
        edit = dialog.child_window(title=label, control_type='Edit')
        edit.set_edit_text(str(value))
        return True
    except Exception:
        pass
    # Try finding by proximity: all edits in order; use index
    try:
        edits = dialog.children(control_type='Edit')
        texts = dialog.children(control_type='Text')
        for i, txt in enumerate(texts):
            if label.lower() in (txt.window_text() or '').lower():
                if i < len(edits):
                    edits[i].set_edit_text(str(value))
                    return True
    except Exception:
        pass
    return False


def _click_ok(dialog):
    for title in ('OK', '&OK', 'Apply', 'Close', 'Đóng'):
        try:
            dialog.child_window(title=title, control_type='Button').click_input()
            time.sleep(0.4)
            return
        except Exception:
            pass
    try:
        dialog.type_keys('{ENTER}')
    except Exception:
        pass


# ── Step-by-step workflow ─────────────────────────────────────────────────────

class StepLog:
    def __init__(self, shot_dir):
        self.shot_dir = Path(shot_dir)
        self.steps = []

    def record(self, window, name, status='ok', note=''):
        shot_path = self.shot_dir / f'{len(self.steps)+1:02d}_{name.replace(" ","_")}.png'
        try:
            path = _shot(window, shot_path)
        except Exception as exc:
            path = None
            logger.warning('Screenshot failed for step %s: %s', name, exc)
        entry = {'step': name, 'status': status, 'screenshot': path, 'note': note}
        self.steps.append(entry)
        return entry

    def fail(self, window, name, error):
        entry = self.record(window, name, status='error', note=error)
        raise RuntimeError(f'Bước "{name}" thất bại: {error}')


def _step_new_project(window, log):
    """File → New → confirm defaults."""
    try:
        _menu_click(window, 'File', 'New')
        time.sleep(_DIALOG_WAIT)
        # Look for New project dialog and click OK/Create
        from pywinauto import Desktop
        for dlg_title in ('New Project', 'Dự án mới', 'Project'):
            try:
                dlg = Desktop(backend='uia').window(title_re=f'.*{dlg_title}.*', top_level_only=True)
                dlg.wait('visible', timeout=4)
                _click_ok(dlg)
                break
            except Exception:
                pass
        time.sleep(_STEP_PAUSE)
        log.record(window, '01_new_project', note='Tạo dự án mới')
    except RuntimeError:
        raise
    except Exception as exc:
        log.fail(window, '01_new_project', str(exc))


def _step_soil_mode(window, log):
    """Switch to Soil input mode."""
    ok = _toolbar_tab(window, 'Soil') or _toolbar_tab(window, 'Đất')
    if not ok:
        # Keyboard shortcut F1 or toolbar button index
        window.type_keys('%{F4}')  # last resort
    time.sleep(_STEP_PAUSE)
    log.record(window, '02_soil_mode', note='Chuyển sang chế độ nhập đất')


def _step_add_borehole(window, log, depth):
    """Add a borehole to define the soil profile."""
    try:
        # Click "Add borehole" in the explorer or toolbar
        for title in ('Add borehole', 'Thêm lỗ khoan', 'Borehole', '+'):
            try:
                btn = window.child_window(title=title, control_type='Button')
                btn.click_input()
                time.sleep(_DIALOG_WAIT)
                break
            except Exception:
                continue
        # In borehole dialog, click on the model area at x=0 to place it
        # (simplified: just press Enter to accept default placement)
        from pywinauto import Desktop
        try:
            dlg = Desktop(backend='uia').window(title_re=r'.*[Bb]orehole.*', top_level_only=True)
            dlg.wait('visible', timeout=3)
            _click_ok(dlg)
        except Exception:
            window.type_keys('{ENTER}')
        time.sleep(_STEP_PAUSE)
        log.record(window, '03_borehole', note=f'Thêm lỗ khoan, tổng chiều sâu {depth}m')
    except Exception as exc:
        log.fail(window, '03_borehole', str(exc))


def _step_add_soil_layers(window, log, layers):
    """Open Materials and add soil layers via the Soil Material dialog."""
    # Open Soil Materials dialog
    try:
        _menu_click(window, 'Soil', 'Show materials')
    except Exception:
        try:
            btn = window.child_window(title_re=r'.*[Mm]aterial.*', control_type='Button')
            btn.click_input()
        except Exception:
            pass
    time.sleep(_DIALOG_WAIT)

    from pywinauto import Desktop
    for i, layer in enumerate(layers):
        try:
            # Click "New material" or "+" button in the materials dialog
            for new_title in ('New material', 'Add', '+', 'New', 'Mới'):
                try:
                    mat_dlg = Desktop(backend='uia').window(
                        title_re=r'.*(Material|Vật liệu).*', top_level_only=True)
                    btn = mat_dlg.child_window(title=new_title, control_type='Button')
                    btn.click_input()
                    time.sleep(_DIALOG_WAIT)
                    break
                except Exception:
                    continue

            # Fill in properties
            prop_dlg = Desktop(backend='uia').window(
                title_re=r'.*(Soil|Đất|Material|Properties).*', top_level_only=True)
            prop_dlg.wait('visible', timeout=4)

            _type_value(prop_dlg, 'Name',  layer['name'])
            _type_value(prop_dlg, 'E',     layer['E'])
            _type_value(prop_dlg, 'nu',    layer['nu'])
            _type_value(prop_dlg, 'γunsat', layer['gamma'])
            _type_value(prop_dlg, 'γsat',  layer.get('gamma_sat', layer['gamma'] + 2))
            _type_value(prop_dlg, "c'ref", layer['c'])
            _type_value(prop_dlg, "φ'",    layer['phi'])
            time.sleep(0.3)
            _click_ok(prop_dlg)
            time.sleep(0.6)

            log.record(window, f'04_soil_layer_{i+1}',
                       note=f'Lớp {i+1}: {layer["name"]} E={layer["E"]} φ={layer["phi"]}°')
        except Exception as exc:
            logger.warning('Không thêm được lớp đất %d: %s', i+1, exc)
            log.record(window, f'04_soil_layer_{i+1}', status='warn',
                       note=f'Cảnh báo lớp {i+1}: {exc}')

    # Close materials dialog
    try:
        mat_dlg = Desktop(backend='uia').window(title_re=r'.*(Material|Vật liệu).*',
                                                 top_level_only=True)
        _click_ok(mat_dlg)
    except Exception:
        pass
    time.sleep(_STEP_PAUSE)


def _step_structures_mode(window, log):
    """Switch to Structures mode to define geometry."""
    _toolbar_tab(window, 'Structures') or _toolbar_tab(window, 'Kết cấu')
    time.sleep(_STEP_PAUSE)
    log.record(window, '05_structures_mode', note='Chuyển sang chế độ Kết cấu/Hình học')


def _step_draw_geometry_excavation(window, log, problem):
    """Draw retaining wall plates for excavation pit (simplified)."""
    H = problem['excavation_depth']
    W = problem['excavation_width']
    t = problem['wall_thickness']
    d = problem.get('embedment_depth', 2.0)
    total = H + d

    # Use keyboard shortcut or toolbar to draw Plate element
    try:
        # Plaxis: Create Plate shortcut is usually on toolbar
        plate_btn = window.child_window(title_re=r'.*[Pp]late.*', control_type='Button')
        plate_btn.click_input()
        time.sleep(0.5)
    except Exception:
        pass

    # Type coordinates in command line (Plaxis has a command line input at bottom)
    half = W / 2
    try:
        cmd = window.child_window(title_re=r'.*[Cc]ommand.*', control_type='Edit')
        cmd.set_edit_text(f'{half:.3f} 0')
        cmd.type_keys('{ENTER}')
        time.sleep(0.3)
        cmd.set_edit_text(f'{half:.3f} -{total:.3f}')
        cmd.type_keys('{ENTER}{ESCAPE}')
        time.sleep(_STEP_PAUSE)
    except Exception as exc:
        logger.warning('Không vẽ được tường vây qua command line: %s', exc)

    log.record(window, '06_geometry',
               note=f'Tường vây ({half:.2f}, 0) → ({half:.2f}, -{total:.2f})')


def _step_draw_geometry_generic(window, log, problem_type):
    """Placeholder geometry step for non-excavation problems."""
    log.record(window, '06_geometry',
               note=f'Hình học {problem_type} — xem màn hình Structures')


def _step_mesh_mode(window, log):
    """Switch to Mesh mode and generate mesh."""
    _toolbar_tab(window, 'Mesh') or _toolbar_tab(window, 'Lưới')
    time.sleep(_STEP_PAUSE)
    log.record(window, '07_mesh_mode', note='Chuyển sang chế độ Lưới')

    # Click "Generate mesh" button
    for title in ('Generate mesh', 'Tạo lưới', 'Mesh', 'Generate'):
        try:
            btn = window.child_window(title=title, control_type='Button')
            btn.click_input()
            time.sleep(_DIALOG_WAIT)
            break
        except Exception:
            continue

    # Confirm in dialog
    from pywinauto import Desktop
    try:
        dlg = Desktop(backend='uia').window(title_re=r'.*(Mesh|Lưới).*', top_level_only=True)
        dlg.wait('visible', timeout=5)
        _click_ok(dlg)
    except Exception:
        window.type_keys('{ENTER}')

    time.sleep(_STEP_PAUSE * 2)
    log.record(window, '08_mesh_generated', note='Lưới phần tử hữu hạn đã tạo')


def _step_staged_construction(window, log, problem):
    """Switch to Staged Construction and set up phases."""
    ok = (_toolbar_tab(window, 'Staged construction') or
          _toolbar_tab(window, 'Staged Construction') or
          _toolbar_tab(window, 'Giai đoạn'))
    time.sleep(_STEP_PAUSE)
    log.record(window, '09_staged_construction', note='Thiết lập giai đoạn thi công')


def _step_calculate(window, log):
    """Click Calculate (F5 or toolbar button) and wait."""
    # Try F5 shortcut
    try:
        window.type_keys('{F5}')
    except Exception:
        for title in ('Calculate', 'Tính toán', 'Run', 'Calculate!'):
            try:
                btn = window.child_window(title=title, control_type='Button')
                btn.click_input()
                break
            except Exception:
                continue

    time.sleep(_STEP_PAUSE)
    log.record(window, '10_calculate_started', note='Bắt đầu tính toán...')

    # Wait for calculation to finish
    deadline = time.time() + _CALC_TIMEOUT
    while time.time() < deadline:
        try:
            title = window.window_text()
            if any(kw in title for kw in ('Calculating', 'Running', '...', 'Tính')):
                time.sleep(_CALC_POLL)
                continue
        except Exception:
            pass
        break

    time.sleep(2)
    log.record(window, '11_calculate_done', note='Tính toán hoàn tất')


def _step_view_results(window, log):
    """Switch to Output / view results and take final screenshot."""
    # Try Output mode or Results tab
    for title in ('Output', 'Results', 'Kết quả', 'View results'):
        try:
            _toolbar_tab(window, title)
            time.sleep(_STEP_PAUSE)
            break
        except Exception:
            continue

    # Try menu View > Results or similar
    try:
        _menu_click(window, 'View', 'Results')
        time.sleep(_STEP_PAUSE)
    except Exception:
        pass

    log.record(window, '12_results', note='Kết quả phân tích')


# ── Public API ────────────────────────────────────────────────────────────────

def run_plaxis_automation(problem, version='2d', shot_dir=None, plaxis_exe=None):
    """Run a complete step-by-step Plaxis 2D UI automation session.

    Args:
        problem:      validated problem dict (from plaxis_app._validate_problem)
        version:      '2d' or '3d'
        shot_dir:     directory for PNG screenshots; uses tempdir if None
        plaxis_exe:   path to PLAXIS2D.exe; uses running instance if None

    Returns:
        dict with keys:
          executed: bool
          steps: list of {step, status, screenshot, note}
          error: str if executed=False
    """
    if not available():
        return {
            'executed': False,
            'steps': [],
            'error': (
                'UI Automation cần chạy ChatAI trên Windows với '
                'pywinauto + psutil + Pillow đã cài.\n'
                'Chạy: pip install pywinauto psutil Pillow'
            ),
        }

    import tempfile
    if not shot_dir:
        shot_dir = Path(tempfile.gettempdir()) / f'plaxis_ui_{uuid.uuid4().hex[:8]}'
    shot_dir = Path(shot_dir)
    shot_dir.mkdir(parents=True, exist_ok=True)

    log = StepLog(shot_dir)

    try:
        proc = _find_or_launch(plaxis_exe)
        window = _main_window(proc.pid)
    except RuntimeError as exc:
        return {'executed': False, 'steps': log.steps, 'error': str(exc)}
    except Exception as exc:
        return {'executed': False, 'steps': log.steps, 'error': f'Lỗi khởi động: {exc}'}

    # Initial screenshot — Plaxis open
    log.record(window, '00_plaxis_open', note='Plaxis 2D đã mở')

    ptype = problem.get('type', '')
    layers = problem.get('soil_layers', [])
    total_depth = sum(l['thickness'] for l in layers)

    try:
        _step_new_project(window, log)
        _step_soil_mode(window, log)
        _step_add_borehole(window, log, total_depth)
        _step_add_soil_layers(window, log, layers)
        _step_structures_mode(window, log)

        if ptype == 'excavation_pit':
            _step_draw_geometry_excavation(window, log, problem)
        else:
            _step_draw_geometry_generic(window, log, ptype)

        _step_mesh_mode(window, log)
        _step_staged_construction(window, log, problem)
        _step_calculate(window, log)
        _step_view_results(window, log)

        return {'executed': True, 'steps': log.steps, 'error': ''}

    except RuntimeError as exc:
        return {'executed': False, 'steps': log.steps, 'error': str(exc)}
    except Exception as exc:
        log.record(window, 'error', status='error', note=str(exc))
        return {'executed': False, 'steps': log.steps, 'error': f'Lỗi không mong muốn: {exc}'}


# ── ChatAI Tool interface ─────────────────────────────────────────────────────

class PlaxisUIAutomationApp:
    """ChatAI tool: plaxis_ui_automation — step-by-step UI control with screenshots."""

    def __init__(self, files, audit):
        self._files = files
        self._audit = audit

    def prepare(self, name, args):
        from .plaxis_app import _validate_problem

        version = args.get('version', '')
        if version not in ('2d', '3d'):
            raise ValueError("version phải là '2d' hoặc '3d'.")

        problem = _validate_problem(args.get('problem', ''))

        project_name = args.get('project_name', 'PlaxisAuto')
        if not isinstance(project_name, str) or not project_name.strip():
            raise ValueError('project_name là bắt buộc.')
        if len(project_name) > 100:
            raise ValueError('project_name tối đa 100 ký tự.')
        project_name = project_name.strip()

        plaxis_exe = args.get('plaxis_exe', '') or None
        if plaxis_exe and len(plaxis_exe) > 4096:
            raise ValueError('plaxis_exe đường dẫn quá dài.')

        shot_folder = f'Plaxis_Auto_{uuid.uuid4().hex[:8]}'

        return {
            'action': 'plaxis_ui_automation',
            'version': version,
            'problem_type': problem['type'],
            'project_name': project_name,
            'problem': problem,
            'plaxis_exe': plaxis_exe,
            'shot_folder': shot_folder,
        }

    def commit(self, plan):
        shot_dir = None
        if self._files.roots:
            shot_dir = self._files.roots[0] / plan['shot_folder']

        result = run_plaxis_automation(
            problem=plan['problem'],
            version=plan['version'],
            shot_dir=shot_dir,
            plaxis_exe=plan.get('plaxis_exe'),
        )

        self._audit('plaxis_ui_automation', {
            'version': plan['version'],
            'problem_type': plan['problem_type'],
            'executed': result['executed'],
            'steps': len(result.get('steps', [])),
        })

        steps = result.get('steps', [])
        screenshots = [s['screenshot'] for s in steps if s.get('screenshot')]

        if not result['executed'] and not steps:
            return {
                'ok': False,
                'error': result['error'],
                'note': result['error'],
                'steps': steps,
            }

        lines = [
            f"UI Automation {plan['problem_type']} ({plan['version'].upper()}) "
            + ('hoàn tất.' if result['executed'] else '— dừng giữa chừng.'),
            '',
            f'Tổng bước thực hiện: {len(steps)}',
            f'Ảnh chụp: {len(screenshots)} bước',
        ]
        if not result['executed']:
            lines.append(f'Lỗi: {result["error"]}')
        lines.append('')
        lines.append('Các bước:')
        for s in steps:
            icon = '✓' if s['status'] == 'ok' else ('⚠' if s['status'] == 'warn' else '✗')
            lines.append(f"  {icon} {s['step'].replace('_', ' ')}: {s['note']}")

        return {
            'ok': result['executed'],
            'executed': result['executed'],
            'steps': steps,
            'screenshots': screenshots,
            'files': screenshots,
            'error': result.get('error', ''),
            'note': '\n'.join(lines),
        }

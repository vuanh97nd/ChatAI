"""Plaxis 2D UI Control — fallback when Remote Scripting Server is unavailable.

Uses Windows UI Automation (pywinauto) to:
  1. Locate or launch Plaxis 2D
  2. Run a generated .py script via File → Run Script menu
  3. Capture a screenshot of the results viewport

This is automatically used by plaxis_run_problem when port 10000 is unreachable
and the caller provides a plaxis_exe path or Plaxis is already running.

Windows-only. Requires: pywinauto, psutil, Pillow (pip install plxscripting is NOT
required for this path).
"""
import logging
import os
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_PLAXIS_PROC_NAMES = ('PLAXIS2D.exe', 'Plaxis2D.exe', 'plaxis2d.exe', 'PLAXISINPUT.exe')
_MENU_WAIT = 2.5   # seconds to wait for menu/dialog to appear
_CALC_POLL = 3.0   # seconds between progress checks
_CALC_TIMEOUT = 300  # max seconds to wait for calculation


def available():
    """True when running on Windows with pywinauto + psutil installed."""
    if os.name != 'nt':
        return False
    try:
        import importlib.util
        return all(importlib.util.find_spec(n) for n in ('pywinauto', 'psutil'))
    except Exception:
        return False


# ── Process helpers ───────────────────────────────────────────────────────────

def _find_plaxis_process():
    """Return psutil.Process for a running Plaxis 2D instance, or None."""
    try:
        import psutil
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                name = proc.info.get('name', '') or ''
                if any(name.lower() == p.lower() for p in _PLAXIS_PROC_NAMES):
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as exc:
        logger.debug('Error scanning processes: %s', exc)
    return None


def _launch_plaxis(exe_path):
    """Launch Plaxis 2D and return psutil.Process. Raises RuntimeError on failure."""
    try:
        import psutil
        proc = subprocess.Popen([str(exe_path)], cwd=str(Path(exe_path).parent), shell=False)
        ps = psutil.Process(proc.pid)
        # Wait up to 30s for Plaxis window to appear
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                wins = ps.num_handles()  # proxy for "process is alive"
                break
            except Exception:
                time.sleep(1)
        time.sleep(5)  # extra settle time for Plaxis to initialise
        return ps
    except Exception as exc:
        raise RuntimeError(f'Không thể khởi động Plaxis: {exc}') from exc


def _get_main_window(pid):
    """Return the first top-level window for the given PID using pywinauto."""
    from pywinauto import Desktop
    wins = Desktop(backend='uia').windows(process=pid)
    if not wins:
        raise RuntimeError('Không tìm thấy cửa sổ Plaxis.')
    # Prefer the window with the largest area (main window vs splash)
    return max(wins, key=lambda w: _win_area(w))


def _win_area(win):
    try:
        r = win.rectangle()
        return (r.right - r.left) * (r.bottom - r.top)
    except Exception:
        return 0


# ── Script execution via File > Run Script ────────────────────────────────────

def _run_script_via_menu(window, script_path):
    """Trigger File → Run Script, navigate to script_path, confirm."""
    # Click the File menu
    try:
        file_menu = window.child_window(title='File', control_type='MenuItem')
        file_menu.click_input()
        time.sleep(_MENU_WAIT)
    except Exception as exc:
        raise RuntimeError(f'Không tìm thấy menu File: {exc}') from exc

    # Click Run Script item
    try:
        run_item = window.child_window(title_re=r'Run Script.*', control_type='MenuItem')
        run_item.click_input()
        time.sleep(_MENU_WAIT)
    except Exception as exc:
        # Fallback: try "Script" submenu
        try:
            script_menu = window.child_window(title_re=r'Script.*', control_type='MenuItem')
            script_menu.click_input()
            time.sleep(0.5)
            run_item = window.child_window(title_re=r'Run.*', control_type='MenuItem')
            run_item.click_input()
            time.sleep(_MENU_WAIT)
        except Exception as exc2:
            raise RuntimeError(
                f'Không tìm thấy mục Run Script trong menu File: {exc} / {exc2}'
            ) from exc2

    # File open dialog — type path and confirm
    from pywinauto import Desktop
    try:
        dlg = Desktop(backend='uia').window(title_re=r'.*(Open|Browse|Script).*', top_level_only=True)
        dlg.wait('visible', timeout=5)
    except Exception as exc:
        raise RuntimeError(f'Hộp thoại mở file không xuất hiện: {exc}') from exc

    try:
        # Find filename edit field and type the path
        edit = dlg.child_window(control_type='Edit')
        edit.set_text(str(script_path))
        time.sleep(0.3)
        # Click Open/OK button
        for btn_title in ('Open', 'Mở', 'OK', '&Open', '&OK'):
            try:
                btn = dlg.child_window(title=btn_title, control_type='Button')
                btn.click_input()
                return
            except Exception:
                continue
        # Last resort: press Enter
        edit.type_keys('{ENTER}')
    except Exception as exc:
        raise RuntimeError(f'Lỗi nhập đường dẫn script: {exc}') from exc


def _wait_for_calculation(window, timeout=_CALC_TIMEOUT):
    """Poll Plaxis window title for calculation-in-progress indicator."""
    deadline = time.time() + timeout
    calculating = False
    while time.time() < deadline:
        try:
            title = window.window_text()
            if any(kw in title for kw in ('Calculating', 'Running', 'Tính toán', '...')):
                calculating = True
                time.sleep(_CALC_POLL)
                continue
            if calculating:
                # Was calculating, now done
                break
        except Exception:
            break
        time.sleep(_CALC_POLL)
    # Extra settle time after calculation
    time.sleep(2)


# ── Screenshot ────────────────────────────────────────────────────────────────

def _take_screenshot(window, output_path):
    """Capture the Plaxis window to output_path (PNG). Returns path."""
    try:
        from PIL import ImageGrab
        rect = window.rectangle()
        img = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom))
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(out), 'PNG')
        return str(out)
    except Exception as exc:
        raise RuntimeError(f'Không chụp được màn hình Plaxis: {exc}') from exc


# ── Public API ────────────────────────────────────────────────────────────────

def run_via_ui(script_text, script_dir, screenshot_path, plaxis_exe=None):
    """Write script_text to a temp file, run it via Plaxis UI, capture screenshot.

    Args:
        script_text:     Python script content (str)
        script_dir:      Directory to write the temp script file (Path or str)
        screenshot_path: Where to save the PNG screenshot (Path or str)
        plaxis_exe:      Path to PLAXIS2D.exe; pass None to use a running instance

    Returns:
        dict with keys: executed (bool), screenshot (str|None), error (str),
        mode ('ui_control'), note (str)
    """
    if not available():
        return {
            'executed': False,
            'screenshot': None,
            'mode': 'ui_control',
            'error': (
                'UI Control cần chạy ChatAI trên Windows với pywinauto + psutil đã cài.\n'
                'Chạy: pip install pywinauto psutil'
            ),
        }

    # Write script to a file
    script_path = Path(script_dir) / f'plaxis_ui_{int(time.time())}.py'
    try:
        script_path.write_text(script_text, encoding='utf-8')
    except Exception as exc:
        return {'executed': False, 'screenshot': None, 'mode': 'ui_control',
                'error': f'Không ghi được file script tạm: {exc}'}

    try:
        # Find or launch Plaxis
        proc = _find_plaxis_process()
        if proc is None:
            if not plaxis_exe:
                return {
                    'executed': False, 'screenshot': None, 'mode': 'ui_control',
                    'error': (
                        'Plaxis 2D chưa chạy và không có đường dẫn plaxis_exe.\n'
                        'Hãy mở Plaxis trước, hoặc cung cấp plaxis_exe trong tham số.'
                    ),
                }
            proc = _launch_plaxis(plaxis_exe)

        window = _get_main_window(proc.pid)
        _run_script_via_menu(window, script_path)
        _wait_for_calculation(window)
        shot = _take_screenshot(window, screenshot_path)

        return {
            'executed': True,
            'screenshot': shot,
            'mode': 'ui_control',
            'error': '',
            'note': f'Script chạy qua UI Control. Kết quả: ảnh chụp màn hình tại {shot}',
        }

    except RuntimeError as exc:
        return {'executed': False, 'screenshot': None, 'mode': 'ui_control',
                'error': str(exc)}
    except Exception as exc:
        return {'executed': False, 'screenshot': None, 'mode': 'ui_control',
                'error': f'Lỗi UI Control: {exc}'}
    finally:
        # Clean up temp script (best-effort)
        try:
            script_path.unlink(missing_ok=True)
        except Exception:
            pass


# ── ChatAI Tool interface ─────────────────────────────────────────────────────

class PlaxisUIControlApp:
    """ChatAI tool: run a Plaxis script via Windows UI automation (File > Run Script).

    This is a standalone tool (plaxis_ui_run) that can also be invoked by
    PlaxisRemoteApp as a fallback when the Remote Scripting Server is not running.
    """

    def __init__(self, plaxis_app, files, audit):
        self._app = plaxis_app      # PlaxisApp for script generation
        self._files = files
        self._audit = audit

    def prepare(self, name, args):
        from .plaxis_app import _validate_problem, _generate_script, _PORT

        version = args.get('version', '')
        if version not in ('2d', '3d'):
            raise ValueError("version phải là '2d' hoặc '3d'.")

        problem = _validate_problem(args.get('problem', ''))
        port = _PORT[version]

        project_name = args.get('project_name', 'PlaxisUI')
        if not isinstance(project_name, str) or not project_name.strip():
            raise ValueError('project_name là bắt buộc.')
        if len(project_name) > 100:
            raise ValueError('project_name tối đa 100 ký tự.')
        project_name = project_name.strip()

        plaxis_exe = args.get('plaxis_exe', '')
        if plaxis_exe and not isinstance(plaxis_exe, str):
            raise ValueError('plaxis_exe phải là đường dẫn EXE (chuỗi).')
        if plaxis_exe and len(plaxis_exe) > 4096:
            raise ValueError('plaxis_exe đường dẫn quá dài.')

        script = _generate_script(problem, version, port, project_name)

        import uuid as _uuid
        shot_name = f'Plaxis_UI_{_uuid.uuid4().hex[:8]}.png'

        return {
            'action': 'plaxis_ui_run',
            'version': version,
            'problem_type': problem['type'],
            'project_name': project_name,
            'plaxis_exe': plaxis_exe or None,
            'script': script,
            'screenshot_name': shot_name,
        }

    def commit(self, plan):
        if not self._files.roots:
            raise PermissionError('Thêm thư mục được phép trong Cài đặt để lưu ảnh kết quả.')

        script_dir = self._files.roots[0]
        screenshot_path = script_dir / plan['screenshot_name']

        result = run_via_ui(
            script_text=plan['script'],
            script_dir=script_dir,
            screenshot_path=screenshot_path,
            plaxis_exe=plan.get('plaxis_exe'),
        )

        self._audit('plaxis_ui_run', {
            'version': plan['version'],
            'problem_type': plan['problem_type'],
            'executed': result['executed'],
        })

        if not result['executed']:
            return {'ok': False, 'error': result['error'], 'note': result['error']}

        return {
            'ok': True,
            'executed': True,
            'mode': 'ui_control',
            'screenshot': result['screenshot'],
            'files': [result['screenshot']] if result.get('screenshot') else [],
            'note': result.get('note', ''),
        }

"""Bộ cài/launcher Windows. Mở run.bat; --install-only để chỉ cài nền."""
import json
import os
import struct
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / '.venv'
VENV_PYTHON = VENV_DIR / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
PROBE = ('import json,sys,struct; print(json.dumps({'
         '"version":list(sys.version_info[:2]),"bits":struct.calcsize("P")*8,'
         '"prefix":sys.prefix,"base_prefix":sys.base_prefix}))')
IMPORT_CHECK = ('from PySide6.QtCore import QTimer; from PySide6.QtGui import QTextDocument; '
                'from PySide6.QtWidgets import QApplication; import importlib.util; assert all(importlib.util.find_spec(n) for n in ("ollama","pandas","openpyxl"))')


def child_env():
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8')
    # Không cho PYTHONHOME/PYTHONPATH của Python khác làm hỏng venv.
    env.pop('PYTHONHOME', None)
    env.pop('PYTHONPATH', None)
    return env


def confirm(message):
    if sys.stdin is not None and sys.stdin.isatty():
        try:
            return input(message + ' [Y/N]: ').strip().lower() in {'y', 'yes', 'c', 'co', 'có'}
        except EOFError:
            return False
    try:
        import tkinter as tk
        from tkinter import messagebox
        window = tk.Tk(); window.withdraw()
        try: return messagebox.askyesno('Chat AI', message, parent=window)
        finally: window.destroy()
    except Exception:
        return False


def show_error(message):
    print('\n' + message, flush=True)
    if sys.stdin is None or not sys.stdin.isatty():
        try:
            import tkinter as tk
            from tkinter import messagebox
            window = tk.Tk(); window.withdraw()
            try: messagebox.showerror('Chat AI', message, parent=window)
            finally: window.destroy()
        except Exception: pass


def python_info(command):
    try:
        result = subprocess.run([*command, '-c', PROBE], capture_output=True,
                                text=True, encoding='utf-8', errors='replace',
                                timeout=20, env=child_env())
        if result.returncode == 0: return json.loads(result.stdout.strip())
    except (OSError, subprocess.TimeoutExpired, ValueError): pass
    return None


def compatible(info):
    return bool(info and (3, 11) <= tuple(info['version']) <= (3, 12) and info['bits'] == 64)


def base_python():
    candidates = []
    if os.name == 'nt': candidates += [['py', '-3.12'], ['py', '-3.11']]
    candidates += [[getattr(sys, '_base_executable', sys.executable)], ['python']]
    for command in candidates:
        info = python_info(command)
        if compatible(info) and info['prefix'] == info['base_prefix']: return command
    raise RuntimeError('Không tìm thấy Python 3.11/3.12 64-bit hoạt động. '
                       'Hãy cài Python 3.12 64-bit kèm Python Launcher, rồi mở run.bat lại. '
                       'Bản này chưa hỗ trợ môi trường Python 3.14.')


def run_logged(args, path):
    """Hiện stdout/stderr trực tiếp và lưu log, không giấu tiến trình pip."""
    with path.open('a', encoding='utf-8') as log:
        log.write('\n=== ' + datetime.now().isoformat() + ' ===\n')
        log.flush()
        child = subprocess.Popen(args, cwd=ROOT, env=child_env(), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
            bufsize=1, shell=False)
        try:
            for line in child.stdout:
                print(line, end='', flush=True); log.write(line); log.flush()
            code = child.wait(); log.write(f'\nExit code: {code}\n'); return code
        except BaseException:
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=10)
                except subprocess.TimeoutExpired: child.kill(); child.wait()
            raise


def check_imports():
    try:
        result = subprocess.run([str(VENV_PYTHON), '-c', IMPORT_CHECK], capture_output=True,
            text=True, encoding='utf-8', errors='replace', timeout=60, env=child_env())
        return result.returncode == 0, result.stderr or result.stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)


def error_tail(path):
    try:
        with path.open('rb') as inp:
            inp.seek(max(0, path.stat().st_size - 5000))
            text = inp.read().decode('utf-8', errors='replace')
        lines = text.splitlines()
        return '\n'.join(lines[-18:])
    except OSError: return ''


def install():
    info = python_info([str(VENV_PYTHON)]) if VENV_PYTHON.is_file() else None
    environment_ok = compatible(info) and info['prefix'] != info['base_prefix']
    ready, reason = check_imports() if environment_ok else (False, 'Môi trường .venv thiếu, hỏng hoặc sai phiên bản.')
    if ready:
        print('Thư viện desktop đã sẵn sàng.', flush=True); return True
    print('Cần cài/sửa nền desktop: ' + reason[-1500:], flush=True)
    installer_python = base_python() if not environment_ok else None
    message = 'Bạn có muốn tải/cài thư viện desktop từ PyPI? Cần Internet.'
    if not environment_ok and VENV_DIR.exists():
        message += ' Môi trường .venv cũ sẽ được đổi tên để giữ lại và tạo môi trường mới. Lịch sử/tài liệu được giữ nguyên.'
    if not confirm(message):
        print('Đã hủy cài đặt.'); return False
    log = ROOT / 'data/install-base.log'
    if not environment_ok:
        if VENV_DIR.exists():
            backup = ROOT / ('.venv-old-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
            VENV_DIR.rename(backup); print('Đã giữ môi trường cũ tại:', backup)
        print('Đang tạo môi trường Python…', flush=True)
        if run_logged([*installer_python, '-m', 'venv', str(VENV_DIR)], log):
            raise RuntimeError('Không tạo được .venv.\n' + error_tail(log) + '\nLog: ' + str(log))
    # Phục hồi pip bị thiếu; chỉ chạy sau xác nhận cài đặt.
    probe = subprocess.run([str(VENV_PYTHON), '-m', 'pip', '--version'], capture_output=True,
                            timeout=30, env=child_env())
    if probe.returncode and run_logged([str(VENV_PYTHON), '-m', 'ensurepip', '--upgrade'], log):
        raise RuntimeError('Không khôi phục được pip.\n' + error_tail(log))
    print('Đang tải thư viện. Giữ cửa sổ này mở; tiến trình xuất hiện bên dưới.', flush=True)
    args = [str(VENV_PYTHON), '-m', 'pip', 'install', '--disable-pip-version-check',
            '--only-binary=:all:', '--index-url', 'https://pypi.org/simple',
            '--timeout', '60', '--retries', '3', '-r', str(ROOT / 'requirements.txt')]
    if run_logged(args, log):
        raise RuntimeError('Cài thư viện thất bại.\n' + error_tail(log) + '\nGửi file: ' + str(log))
    ready, reason = check_imports()
    if not ready:
        with log.open('a', encoding='utf-8') as output: output.write(reason)
        raise RuntimeError('Pip đã chạy nhưng chưa nạp được giao diện Qt/thư viện.\n' + reason[-2500:] + '\nLog: ' + str(log))
    print('Cài đặt desktop hoàn tất.', flush=True); return True


def main():
    os.chdir(ROOT); (ROOT / 'data').mkdir(exist_ok=True)
    startup = ROOT / 'data/startup.log'
    with startup.open('a', encoding='utf-8') as log:
        log.write(f'\n=== {datetime.now().isoformat()} ===\nPython: {sys.version}\nExecutable: {sys.executable}\nFolder: {ROOT}\n')
    needed = ['app.py', 'desktop_ui.py', 'requirements.txt', 'assistant/office.py']
    missing = [name for name in needed if not (ROOT / name).is_file()]
    if missing: raise RuntimeError('Thiếu file: ' + ', '.join(missing) + '. Đợi Drive đồng bộ đầy đủ thư mục Chat-AI.')
    if not install(): return 2
    if '--install-only' in sys.argv: return 0
    print('Đang mở cửa sổ Chat AI trên Windows…', flush=True)
    print('Log khởi chạy:', startup, flush=True)
    code = run_logged([str(VENV_PYTHON), str(ROOT / 'app.py')], startup)
    if code: raise RuntimeError(f'Chat AI dừng với mã {code}.\n' + error_tail(startup) + '\nGửi file: ' + str(startup))
    return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except KeyboardInterrupt: print('\nĐã dừng.'); sys.exit(130)
    except Exception as error:
        try:
            (ROOT / 'data').mkdir(exist_ok=True)
            with (ROOT / 'data/startup.log').open('a', encoding='utf-8') as log: log.write(traceback.format_exc())
        except OSError: pass
        show_error(str(error)); sys.exit(1)

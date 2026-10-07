"""Opt-in installer: fixed packages only, in the app's isolated Python runtime."""
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
from .windows_apps import _STOP

PACKAGES={'pywinauto':'pywinauto>=0.6.9,<0.7','psutil':'psutil>=5.9,<8',
          'comtypes':'comtypes>=1.4,<2','playwright':'playwright>=1.50,<2','pypdf':'pypdf>=5,<7','docx':'python-docx>=1.1,<2','ezdxf':'ezdxf>=1.3,<2'}


def missing_modules():
    missing=[]
    for name in PACKAGES:
        try:
            # COM must be initialized later by WindowsBackend on the action thread.
            if name in {'pywinauto','comtypes','psutil'}:
                if importlib.util.find_spec(name) is None:raise ImportError(name)
            else:importlib.import_module(name+'.sync_api' if name=='playwright' else name)
        except (ImportError,OSError):missing.append(name)
    return missing


def ensure_dependencies(cfg,policy_path=None,on_status=None,audit=None):
    policy=lambda:json.loads(Path(policy_path).read_text(encoding='utf-8')) if policy_path else cfg
    if not policy().get('automation_auto_install'):return
    if not policy().get('windows_apps_enabled'):return
    import os
    if os.name!='nt':return
    missing=missing_modules()
    if not missing:return
    executable=Path(sys.executable)
    python=executable.with_name('python.exe') if executable.name.lower()=='pythonw.exe' else executable
    if sys.prefix==sys.base_prefix and not (python.parent/'chat-ai-runtime.json').is_file():
        raise RuntimeError('Không tự cài vào Python hệ thống. Chạy ChatAI trong .venv hoặc runtime đóng gói của app.')
    if not python.is_file():raise RuntimeError('Không tìm thấy Python của ChatAI để cài thư viện.')
    if _STOP.is_set():raise PermissionError('Đã dừng AI; chưa cài thư viện.')
    if on_status:on_status('Đang tự cài thư viện vào '+str(python)+': '+', '.join(missing))
    # Model cannot supply a package, command, index or URL. Never elevate or disable TLS verification.
    # CREATE_NO_WINDOW prevents a console flash from python.exe on Windows.
    launch_options={'creationflags':getattr(subprocess,'CREATE_NO_WINDOW',0x08000000)} if os.name=='nt' else {}
    process=subprocess.Popen([str(python),'-m','pip','install','--disable-pip-version-check',
                              *[PACKAGES[name] for name in missing]],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,shell=False,**launch_options)
    started=time.monotonic();last=started
    try:
        while process.poll() is None:
            now=time.monotonic()
            current=policy()
            if _STOP.is_set() or not current.get('automation_auto_install') or not current.get('windows_apps_enabled'):
                raise PermissionError('Đã dừng hoặc thu hồi quyền cài thư viện; hãy kiểm tra lại môi trường trước khi tiếp tục.')
            if now-started>240:raise TimeoutError('Cài thư viện quá 4 phút. Kiểm tra mạng rồi thử lại.')
            if on_status and now-last>=20:
                on_status('Đang cài thư viện · '+str(int(now-started))+' giây · '+', '.join(missing));last=now
            time.sleep(.25)
        if process.returncode:raise RuntimeError('Cài thư viện không thành công (mã '+str(process.returncode)+'). Kiểm tra mạng/pip của '+str(python)+'.')
    finally:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
    importlib.invalidate_caches()
    remaining=missing_modules()
    if audit:audit('automation_dependencies_install',{'packages':missing,'remaining':remaining,'python':str(python)})
    if remaining:raise RuntimeError('Đã cài nhưng chưa nạp được '+', '.join(remaining)+'. Khởi động lại ChatAI để nạp thư viện.')
    if on_status:on_status('Đã cài thư viện cần thiết; tiếp tục công việc.')

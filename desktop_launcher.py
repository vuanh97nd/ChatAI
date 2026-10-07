"""Khởi chạy Chat AI trong runtime đóng gói hoặc virtualenv riêng của ứng dụng."""
import hashlib
import os
import subprocess
import sys
import traceback
import time
from assistant.performance import measure,record
LAUNCHER_STARTED=time.monotonic()
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _bundled_runtime():
    runtime = (ROOT / "runtime" / "python").resolve()
    marker = runtime / "chat-ai-runtime.json"
    try:
        return marker.is_file() and Path(sys.executable).resolve().parent == runtime
    except OSError:
        return False


def _local_env_dir():
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local") if os.name == "nt" else str(Path.home() / ".local" / "share")
    key = hashlib.sha256(str(ROOT).casefold().encode("utf-8")).hexdigest()[:16]
    return Path(base) / "ChatAI" / "environments" / key


def _run_logged(args, log, timeout):
    log.write("\n> " + subprocess.list2cmdline([str(x) for x in args]) + "\n")
    log.flush()
    return subprocess.run(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                          check=False, timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)


def _prepare_local_environment():
    """Redirect a system-Python launch into a per-user venv; never pip-install globally."""
    if os.name != "nt" or sys.prefix != sys.base_prefix or _bundled_runtime():
        return None

    env_dir = _local_env_dir()
    py = env_dir / "Scripts" / "python.exe"
    pyw = env_dir / "Scripts" / "pythonw.exe"
    bootstrap_python = Path(sys.executable).with_name("python.exe")
    log_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "ChatAI" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "environment-bootstrap.log"
    with log_path.open("a", encoding="utf-8", buffering=1) as log:
        if not bootstrap_python.is_file():
            raise RuntimeError("Không tìm thấy python.exe cạnh Python đang chạy; không cài thư viện vào Python hệ thống.")

        healthy = False
        if py.is_file() and pyw.is_file():
            check = subprocess.run([str(py), "-c", "import PySide6.QtWidgets, ollama"], cwd=ROOT,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            healthy = check.returncode == 0

        if not healthy:
            env_dir.parent.mkdir(parents=True, exist_ok=True)
            if env_dir.exists():
                import shutil
                old = env_dir.with_name(env_dir.name + ".repair-" + str(os.getpid()))
                try:
                    env_dir.rename(old)
                except OSError:
                    shutil.rmtree(env_dir, ignore_errors=True)
            log.write("Tạo virtualenv riêng trong LocalAppData; không thay đổi Python hệ thống.\n")
            created = _run_logged([str(bootstrap_python), "-m", "venv", str(env_dir)], log, 600)
            if created.returncode:
                raise RuntimeError("Không tạo được virtualenv riêng. Xem log: " + str(log_path))
            requirements = ROOT / "requirements-bundled.txt"
            if requirements.is_file():
                install_args = [str(py), "-m", "pip", "install", "--disable-pip-version-check",
                                "--no-input", "--prefer-binary", "-r", str(requirements)]
            else:
                install_args = [str(py), "-m", "pip", "install", "--disable-pip-version-check",
                                "--no-input", "--prefer-binary", "PySide6-Essentials>=6.8,<7", "ollama>=0.6,<1"]
            installed = _run_logged(install_args, log, 2400)
            if installed.returncode:
                raise RuntimeError("Không cài được thư viện vào virtualenv riêng. Xem log: " + str(log_path))

        if not pyw.is_file():
            raise RuntimeError("Virtualenv đã tạo nhưng thiếu pythonw.exe: " + str(env_dir))
        log.write("Virtualenv sẵn sàng: " + str(env_dir) + "\n")
        log.flush()
        env = os.environ.copy()
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
        env["PYTHONUTF8"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        subprocess.Popen([str(pyw), str(ROOT / "desktop_launcher.py")], cwd=ROOT, env=env,
                         close_fds=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return 0


def ensure_qt(log):
    """Repair Qt only in an isolated venv or the app's bundled runtime."""
    try:
        import PySide6.QtWidgets  # noqa: F401
        return
    except ModuleNotFoundError as exc:
        if exc.name != "PySide6":
            raise

    if sys.prefix == sys.base_prefix and not _bundled_runtime():
        raise RuntimeError("Chat AI chặn cài thư viện vào Python hệ thống. Hãy mở lại bằng run.bat để tạo môi trường riêng.")
    python = Path(sys.executable).with_name("python.exe")
    if not python.is_file():
        raise RuntimeError("Không tìm thấy python.exe trong môi trường Chat AI.")
    log.write("Cài PySide6 vào môi trường riêng của Chat AI.\n")
    result = subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                             "--no-input", "--prefer-binary", "PySide6-Essentials>=6.8,<7"],
                            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False,
                            timeout=1200, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError("Không cài được PySide6 vào môi trường riêng. Xem data/startup.log.")
    import PySide6.QtWidgets  # noqa: F401


def main():
    os.chdir(ROOT)
    try:
        with measure('startup.launcher_environment'):redirected = _prepare_local_environment()
        if redirected is not None:
            return redirected
    except Exception as exc:
        if os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(exc), "Chat AI — Không tạo được môi trường riêng", 0x10)
        return 1

    with measure('startup.launcher_log'):
        (ROOT / 'data').mkdir(exist_ok=True)
        log = (ROOT / 'data' / 'startup.log').open('a',encoding='utf-8',buffering=1)
    sys.stdout = sys.stderr = log
    os.environ.pop("PYTHONHOME", None)
    os.environ.pop("PYTHONPATH", None)
    try:
        with measure('startup.launcher_qt_import'):ensure_qt(log)
        record('startup.launcher_before_app',time.monotonic()-LAUNCHER_STARTED)
        from app import main as start
        return start() or 0
    except Exception:
        detail = traceback.format_exc()
        log.write(detail)
        log.flush()
        if os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, "Không mở được Chat AI. Xem nhật ký:\n" +
                str(ROOT / "data" / "startup.log") + "\n\n" + detail[-1200:], "Chat AI", 16)
        return 1


if __name__ == "__main__":
    sys.exit(main())

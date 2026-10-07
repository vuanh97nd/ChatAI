"""Explicitly approved Windows UI Automation; no shell or global mouse/keyboard."""
from contextlib import contextmanager, nullcontext
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path

_STOP = threading.Event()
_PAUSED = threading.Event()
_SESSIONS = {}
_LOCK = threading.RLock()


def stop_automation():
    _STOP.set()
    _PAUSED.clear()


def resume_automation():
    _STOP.clear()
    _PAUSED.clear()


def pause_automation(paused=True):
    if paused:_PAUSED.set()
    else:_PAUSED.clear()

def wait_automation():
    while _PAUSED.is_set() and not _STOP.is_set():
        _STOP.wait(.1)

def available():
    return os.name == 'nt' and all(importlib.util.find_spec(name) is not None
                                 for name in ('pywinauto', 'psutil', 'comtypes'))


def readiness(cfg):
    """Report actual prerequisites, without importing COM or granting permission."""
    if os.name != 'nt':
        return 'Không thể điều khiển app: tính năng này cần chạy ChatAI trên Windows.'
    missing = [name for name in ('pywinauto', 'psutil', 'comtypes')
               if importlib.util.find_spec(name) is None]
    if missing:
        if cfg.get('automation_auto_install'):
            return 'Thiếu thư viện: '+', '.join(missing)+'. ChatAI sẽ tự cài vào Python đang chạy khi dùng công cụ, theo quyền đã lưu.'
        python=Path(sys.executable)
        if python.name.lower()=='pythonw.exe':python=python.with_name('python.exe')
        quoted=str(python).replace("'","''")
        return ('Thiếu thư viện: ' + ', '.join(missing) +
                ". Trong thư mục dự án chạy & '"+quoted+"' -m pip install "
                '-r requirements-windows-automation.txt rồi khởi động lại ChatAI.')
    if not cfg.get('windows_apps_enabled'):
        return 'Chưa bật quyền: vào Cài đặt → Điều khiển ứng dụng, bật quyền và Lưu.'
    if _STOP.is_set():
        return 'Điều khiển app đang dừng: bấm Tiếp tục điều khiển app trong Cài đặt.'
    if not cfg.get('windows_apps_allowed') and not cfg.get('windows_apps_all_installed'):
        return 'Chưa có app được phép: vào Cài đặt → Điều khiển ứng dụng → Thêm ứng dụng EXE, rồi Lưu.'
    browser_ready = importlib.util.find_spec('playwright') is not None
    browser_note = (' Chrome: đã có Playwright, hỗ trợ quy trình web sau khi duyệt.' if browser_ready else
                    ' Chrome tự động cần playwright: cài lại requirements-windows-automation.txt rồi khởi động lại.')
    return 'Sẵn sàng: có thể yêu cầu mở EXE được phép; thao tác UIA cần xác nhận.' + browser_note


def validate_settings(cfg):
    enabled = cfg.setdefault('windows_apps_enabled', False)
    background = cfg.setdefault('browser_background', False)
    auto_install=cfg.setdefault('automation_auto_install',False)
    compact=cfg.setdefault('windows_apps_compact',True)
    auto_execute=cfg.setdefault('windows_apps_auto_execute',False)
    all_installed=cfg.setdefault('windows_apps_all_installed',False)
    paths = cfg.setdefault('windows_apps_allowed', [])
    if any(type(v) is not bool for v in (enabled,background,auto_install,all_installed,auto_execute,compact)) or not isinstance(paths, list) or len(paths) > 30:
        raise ValueError('Quyền ứng dụng Windows không hợp lệ.')
    if any(not isinstance(p, str) or not p.strip() or len(p)>4096 or '\n' in p or '\x00' in p for p in paths):
        raise ValueError('Mỗi ứng dụng cần một đường dẫn EXE riêng.')
    from pathlib import PureWindowsPath
    if any(not PureWindowsPath(p).is_absolute() or PureWindowsPath(p).suffix.lower() != '.exe'
           or p.startswith(('\\\\', '//')) for p in paths):
        raise ValueError('Chỉ cho phép đường dẫn EXE tuyệt đối trên ổ đĩa Windows, không dùng UNC.')


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class WindowsBackend:
    @contextmanager
    def apartment(self):
        sys.coinit_flags = 0
        import comtypes
        comtypes.CoInitializeEx(0)  # UIA runs in worker threads; initialize COM for each task.
        try:
            yield
        finally:
            comtypes.CoUninitialize()

    def launch(self, path):
        # No model-supplied arguments, shell, scripts or elevation.
        process = subprocess.Popen([str(path)], cwd=str(path.parent), shell=False)
        import psutil
        return process.pid, psutil.Process(process.pid).create_time()

    def windows(self, session):
        import psutil
        from pywinauto import Desktop
        process = psutil.Process(session['pid'])
        if process.create_time() != session['started'] or Path(process.exe()).resolve() != session['path']:
            raise PermissionError('Tiến trình đã thay đổi; mở lại app bằng công cụ.')
        return Desktop(backend='uia').windows(process=session['pid'])

    def describe(self, control):
        info = control.element_info
        password = bool(info.element.CurrentIsPassword)
        # Names and editable text can contain passwords; redact password controls.
        return {'name': '' if password else str(info.name or '')[:300],
                'type': info.control_type, 'password': password,
                'identity': tuple(info.runtime_id), 'pid': info.process_id}

    def children(self, control):
        # Bound traversal instead of reading an unbounded desktop tree.
        return control.children()

    def action(self, control, operation, text):
        if operation == 'click':
            control.iface_invoke.Invoke()  # No mouse or keyboard fallback.
        elif operation == 'set_text':
            if control.iface_value.CurrentIsReadOnly:
                raise PermissionError('Ô văn bản chỉ đọc.')
            control.iface_value.SetValue(text)
        elif operation == 'close':
            control.iface_window.Close()  # pywinauto.close() can fall back to ESC; do not use it.
        else:
            raise ValueError('Thao tác không được hỗ trợ.')


class WindowsApps:
    def __init__(self, cfg, audit, owner='local', policy_path=None, backend=None):
        self.cfg, self.audit, self.owner = cfg, audit, owner
        self.policy_path = policy_path
        self.backend = backend or WindowsBackend()

    def check(self):
        wait_automation()
        if _STOP.is_set():
            raise PermissionError('Đã dừng điều khiển app. Bấm Tiếp tục trong Cài đặt để cho phép lại.')
        if self.policy_path:
            policy = json.loads(Path(self.policy_path).read_text(encoding='utf-8'))
        else:
            policy = self.cfg
        if not policy.get('windows_apps_enabled'):
            raise PermissionError('Chưa bật Điều khiển ứng dụng Windows.')
        if isinstance(self.backend, WindowsBackend) and not available():
            raise RuntimeError('Cần Windows và thư viện pywinauto. Xem WINDOWS_AUTOMATION.md.')
        return policy

    def allowed_path(self, raw):
        policy = self.check()
        path = Path(raw).resolve(strict=True)
        if not path.is_file() or path.suffix.lower() != '.exe':
            raise PermissionError('Ứng dụng phải là tệp EXE.')
        from .installed_apps import authorized_apps
        allowed = {Path(row['path']).resolve() for row in authorized_apps(policy)}
        if path not in allowed:
            raise PermissionError('Ứng dụng chưa có trong danh sách được phép.')
        return path

    def session(self, ident):
        self.check()
        session = _SESSIONS.get(ident)
        if not session or session['owner'] != self.owner:
            raise PermissionError('Phiên ứng dụng không thuộc tài khoản này hoặc đã hết hạn.')
        self.allowed_path(str(session['path']))
        if fingerprint(session['path']) != session['sha256']:
            raise PermissionError('Tệp EXE đã thay đổi; mở lại và xác nhận lại.')
        return session

    def prepare(self, name, args):
        self.check()
        if name=='windows_list_apps':
            return {'action':name,'query':args.get('query',''),
                    'notice':'Liệt kê tên và đường dẫn ứng dụng được phép; danh sách được đưa vào hội thoại AI.'}
        if name == 'windows_open':
            path = self.allowed_path(args['path'])
            return {'action': name, 'path': str(path), 'sha256': fingerprint(path),
                    'notice': 'Mở app thật trên Windows. Có thể hiện cửa sổ; không đảm bảo chạy ngầm.'}
        if name not in {'windows_inspect', 'windows_action'}:
            raise ValueError('Công cụ ứng dụng không hợp lệ.')
        with _LOCK:
            session = self.session(args['session'])
            if name == 'windows_inspect':
                return {'action': name, 'session': args['session'], 'path': str(session['path']),
                        'notice': 'Đọc nội dung giao diện app này; kết quả sẽ được đưa vào hội thoại AI.'}
            operation = args['operation']
            if operation not in {'click', 'set_text', 'close'}:
                raise ValueError('Chỉ hỗ trợ click, set_text hoặc close.')
            text = args.get('text', '')
            if not isinstance(text, str) or len(text) > 4000 or '\x00' in text:
                raise ValueError('Văn bản tối đa 4000 ký tự.')
            if operation != 'set_text' and text:
                raise ValueError('Chỉ set_text nhận văn bản.')
            token = args['control']
            item = session['controls'].get(token)
            if not item or item['description']['password']:
                raise PermissionError('Control chưa được đọc hoặc là ô mật khẩu.')
            if operation == 'set_text' and item['description']['type'] != 'Edit':
                raise PermissionError('Chỉ nhập vào ô Edit, không gửi phím toàn hệ thống.')
            if operation == 'close' and item['description']['type'] != 'Window':
                raise PermissionError('Chỉ đóng cửa sổ được chọn.')
            return {'action': name, 'session': args['session'], 'control': token,
                    'operation': operation, 'text': text, 'target': item['description']['name'],
                    'notice': 'Thao tác app có thể sửa dữ liệu/gửi biểu mẫu. Chỉ duyệt nếu đúng ý bạn; không có backup tự động cho app bên ngoài.'}

    def commit(self, plan):
        self.check()
        context = self.backend.apartment() if isinstance(self.backend, WindowsBackend) else nullcontext()
        with context:
            return self._commit(plan)

    def _commit(self, plan):
        self.check()
        action = plan['action']
        if action=='windows_list_apps':
            from .installed_apps import authorized_apps
            rows=authorized_apps(self.check());query=plan.get('query','').casefold().strip()
            from .installed_apps import matches_app
            matches=[row for row in rows if matches_app(row,query)]
            return {'ok':True,'apps':matches[:100],'truncated':len(matches)>100,
                    'note':'Chỉ mở đường dẫn được trả về. Tìm theo query nếu danh sách bị cắt. App không đăng ký với Windows hoặc portable cần thêm EXE thủ công.'}
        if action == 'windows_open':
            path = self.allowed_path(plan['path'])
            if fingerprint(path) != plan['sha256']:
                raise PermissionError('Tệp EXE đã đổi trong khi chờ duyệt.')
            self.check()
            pid, started = self.backend.launch(path)
            ident = uuid.uuid4().hex
            with _LOCK:
                _SESSIONS[ident] = {'owner': self.owner, 'path': path, 'sha256': plan['sha256'],
                                    'pid': pid, 'started': started, 'controls': {}}
            self.audit('windows_open', {'path': str(path), 'pid': pid})
            return {'ok': True, 'session': ident, 'pid': pid,
                    'note': 'Đã gửi lệnh mở; dùng windows_inspect để kiểm tra giao diện. App single-instance có thể chuyển sang tiến trình khác, khi đó chưa hỗ trợ.'}
        with _LOCK:
            session = self.session(plan['session'])
            windows = self.backend.windows(session)  # Revalidate PID and process identity.
            if action == 'windows_inspect':
                controls = {}; rows = []; queue = list(windows)[:10]
                visited = set()
                while queue and len(rows) < 60:
                    self.check()
                    control = queue.pop(0)
                    description = self.backend.describe(control)
                    identity = description['identity']
                    if identity in visited:
                        continue
                    visited.add(identity)
                    if description['password'] or description['pid'] != session['pid']:
                        continue
                    token = uuid.uuid4().hex
                    controls[token] = {'description': description}
                    rows.append({'control': token, 'name': description['name'], 'type': description['type']})
                    queue.extend(self.backend.children(control)[:60 - len(rows)])
                    queue = queue[:60]
                session['controls'] = controls
                self.audit('windows_inspect', {'pid': session['pid'], 'count': len(rows)})
                return {'ok': True, 'controls': rows, 'limited': bool(queue),
                        'note': 'Chỉ control UIA của tiến trình đã mở; không đọc toàn màn hình, không đọc ô mật khẩu.'}
            if action != 'windows_action':
                raise ValueError('Thao tác không hợp lệ.')
            # Re-run argument/policy checks after user approval.
            self.prepare(action, {k: plan[k] for k in ('session', 'control', 'operation', 'text')})
            item = session['controls'][plan['control']]
            # Resolve a fresh wrapper on this worker thread; never reuse COM objects across tasks.
            queue = list(windows)[:10]; seen = set(); target = None
            while queue and len(seen) < 60:
                self.check()
                control = queue.pop(0)
                current = self.backend.describe(control)
                identity = current['identity']
                if identity in seen:continue
                seen.add(identity)
                if current['password'] or current['pid'] != session['pid']:continue
                if identity == item['description']['identity']:
                    if current != item['description']:
                        raise PermissionError('Control đã thay đổi; đọc lại giao diện trước khi thao tác.')
                    target = control;break
                queue.extend(self.backend.children(control)[:60-len(seen)]);queue=queue[:60]
            if target is None:
                raise PermissionError('Control không còn thuộc giao diện app; đọc lại trước khi thao tác.')
            self.check()
            self.backend.action(target, plan['operation'], plan['text'])
            session['controls'] = {}  # Every next action requires a fresh inspected target.
            self.audit('windows_action', {'pid': session['pid'], 'operation': plan['operation']})
            return {'ok': True, 'note': 'Đã gửi thao tác UIA; đọc lại giao diện để xác minh kết quả.'}

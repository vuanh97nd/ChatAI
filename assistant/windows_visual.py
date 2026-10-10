"""Selected-window visual fallback. No desktop capture, shell or macro language."""
import base64
import io
import math
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

VISUAL_TOOLS = frozenset({'windows_list_windows', 'windows_attach', 'windows_capture', 'windows_input'})
# Opaque selections are account-bound and short lived, never model-invented HWNDs.
_SELECTIONS = {}
OBSERVATION_SECONDS = 120
KEYS = {'TAB': 9, 'ENTER': 13, 'ESC': 27, 'SPACE': 32, 'LEFT': 37,
        'UP': 38, 'RIGHT': 39, 'DOWN': 40, 'HOME': 36, 'END': 35,
        'PAGEUP': 33, 'PAGEDOWN': 34, 'BACKSPACE': 8, 'DELETE': 46,
        **{f'F{i}': 111+i for i in range(1, 13)}}
MODIFIERS = {'CTRL': 17, 'SHIFT': 16, 'ALT': 18}


def key_codes(key):
    if not isinstance(key, str):
        raise ValueError('Phím phải là chuỗi.')
    parts = key.upper().split('+')
    if len(parts) > 3 or len(set(parts)) != len(parts):
        raise ValueError('Chỉ gửi một phím hoặc một tổ hợp phím.')
    if any(p not in MODIFIERS for p in parts[:-1]):
        raise ValueError('Modifier chỉ hỗ trợ CTRL, SHIFT, ALT; không hỗ trợ WIN.')
    last = parts[-1]
    code = KEYS.get(last, ord(last) if len(last) == 1 and last.isascii() and last.isalnum() else None)
    if code is None or ('ALT' in parts and last in {'TAB', 'ESC', 'F4'}) or ('CTRL' in parts and last == 'ESC') or ('CTRL' in parts and 'ALT' in parts):
        raise ValueError('Phím này có thể chuyển cửa sổ hoặc hệ thống; không hỗ trợ.')
    return [MODIFIERS[p] for p in parts[:-1]] + [code]


@contextmanager
def physical_pixels():
    import ctypes
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    user.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    old = user.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    try:
        yield
    finally:
        if old:
            user.SetThreadDpiAwarenessContext(old)


class VisualBackend:
    def list_windows(self, path):
        import psutil
        from pywinauto import Desktop
        rows = []
        with physical_pixels():
            for window in Desktop(backend='win32').windows(visible_only=True):
                try:
                    process = psutil.Process(window.process_id())
                    if Path(process.exe()).resolve() != path:
                        continue
                    rows.append({'hwnd': window.handle, 'pid': process.pid,
                                 'started': process.create_time(), 'title': window.window_text()[:300]})
                except (psutil.Error, OSError):
                    continue
        return rows

    def geometry(self, session):
        import win32gui
        import win32process
        import psutil
        hwnd = session['hwnd']
        process = psutil.Process(session['pid'])
        if (process.create_time() != session['started'] or Path(process.exe()).resolve() != session['path'] or
                not win32gui.IsWindow(hwnd) or win32process.GetWindowThreadProcessId(hwnd)[1] != session['pid']):
            raise PermissionError('Cửa sổ hoặc tiến trình đã thay đổi; chọn lại cửa sổ.')
        if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd) or not win32gui.IsWindowEnabled(hwnd):
            raise PermissionError('Cửa sổ bị ẩn, thu nhỏ hoặc có hộp thoại chặn; chọn cửa sổ đang hoạt động.')
        with physical_pixels():
            rect = tuple(win32gui.GetWindowRect(hwnd))
        if rect[2] <= rect[0] or rect[3] <= rect[1]:
            raise PermissionError('Kích thước cửa sổ không hợp lệ.')
        return rect

    def focus(self, session):
        """Win32 focus works for custom canvases even when UIA has no element."""
        import ctypes
        from ctypes import wintypes
        import win32gui
        import win32process
        hwnd = session['hwnd']
        if win32gui.GetForegroundWindow() != hwnd:
            return None
        class GuiThreadInfo(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('flags', wintypes.DWORD),
                        ('hwndActive', wintypes.HWND), ('hwndFocus', wintypes.HWND),
                        ('hwndCapture', wintypes.HWND), ('hwndMenuOwner', wintypes.HWND),
                        ('hwndMoveSize', wintypes.HWND), ('hwndCaret', wintypes.HWND),
                        ('rcCaret', wintypes.RECT)]
        info = GuiThreadInfo(cbSize=ctypes.sizeof(GuiThreadInfo))
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GuiThreadInfo)]
        thread, _ = win32process.GetWindowThreadProcessId(hwnd)
        if not user.GetGUIThreadInfo(thread, ctypes.byref(info)) or not info.hwndFocus:
            return None
        target = int(info.hwndFocus)
        if win32gui.GetAncestor(target, 2) != hwnd or win32process.GetWindowThreadProcessId(target)[1] != session['pid']:
            return None
        kind = win32gui.GetClassName(target).lower()
        if ('edit' in kind and win32gui.GetWindowLong(target, -16) & 0x20):
            return None  # ES_PASSWORD, including native edit controls without UIA.
        try:
            from pywinauto.uia_defines import IUIA
            element = IUIA().iuia.GetFocusedElement()
            if element.CurrentIsPassword or element.CurrentProcessId != session['pid']:
                return None
            return (target, *tuple(element.GetRuntimeId()))
        except Exception:
            return (target,)  # UIA unsupported: bound Win32 focus, never global typing.

    def capture(self, session):
        # PrintWindow renders only the selected HWND, never pixels from other apps.
        import ctypes
        import win32gui
        import win32ui
        from PIL import Image
        rect = self.geometry(session)
        width, height = rect[2]-rect[0], rect[3]-rect[1]
        if width > 8192 or height > 8192 or width * height > 20000000:
            raise ValueError('Cửa sổ quá lớn; giảm kích thước rồi chụp lại.')
        hwnd = session['hwnd']
        with physical_pixels():
            dc_handle = win32gui.GetWindowDC(hwnd)
            source = win32ui.CreateDCFromHandle(dc_handle)
            target = source.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            old = None
            try:
                bitmap.CreateCompatibleBitmap(source, width, height)
                old = target.SelectObject(bitmap)
                user = ctypes.WinDLL('user32', use_last_error=True)
                user.PrintWindow.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
                if not user.PrintWindow(hwnd, target.GetSafeHdc(), 2):
                    raise RuntimeError('Windows không chụp được cửa sổ này; không suy đoán tọa độ.')
                picture = Image.frombuffer('RGB', (width, height), bitmap.GetBitmapBits(True), 'raw', 'BGRX', 0, 1)
            finally:
                if old is not None:
                    target.SelectObject(old)
                win32gui.DeleteObject(bitmap.GetHandle())
                target.DeleteDC()
                source.DeleteDC()
                win32gui.ReleaseDC(hwnd, dc_handle)
        if self.geometry(session) != rect:
            raise PermissionError('Cửa sổ di chuyển khi chụp; chụp lại.')
        if all(lo == hi for lo, hi in picture.getextrema()):
            raise RuntimeError('Ảnh cửa sổ trống; cần đọc mô hình hoặc dùng UIA.')
        for quality in (85, 65, 45, 25):
            stream = io.BytesIO()
            picture.save(stream, format='JPEG', quality=quality)
            if stream.tell() <= 1048576:
                return rect, base64.b64encode(stream.getvalue()).decode('ascii')
        raise RuntimeError('Ảnh vượt 1 MiB; giảm kích thước cửa sổ rồi chụp lại.')

    def input(self, session, plan, check):
        import ctypes
        from ctypes import wintypes
        import win32gui
        hwnd = session['hwnd']
        rect = tuple(plan['rect'])
        class Mouse(ctypes.Structure):
            _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
                        ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
        class Keyboard(ctypes.Structure):
            _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD),
                        ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
        class Payload(ctypes.Union):
            _fields_ = [('mi', Mouse), ('ki', Keyboard)]
        class Input(ctypes.Structure):
            _anonymous_ = ('data',)
            _fields_ = [('type', wintypes.DWORD), ('data', Payload)]
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
        user.SendInput.restype = wintypes.UINT
        def send(events):
            array = (Input * len(events))(*events)
            if user.SendInput(len(events), array, ctypes.sizeof(Input)) != len(events):
                # Best effort release if Windows accepted only the down events. Never replay text.
                releases = [event for event in events if (event.type == 1 and event.ki.dwFlags & 2) or (event.type == 0 and event.mi.dwFlags & 4)]
                if releases:
                    release_array = (Input * len(releases))(*releases)
                    user.SendInput(len(releases), release_array, ctypes.sizeof(Input))
                raise RuntimeError('Windows chặn hoặc chỉ nhận một phần thao tác; đọc lại trước khi thử tiếp.')
        def guard():
            check()
            if self.geometry(session) != rect or win32gui.GetForegroundWindow() != hwnd:
                raise PermissionError('Mất focus hoặc cửa sổ di chuyển; đã dừng nhập.')
        def keyboard(code=0, scan=0, flags=0):
            return Input(type=1, ki=Keyboard(wVk=code, wScan=scan, dwFlags=flags | (1 if code in {33,34,35,36,37,38,39,40,45,46} else 0)))
        with physical_pixels():
            check()
            if self.geometry(session) != rect:
                raise PermissionError('Cửa sổ di chuyển; chụp lại trước khi thao tác.')
            win32gui.SetForegroundWindow(hwnd)
            guard()
            if plan['operation'] == 'click':
                x, y = rect[0]+plan['x'], rect[1]+plan['y']
                if win32gui.GetAncestor(win32gui.WindowFromPoint((x, y)), 2) != hwnd:
                    raise PermissionError('Điểm click bị cửa sổ khác che; chụp lại.')
                import win32api
                left, top, width, height = (win32api.GetSystemMetrics(i) for i in (76, 77, 78, 79))
                if width <= 1 or height <= 1:
                    raise PermissionError('Không xác định được vùng màn hình.')
                move = Mouse(dx=round((x-left)*65535/(width-1)), dy=round((y-top)*65535/(height-1)), dwFlags=0xC001)
                guard()
                # Move and click as one batch: never click wherever the cursor happened to move.
                send([Input(type=0, mi=move), Input(type=0, mi=Mouse(dwFlags=2)), Input(type=0, mi=Mouse(dwFlags=4))])
                return
            if not plan.get('focus') or self.focus(session) != plan['focus']:
                raise PermissionError('Focus nhập đã đổi hoặc chưa được quan sát; click đúng ô rồi đọc lại ảnh.')
            if plan['operation'] == 'type_text':
                # Unicode packets: literal text, no pywinauto hotkey syntax or clipboard.
                raw = plan['text'].encode('utf-16-le')
                for pos in range(0, len(raw), 2):
                    guard()
                    if self.focus(session) != plan['focus']:
                        raise PermissionError('Focus nhập đã đổi; dừng phần văn bản còn lại.')
                    unit = int.from_bytes(raw[pos:pos+2], 'little')
                    send([keyboard(scan=unit, flags=4), keyboard(scan=unit, flags=6)])
            else:
                codes = key_codes(plan['key'])
                guard()
                # Atomic short chord means pause/stop never leaves modifiers pressed.
                send([keyboard(code=c) for c in codes] + [keyboard(code=c, flags=2) for c in reversed(codes)])


class VisualWindows:
    def __init__(self, apps, backend=None):
        self.apps = apps
        self.backend = backend or VisualBackend()

    def prepare(self, name, args):
        from .windows_apps import _LOCK
        self.apps.check()
        if name in {'windows_list_windows', 'windows_attach'}:
            path = self.apps.allowed_path(args['path'])
            plan = {'action': name, 'path': str(path)}
            if name == 'windows_attach':
                row = _SELECTIONS.get(args['window'])
                if not row or row['owner'] != self.apps.owner or row['path'] != path or time.monotonic()-row['observed'] > OBSERVATION_SECONDS:
                    raise PermissionError('Chọn cửa sổ từ windows_list_windows mới nhất.')
                plan['window'] = args['window']
            return plan
        with _LOCK:
            session = self.apps.session(args['session'])
            if 'hwnd' not in session:
                raise PermissionError('Dùng windows_list_windows và windows_attach để chọn đúng cửa sổ.')
            if name == 'windows_capture':
                return {'action': name, 'session': args['session'], 'notice': 'Ảnh chỉ cửa sổ được chọn sẽ được đưa vào hội thoại AI.'}
            if name != 'windows_input':
                raise ValueError('Công cụ không hợp lệ.')
            observation = session.get('observation')
            if not observation or observation['token'] != args['observation'] or time.monotonic()-observation['time'] > OBSERVATION_SECONDS:
                raise PermissionError('Ảnh cũ hoặc đã dùng; chụp lại cửa sổ trước khi nhập.')
            operation = args['operation']
            plan = {'action': name, 'session': args['session'], 'observation': args['observation'],
                    'operation': operation, 'rect': observation['rect'], 'focus': observation.get('focus')}
            if operation == 'click':
                width, height = observation['width'], observation['height']
                for key, limit in [('x', width), ('y', height)]:
                    value = args.get(key)
                    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value < limit or value != int(value):
                        raise ValueError('Tọa độ pixel nguyên phải nằm trong ảnh cửa sổ.')
                    plan[key] = int(value)
            elif operation == 'type_text':
                text = args.get('text')
                if not isinstance(text, str) or not 1 <= len(text) <= 1000 or any(ord(c)<32 for c in text):
                    raise ValueError('Nhập 1–1000 ký tự thường; gửi ENTER/TAB riêng để xác minh.')
                plan['text'] = text
            elif operation == 'press_key':
                key_codes(args.get('key'))
                plan['key'] = args['key']
            else:
                raise ValueError('Chỉ hỗ trợ click, type_text, press_key.')
            plan['notice'] = 'Thao tác cửa sổ được chọn và chụp lại để xác minh; không coi gửi phím thành công là đã hoàn thành bài toán.'
            return plan

    def commit(self, plan):
        from .windows_apps import _LOCK, _SESSIONS, fingerprint
        self.apps.check()
        name = plan['action']
        if name in {'windows_list_windows', 'windows_attach'}:
            plan = self.prepare(name, plan)
            path = self.apps.allowed_path(plan['path'])
            with _LOCK:
                if name == 'windows_list_windows':
                    for token, row in list(_SELECTIONS.items()):
                        if time.monotonic()-row['observed'] > OBSERVATION_SECONDS:
                            del _SELECTIONS[token]
                    rows = []
                    for info in self.backend.list_windows(path)[:30]:
                        token = uuid.uuid4().hex
                        _SELECTIONS[token] = dict(info, owner=self.apps.owner, path=path, observed=time.monotonic())
                        rows.append({'window': token, 'title': info['title'], 'pid': info['pid']})
                    return {'ok': True, 'windows': rows, 'note': 'Chọn cửa sổ đang có; không mở lại ứng dụng.'}
                row = _SELECTIONS[plan['window']]
                session = dict(row, sha256=fingerprint(path), controls={})
                self.backend.geometry(session)
                ident = uuid.uuid4().hex
                _SESSIONS[ident] = session
                self.apps.audit(name, {'pid': session['pid'], 'hwnd': session['hwnd']})
                return {'ok': True, 'session': ident, 'title': row['title'], 'note': 'Đã gắn cửa sổ hiện có. Chụp bằng windows_capture trước thao tác.'}
        with _LOCK:
            prepared = self.prepare(name, plan)
            session = self.apps.session(plan['session'])
            rect = self.backend.geometry(session)
            if name == 'windows_input' and tuple(rect) != tuple(prepared['rect']):
                session.pop('observation', None)
                raise PermissionError('Cửa sổ di chuyển; chụp lại trước khi thao tác.')
            if name == 'windows_input':
                # Invalidate BEFORE sending: a partial failure must never replay an old click.
                session.pop('observation', None)
                session['controls'] = {}
                self.backend.input(session, prepared, self.apps.check)
            self.apps.check()
            rect, encoded = self.backend.capture(session)
            self.apps.check()
            token = uuid.uuid4().hex
            session['observation'] = {'token': token, 'time': time.monotonic(), 'rect': rect,
                                      'width': rect[2]-rect[0], 'height': rect[3]-rect[1], 'focus': self.backend.focus(session)}
            self.apps.audit(name, {'pid': session['pid'], 'operation': prepared.get('operation'), 'verified': False})
            return {'ok': True, 'observation': token, 'width': rect[2]-rect[0], 'height': rect[3]-rect[1],
                    '_screenshot': encoded, 'verification_required': True,
                    'note': 'Ảnh mới sau thao tác. Đọc ảnh hoặc mô hình để xác nhận kết quả trước bước tiếp theo. Không suy đoán nếu ảnh trống/sai cửa sổ.'}


def tool_message(name, result):
    """Keep pixels out of JSON truncation; retain just the latest image in history."""
    import json
    clean = dict(result)
    encoded = clean.pop('_screenshot', None)
    message = {'role': 'tool', 'tool_name': name, 'content': json.dumps(clean, ensure_ascii=False)}
    if encoded:
        message['images'] = [encoded]
    return message


WINDOWS_VISUAL_INSTRUCTION = (
    ' Khi UIA không hỗ trợ, dùng windows_list_windows(path) rồi windows_attach chọn đúng cửa sổ đang có; '
    'không mở thêm PLAXIS. windows_capture trả ảnh cửa sổ và observation; windows_input nhận tọa độ pixel '
    'trong ảnh đó, một click/phím/văn bản mỗi lượt và tự chụp lại. Đọc ảnh sau mỗi thao tác, đối chiếu '
    'mô hình sau mỗi nhóm. Không đoán tọa độ khi model không nhìn được ảnh. Không thao tác cửa sổ khác, '
    'không nhập mật khẩu, không dùng phím để mở shell. Tạm dừng/Kết thúc phải ngắt bước tiếp theo. '
)

"""Gọi trực tiếp API OpenAI-compatible từ máy qua proxy Node.js cục bộ.

Khóa lưu bằng DPAPI theo tài khoản Windows. Trên hệ điều hành khác
cấu hình lưu dạng plaintext (không dùng DPAPI).
"""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


def _config_path() -> Path:
    from .accounts import credentials_path
    return credentials_path().with_name('local_openai.dpapi')


def _encrypt(data: bytes) -> bytes:
    try:
        from .accounts import _dpapi
        return _dpapi(data)
    except RuntimeError:
        # Non-Windows: store as-is (no DPAPI available).
        return data


def _decrypt(data: bytes) -> bytes:
    try:
        from .accounts import _dpapi
        return _dpapi(data, decrypt=True)
    except RuntimeError:
        return data


def save_config(url: str, key: str, model: str,
                use_as_fallback: bool, use_directly: bool) -> None:
    payload = json.dumps({
        'url': url.rstrip('/'),
        'key': key,
        'model': model,
        'use_as_fallback': bool(use_as_fallback),
        'use_directly': bool(use_directly),
    }).encode('utf-8')
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_bytes(_encrypt(payload))
    tmp.replace(path)


def load_config() -> dict | None:
    path = _config_path()
    if not path.is_file():
        return None
    try:
        raw = _decrypt(path.read_bytes())
        data = json.loads(raw.decode('utf-8'))
        if not isinstance(data, dict) or not data.get('url'):
            return None
        data.setdefault('key', '')
        data.setdefault('model', 'gpt-4o-mini')
        data.setdefault('use_as_fallback', False)
        data.setdefault('use_directly', False)
        return data
    except Exception:
        return None


def forget_config() -> None:
    _config_path().unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Core HTTP call
# ---------------------------------------------------------------------------

_RETRY_STATUSES = {502, 503, 504}
_RETRY_DELAY = 2.0   # seconds between retry attempts
_MAX_RETRIES = 1
_UNSET = object()


def _http_post(url: str, headers: dict, body: bytes, timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _chat_once(url: str, key: str, payload: bytes, timeout: float) -> tuple[int, bytes]:
    headers = {'Content-Type': 'application/json', 'Content-Length': str(len(payload))}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    return _http_post(url, headers, payload, timeout)


def chat(messages: list[dict], url: str, key: str, model: str,
         timeout: float = 60.0, cancel_event=None) -> str:
    """Gọi /v1/chat/completions và trả về nội dung text của AI.

    Tự thử lại một lần nếu server trả 502/503/504.
    Ném RuntimeError với thông báo cụ thể để hiển thị trong UI.
    """
    endpoint = url.rstrip('/') + '/v1/chat/completions'
    payload = json.dumps({
        'model': model,
        'messages': messages,
        'max_tokens': 2048,
        'temperature': 0.2,
    }).encode('utf-8')

    status, body = _UNSET, b''
    for attempt in range(_MAX_RETRIES + 1):
        if cancel_event and cancel_event.is_set():
            raise RuntimeError('Đã hủy yêu cầu.')
        if attempt > 0:
            time.sleep(_RETRY_DELAY)
        try:
            status, body = _chat_once(endpoint, key, payload, timeout)
        except OSError as exc:
            if attempt < _MAX_RETRIES:
                continue
            _raise_connection_error(url, exc)

        if status not in _RETRY_STATUSES or attempt == _MAX_RETRIES:
            break

    return _parse_response(status, body, url, model)


def _raise_connection_error(url: str, exc: OSError) -> None:
    msg = str(exc)
    if 'refused' in msg.lower() or 'connect' in msg.lower():
        raise RuntimeError(
            f'Không kết nối được server tại {url}. '
            'Kiểm tra server Node.js đã chạy chưa (bấm "Khởi động server Node.js").'
        )
    raise RuntimeError(f'Lỗi mạng khi gọi {url}: {msg}')


def _parse_response(status: int, body: bytes, url: str, model: str) -> str:
    text = body.decode('utf-8', errors='replace') if body else ''

    # Try to extract a JSON error message for nicer UX
    upstream_msg = ''
    try:
        obj = json.loads(text)
        upstream_msg = (
            (obj.get('error') or {}).get('message', '')
            or obj.get('message', '')
        )
    except Exception:
        pass

    if status == 200:
        try:
            obj = json.loads(text)
            content = obj['choices'][0]['message']['content']
            if not content or not str(content).strip():
                raise RuntimeError('API trả phản hồi trống. Kiểm tra model và hạn mức tài khoản.')
            return str(content).strip()
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(f'Phản hồi từ server không đúng định dạng OpenAI: {exc}') from exc

    if status == 401:
        raise RuntimeError(
            f'Xác thực thất bại (HTTP 401). '
            + ('Chi tiết: ' + upstream_msg if upstream_msg else 'Kiểm tra AUTH_KEY trong .env và ứng dụng.')
        )
    if status == 403:
        raise RuntimeError(f'Không có quyền (HTTP 403). {upstream_msg or "Kiểm tra cấu hình proxy."}')
    if status == 404:
        raise RuntimeError(
            f'Model "{model}" không tìm thấy (HTTP 404). '
            'Kiểm tra tên model và quyền API của tài khoản OpenAI.'
        )
    if status == 429:
        raise RuntimeError(
            f'OpenAI đang giới hạn yêu cầu hoặc hết hạn mức (HTTP 429). '
            + ('Chi tiết: ' + upstream_msg if upstream_msg else 'Thử lại sau hoặc nạp thêm credit.')
        )
    if status in (502, 503, 504):
        raise RuntimeError(
            f'Server proxy hoặc OpenAI trả HTTP {status} (Bad Gateway / Service Unavailable). '
            'OpenAI có thể đang gián đoạn — thử lại sau vài phút. '
            + ('Chi tiết: ' + upstream_msg if upstream_msg else '')
        )
    if status == 500:
        raise RuntimeError(
            f'Lỗi nội bộ server OpenAI (HTTP 500). '
            + ('Chi tiết: ' + upstream_msg if upstream_msg else 'Thử lại sau.')
        )
    raise RuntimeError(
        f'API tùy chỉnh trả HTTP {status}. '
        + ('Chi tiết: ' + upstream_msg if upstream_msg else 'Kiểm tra URL, khóa server và model.')
    )


# ---------------------------------------------------------------------------
# Convenience: test with a short "Hello" prompt
# ---------------------------------------------------------------------------

def test_chat(url: str, key: str, model: str) -> str:
    """Gửi tin nhắn ngắn để kiểm tra kết nối. Trả về nội dung AI hoặc ném RuntimeError."""
    return chat(
        messages=[{'role': 'user', 'content': 'Chỉ trả lời OK.'}],
        url=url, key=key, model=model,
        timeout=30.0,
    )

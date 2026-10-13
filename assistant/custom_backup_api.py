"""Account-scoped, DPAPI-protected OpenAI-compatible desktop fallback."""
import json
from urllib.parse import urlparse
from urllib.request import Request, HTTPRedirectHandler, build_opener
from urllib.error import HTTPError

from .accounts import _dpapi, credentials_path
from .network import _HTTPHandler, _HTTPSHandler


def endpoint_url(value):
    value = value.strip().rstrip('/')
    parsed = urlparse(value)
    local = parsed.hostname in ('localhost', '127.0.0.1', '::1')
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.scheme not in ('http', 'https') or parsed.scheme == 'http' and not local:
        raise ValueError('Dùng URL HTTPS; HTTP chỉ cho localhost/127.0.0.1.')
    if parsed.path.endswith('/chat/completions'):
        return value
    return value + ('/chat/completions' if parsed.path.endswith('/v1') else '/v1/chat/completions')


def validate(profile):
    endpoint_url(profile.get('url', ''))
    if not isinstance(profile.get('model'), str) or not 1 <= len(profile['model'].strip()) <= 160:
        raise ValueError('Nhập model chat mà server hỗ trợ.')
    key = profile.get('api_key', '')
    if not isinstance(key, str) or not 1 <= len(key) <= 4096 or any(ord(c) < 32 for c in key):
        raise ValueError('Nhập khóa xác thực server, tối đa 4096 ký tự.')
    if type(profile.get('enabled', False)) is not bool:
        raise ValueError('enabled phải là boolean.')
    return dict(profile, url=profile['url'].strip().rstrip('/'), model=profile['model'].strip())


def load(primary, enabled_only=False):
    try:
        value = json.loads(_dpapi(credentials_path().with_name('custom-backup.dpapi').read_bytes(), True))
        if value.get('primary') != primary:
            return None
        profile = validate(value['profile'])
        return profile if not enabled_only or profile.get('enabled') else None
    except (OSError, ValueError, RuntimeError, KeyError, TypeError):
        return None


def save(primary, profile):
    profile = validate(profile)
    target = credentials_path().with_name('custom-backup.dpapi')
    target.parent.mkdir(parents=True, exist_ok=True)
    encrypted = _dpapi(json.dumps({'primary': primary, 'profile': profile}).encode('utf-8'))
    temp = target.with_suffix('.tmp')
    temp.write_bytes(encrypted)
    temp.replace(target)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError('API chuyển hướng URL; nhập URL đích chính xác rồi thử lại.')


def open_response(profile, messages, options=None, stream=False, timeout=125):
    profile = validate(profile)
    options = options or {}
    payload = {'model': profile['model'], 'messages': messages, 'stream': stream,
               'max_tokens': options.get('num_predict', 1600),
               'temperature': options.get('temperature', .2)}
    request = Request(endpoint_url(profile['url']), data=json.dumps(payload).encode('utf-8'),
        headers={'Authorization': 'Bearer ' + profile['api_key'], 'Content-Type': 'application/json',
                 'Accept': 'text/event-stream' if stream else 'application/json'})
    try:
        return build_opener(_HTTPHandler(), _HTTPSHandler(), NoRedirect()).open(request, timeout=timeout)
    except HTTPError as error:
        # Do not expose upstream error bodies, which may echo credentials.
        raise RuntimeError('API tùy chỉnh trả HTTP ' + str(error.code) + '; kiểm tra URL, khóa server và model.') from None
    except Exception as error:
        raise RuntimeError(str(error).replace(profile['api_key'], '[ẨN]')) from None


def chat(profile, messages, options=None, timeout=125):
    with open_response(profile, messages, options, timeout=timeout) as response:
        value = json.loads(response.read(4 * 1024 ** 2))
    choices = value.get('choices', [])
    answer = choices[0].get('message', {}).get('content') if choices else None
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError('API chưa trả choices[0].message.content hợp lệ.')
    return {'success': True, 'answer': answer,
            'truncated': choices[0].get('finish_reason') == 'length'}


def stream_answer(profile, messages, options=None, timeout=125, cancel_event=None):
    with open_response(profile, messages, options, True, timeout) as response:
        if 'text/event-stream' not in response.headers.get('Content-Type', ''):
            value = json.loads(response.read(4 * 1024 ** 2))
            choices = value.get('choices', [])
            text = choices[0].get('message', {}).get('content') if choices else None
            if not isinstance(text, str) or not text:
                raise RuntimeError('API không trả nội dung chat hợp lệ.')
            yield 'text', text
            return
        complete = False
        received = False
        for raw in response:
            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError('Đã dừng yêu cầu API.')
            line = raw.decode('utf-8').strip()
            if not line.startswith('data:'):
                continue
            payload = line[5:].strip()
            if payload == '[DONE]':
                complete = True
                break
            value = json.loads(payload)
            if value.get('error'):
                raise RuntimeError('API tùy chỉnh báo lỗi trong luồng.')
            choices = value.get('choices', [])
            if not choices:
                continue
            delta = choices[0].get('delta', {})
            text = delta.get('content')
            if isinstance(text, str) and text:
                received = True
                yield 'text', text
            if choices[0].get('finish_reason') is not None:
                complete = True
        if not complete or not received:
            raise RuntimeError('API tùy chỉnh ngắt luồng hoặc chưa trả nội dung; không tự gửi lại.')


def fallback(session, messages, options=None, timeout=125, on_status=None):
    primary = {'endpoint': session['endpoint'], 'username': session['username']}
    profile = load(primary, enabled_only=True)
    if profile is None:
        return None
    if on_status:
        on_status('Đang dùng API tùy chỉnh dự phòng trên máy này.')
    return chat(profile, messages, options, timeout)

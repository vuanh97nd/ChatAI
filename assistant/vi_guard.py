"""Chặn chữ Trung Quốc lọt vào câu trả lời tiếng Việt (lỗi hay gặp của Qwen).

Cách làm: bọc ollama.Client.chat. Nếu câu trả lời có chữ Hán/Nhật/Hàn trong khi
người dùng không viết chữ đó, gọi lại model một lần với yêu cầu chỉ dùng tiếng Việt.
Nếu vẫn còn, xóa phần chữ Hán. Không đụng tới lời gọi có tool call hoặc JSON (format).
Được cài tự động khi import gói assistant.
"""
import re

CJK = re.compile(r'[　-〿぀-ヿ㄀-ㄯ㐀-䶿一-鿿'
                 r'가-힯豈-﫿＀-￯]+')
RETRY_NOTE = ('Câu trả lời trước bị lẫn chữ Trung Quốc. Hãy trả lời lại câu hỏi ở trên '
              'hoàn toàn bằng tiếng Việt có dấu, không dùng bất kỳ chữ Hán nào. '
              'Nếu được yêu cầu dịch, hãy dịch sang tiếng Việt.')


def has_cjk(text):
    return bool(text) and CJK.search(text) is not None


def strip_cjk(text):
    cleaned = CJK.sub(' ', text or '')
    cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned)
    cleaned = re.sub(r' +([,.!?;:])', r'\1', cleaned)
    return cleaned.strip()


def _content(obj):
    message = obj['message'] if isinstance(obj, dict) else getattr(obj, 'message', None)
    if message is None:
        return ''
    return (message.get('content') if isinstance(message, dict) else getattr(message, 'content', '')) or ''


def _set_content(obj, text):
    message = obj['message'] if isinstance(obj, dict) else obj.message
    if isinstance(message, dict):
        message['content'] = text
    else:
        message.content = text


def _tool_calls(obj):
    message = obj['message'] if isinstance(obj, dict) else getattr(obj, 'message', None)
    if message is None:
        return None
    return message.get('tool_calls') if isinstance(message, dict) else getattr(message, 'tool_calls', None)


def _user_wrote_cjk(messages):
    for m in messages or []:
        if (m.get('role') if isinstance(m, dict) else getattr(m, 'role', '')) == 'user':
            text = m.get('content') if isinstance(m, dict) else getattr(m, 'content', '')
            if has_cjk(text or ''):
                return True
    return False


def install():
    try:
        import ollama
    except ImportError:
        return
    original = ollama.Client.chat
    if getattr(original, '_vi_guard', False):
        return

    def retry(self, kwargs):
        again = dict(kwargs)
        again.pop('tools', None)
        again['stream'] = False
        again['messages'] = list(kwargs.get('messages') or []) + [{'role': 'user', 'content': RETRY_NOTE}]
        options = dict(again.get('options') or {})
        options['temperature'] = min(float(options.get('temperature', 0.2) or 0.2), 0.2)
        again['options'] = options
        response = original(self, **again)
        text = _content(response)
        if has_cjk(text):
            _set_content(response, strip_cjk(text))
        return response

    def chat(self, *args, **kwargs):
        # Chỉ xử lý lời gọi dạng keyword do Chat AI dùng; JSON/format và câu hỏi chữ Hán bỏ qua.
        if args or kwargs.get('format') or _user_wrote_cjk(kwargs.get('messages')):
            return original(self, *args, **kwargs)
        if not kwargs.get('stream'):
            response = original(self, **kwargs)
            if not _tool_calls(response) and has_cjk(_content(response)):
                try:
                    return retry(self, kwargs)
                except Exception:
                    _set_content(response, strip_cjk(_content(response)))
            return response
        chunks = list(original(self, **kwargs))
        if any(_tool_calls(c) for c in chunks):
            return iter(chunks)
        text = ''.join(_content(c) for c in chunks)
        if not has_cjk(text):
            return iter(chunks)
        try:
            return iter([retry(self, kwargs)])
        except Exception:
            last = chunks[-1] if chunks else None
            if last is None:
                return iter(chunks)
            for c in chunks[:-1]:
                _set_content(c, '')
            _set_content(last, strip_cjk(text))
            return iter(chunks)

    chat._vi_guard = True
    ollama.Client.chat = chat

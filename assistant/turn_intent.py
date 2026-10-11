"""Keep explicit documentation requests separate from unfinished model execution."""
import json
import re
from difflib import SequenceMatcher

WEB_TOOLS = {'browser_search', 'browser_run', 'web_search', 'web_read'}
RESEARCH_TOOLS = WEB_TOOLS | {'windows_list_apps', 'pdf_read', 'document_read'}


def requested_urls(prompt):
    return re.findall(r'https://[^\s<>"\]]+', prompt or '')


def is_web_research(prompt):
    if re.search(r'(?:đừng|không(?: cần)?)\s+(?:đọc|mở|tìm)', prompt or '', re.I):
        return False
    return bool(requested_urls(prompt) and re.search(
        r'đọc|tìm|tra|nghiên cứu|tài liệu|read|search', prompt, re.I))


def current_turn(state):
    messages = state.get('messages', [])
    index = next((i for i in range(len(messages)-1, -1, -1)
                  if messages[i].get('role') == 'user'), -1)
    return messages[index:] if index >= 0 else []


def validate_research_plan(output, state):
    """Require a real lookup attempt; failed/blocked reads must remain reportable."""
    turn = current_turn(state)
    if not turn or not is_web_research(turn[0].get('content', '')):
        return
    if output.get('tool'):
        if output['tool'] not in RESEARCH_TOOLS:
            raise ValueError('Lượt này yêu cầu đọc tài liệu web. Dùng browser_run/browser_search; không sửa mô hình PLAXIS từ yêu cầu đọc tài liệu.')
        return
    answer = output.get('answer', '').strip()
    for message in state.get('messages', [])[:-len(turn)]:
        previous = message.get('content', '')
        if message.get('role') == 'assistant' and len(previous) > 120 and len(answer) > 120:
            if SequenceMatcher(None, previous[:6000], answer[:6000]).ratio() > .9:
                raise ValueError('Phản hồi đang lặp câu trả lời lịch sử. Trả nội dung nguồn web vừa đọc, không lặp báo cáo mô hình cũ.')
    for message in turn[1:]:
        if message.get('role') != 'tool' or message.get('tool_name') not in WEB_TOOLS:
            continue
        try:
            observed = json.loads(message.get('content', '{}'))
        except (ValueError, TypeError):
            continue
        # App-discovery and stale historical results are not a web attempt.
        if isinstance(observed, dict) and ('ok' in observed or 'error' in observed):
            return
    raise ValueError('Chưa đọc web trong lượt này. Gọi browser_run navigate/read cho URL người dùng gửi; tìm Chrome bằng windows_list_apps nếu chưa biết path. Không trả lại báo cáo mô hình cũ thay nội dung trang.')

"""Tự chọn AI theo độ khó, dùng lại client sẵn có trong cloud.py.

Việc nhẹ -> giữ model local đang chọn. Việc khó -> DeepSeek (qua server nếu
đã đăng nhập, nếu không thì key DPAPI/biến môi trường). Không lưu key mới.

Dùng trong agent.py, trước khi gọi model:
    from .auto_route import pick_client
    client, model, label = pick_client(text, store, session, local_client, local_model)
"""
import re
from .cloud import ServerApiClient, ApiDocumentClient, api_key, API_DEFAULT_MODELS

_HARD = re.compile(
    r"phân tích|so sánh|đánh giá|chứng minh|tính toán|thiết kế|kết cấu|tối ưu|"
    r"lập kế hoạch|báo cáo|hợp đồng|quy chuẩn|tcvn|dự toán|bóc khối lượng|"
    r"debug|refactor|thuật toán|vì sao|tại sao|giải thích chi tiết",
    re.I,
)


def is_hard(text, history_chars=0):
    text = text or ''
    return bool(_HARD.search(text)) or len(text) > 600 or history_chars > 12000


def pick_client(text, store, session, local_client, local_model,
                provider='deepseek', allow_cloud=True, history_chars=0):
    """Trả về (client, model, nhãn). Lỗi cấu hình cloud -> quay về local."""
    if not allow_cloud or not is_hard(text, history_chars):
        return local_client, local_model, 'local'
    try:
        if session:
            c = ServerApiClient(session, provider)
            return c, c.model, provider + ' (server)'
        key = api_key(store, provider)
        if key:
            c = ApiDocumentClient(provider, key, API_DEFAULT_MODELS[provider])
            return c, c.model, provider
    except Exception:
        pass
    return local_client, local_model, 'local'

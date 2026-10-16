"""Direct billing transport; primary login credentials never reach the authority."""
import hashlib
import threading
import time

PRIMARY = 'https://chatai.anhvn53.workers.dev'
AUTHORITY = 'https://chatai-backup.vuanh97nd1.workers.dev'
_cache = {}
_lock = threading.Lock()


def billing_path(path):
    return (path.startswith('/api/billing/') or path.startswith('/api/admin/billing/')) and path not in {
        '/api/admin/billing/central-check', '/api/admin/billing/central-migration'}


def payment_transport(transport, endpoint, path, body, timeout):
    try:
        return transport(endpoint,path,body,timeout=timeout)
    except Exception as error:
        status=getattr(error,'status',None)
        if status is not None and status<500:
            raise
        raise RuntimeError('Server thanh toán dự phòng không khả dụng trong phiên này. Không nạp tiền hoặc dùng QR cũ; kiểm tra trạng thái đơn trước khi thử lại.') from None


def direct_request(transport, endpoint, path, body, timeout=20):
    targets = sorted(set(([body['target']] if body.get('target') else []) + list(body.get('owners', []))))
    identity = (endpoint.rstrip('/'), body.get('username'),
                hashlib.sha256(str(body.get('key', '')).encode()).hexdigest(), tuple(targets))
    # Serialize issuance only: parallel QR polls share the same five-minute session.
    with _lock:
        now = time.time()
        for key in list(_cache):
            if _cache[key]['expires_at'] / 1000 <= now + 15:
                del _cache[key]
        session = _cache.get(identity)
        if not session:
            session = payment_transport(transport,endpoint, '/api/account/billing-session',
                                {'username': body.get('username'), 'key': body.get('key'), 'targets': targets}, timeout=timeout)
            if session.get('billing_endpoint') != AUTHORITY or not isinstance(session.get('billing_session'), str):
                raise RuntimeError('Server thanh toán chưa được xác minh; không gửi thông tin đăng nhập.')
            if not isinstance(session.get('expires_at'), (int, float)) or session['expires_at'] / 1000 <= now:
                raise RuntimeError('Phiên thanh toán không hợp lệ.')
            if len(_cache) >= 128:
                _cache.clear()
            _cache[identity] = session
    clean = {k: v for k, v in body.items() if k not in ('username', 'key', 'billing_session')}
    try:
        return payment_transport(transport,AUTHORITY, path, {**clean, 'billing_session': session['billing_session']}, timeout)
    except Exception as error:
        # Expired sessions are rejected before any mutation. Never retry an ambiguous payment.
        if getattr(error, 'code', None) == 'BILLING_SESSION_EXPIRED':
            with _lock:
                _cache.pop(identity, None)
        raise


def enrich_accounts(transport, endpoint, body, result, timeout):
    users = result.get('users')
    if not isinstance(users, list):
        return result
    owners = [u['username'] for u in users if u.get('account_status') != 'deleted']
    try:
        totals = direct_request(transport, endpoint, '/api/admin/billing/totals',
                                {**body, 'owners': owners}, timeout)['totals'] if owners else {}
    except Exception:
        totals = {}
    for user in users:
        user['billing'] = totals.get(user['username']) or {'billing_unavailable': True}
    return result

"""Online AI uses the primary session; billing has a separate direct transport."""
from .accounts import AccountAPIError


def request_account(*args, **kwargs):
    from . import accounts
    return accounts.request_account(*args, **kwargs)


def ai_request(session, path, body, timeout=125, on_status=None):
    return request_account(session['endpoint'], path, body, timeout=timeout)


# Compatibility for old integrations. Saved AI fallback credentials are inert.
DEFAULT_BACKUP = 'https://chatai-backup.vuanh97nd1.workers.dev'
_unavailable = {}


def load_backup(primary):
    return None


def active_backup(session):
    return None


def mark_unavailable(session):
    pass


def save_backup(primary, session):
    raise RuntimeError('AI trực tuyến dùng server chính; cấu hình AI dự phòng đã bỏ.')


def forget_backup():
    _unavailable.clear()


def eligible(error):
    return False

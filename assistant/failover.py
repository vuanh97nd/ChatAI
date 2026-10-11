"""AI-only failover; each server owns its authentication and data."""
import json
from .accounts import _dpapi, credentials_path, AccountAPIError

def request_account(*args,**kwargs):
    from . import accounts
    return accounts.request_account(*args,**kwargs)

DEFAULT_BACKUP = 'https://chatai-backup.vuanh97nd1.workers.dev'

def save_backup(primary, session):
    path=credentials_path().with_name('backup.dpapi')
    path.parent.mkdir(parents=True,exist_ok=True)
    encrypted=_dpapi(json.dumps({'primary':primary,'session':session}).encode())
    temp=path.with_suffix('.tmp');temp.write_bytes(encrypted);temp.replace(path)
    with _lock:_unavailable.pop((primary['endpoint'],primary['username']),None)

def load_backup(primary):
    try:
        value=json.loads(_dpapi(credentials_path().with_name('backup.dpapi').read_bytes(),True))
        if value.get('primary')==primary and isinstance(value.get('session'),dict):return value['session']
    except (OSError,ValueError,RuntimeError,AttributeError):pass
    return None

def eligible(error):
    if isinstance(error,AccountAPIError):
        # App billing, invalid credentials, and permission errors are not outages.
        return error.code!='QUOTA_EXHAUSTED' and error.status in (429,500,502,503,504,530)
    return str(error).startswith(('Không kết nối được server Chat AI.','Kết nối tới server Chat AI bị ngắt'))

def ai_request(session,path,body,timeout=125,on_status=None):
    allowed=path in ('/api/provider/model','/api/models','/api/document/model')
    active=active_backup(session) if allowed else None
    if active:
        return request_account(active['endpoint'],path,dict(body,username=active['username'],key=active['key']),timeout=timeout)
    try:return request_account(session['endpoint'],path,body,timeout=timeout)
    except RuntimeError as error:
        backup=load_backup({'endpoint':session['endpoint'],'username':session['username']})
        if path not in ('/api/provider/model','/api/models','/api/document/model') or not backup or not eligible(error):raise
        mark_unavailable(session)
        if on_status:on_status('Server chính không hoạt động; đang dùng AI ở server dự phòng. Lịch sử vẫn thuộc server chính.')
        payload=dict(body,username=backup['username'],key=backup['key'])
        return request_account(backup['endpoint'],path,payload,timeout=timeout)

# A short circuit avoids contacting the locked Worker on every agent step.
import time
from threading import Lock
_unavailable={}
_lock=Lock()

def mark_unavailable(session):
    with _lock:_unavailable[(session['endpoint'],session['username'])]=time.monotonic()+300

def active_backup(session):
    with _lock:until=_unavailable.get((session['endpoint'],session['username']),0)
    if until>time.monotonic():
        return load_backup({'endpoint':session['endpoint'],'username':session['username']})
    return None

def forget_backup():
    credentials_path().with_name('backup.dpapi').unlink(missing_ok=True)
    with _lock:_unavailable.clear()

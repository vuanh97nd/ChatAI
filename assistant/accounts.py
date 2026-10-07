"""HTTPS account API + Windows DPAPI, không lưu mật khẩu dạng plaintext."""
import ctypes
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from .config import ROOT

class AccountAPIError(RuntimeError):
    def __init__(self,message,status,retry_after=None,code=None):
        super().__init__(message);self.status=status;self.retry_after=retry_after;self.code=code


def request_account(endpoint,path,body,timeout=12):
    url=urlparse(endpoint)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        raise ValueError('URL server phải là URL gốc HTTPS.')
    request=Request(endpoint.rstrip('/')+path,data=json.dumps(body).encode('utf-8'),headers={'Content-Type':'application/json','Accept':'application/json','User-Agent':'ChatAI-Desktop/2.5 (+Windows; account API)'})
    try:
        with urlopen(request,timeout=timeout) as response:
            raw=response.read(2000001)
            if len(raw)>2000000:raise RuntimeError('Phản hồi server quá lớn. Hãy chia nhỏ yêu cầu.')
            result=json.loads(raw.decode('utf-8'))
    except HTTPError as error:
        detail={}
        try:
            detail=json.loads(error.read(20000).decode())
            message=detail.get('message') or detail.get('title') or 'Server HTTP '+str(error.code)
            if '1010' in str(message):message='Cloudflare chặn kết nối ứng dụng (1010). Kiểm tra quy tắc Browser Integrity Check hoặc WAF của Worker.'
        except Exception:message='Server HTTP '+str(error.code)
        if error.code==403:
            message=str(message)+'\nKết nối Chat AI v2.5.1: server từ chối truy cập. Kiểm tra Security Events của Cloudflare; nếu có challenge, cần quy tắc dành riêng cho API ứng dụng.'
        if not isinstance(detail,dict):detail={}
        for key in ('key','password','old_key','new_key','api_key'):
            if body.get(key):message=str(message).replace(str(body[key]),'[ẨN]')
        raise AccountAPIError(str(message),error.code,detail.get('retry_after') or error.headers.get('Retry-After'),detail.get('code')) from None
    except (URLError,TimeoutError):raise RuntimeError('Không kết nối được server Chat AI.') from None
    if not result.get('success'):raise RuntimeError('Server chưa xác nhận yêu cầu.')
    return result

def _dpapi(raw,decrypt=False):
    if os.name!='nt':raise RuntimeError('Ghi nhớ đăng nhập được bảo vệ bằng DPAPI trên Windows.')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(raw)
    input_blob=Blob(len(raw),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)))
    entropy=ctypes.create_string_buffer(b'ChatAI.credentials.v1')
    entropy_blob=Blob(len(b'ChatAI.credentials.v1'),ctypes.cast(entropy,ctypes.POINTER(ctypes.c_ubyte)))
    output=Blob();crypt=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if decrypt:
        fn=crypt.CryptUnprotectData
        fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        args=[ctypes.byref(input_blob),None,ctypes.byref(entropy_blob),None,None,1,ctypes.byref(output)]
    else:
        fn=crypt.CryptProtectData
        fn.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        args=[ctypes.byref(input_blob),'Chat AI account',ctypes.byref(entropy_blob),None,None,1,ctypes.byref(output)]
    fn.restype=wintypes.BOOL
    if not fn(*args):raise ctypes.WinError(ctypes.get_last_error())
    try:return ctypes.string_at(output.data,output.size)
    finally:kernel.LocalFree(ctypes.cast(output.data,ctypes.c_void_p))

def credentials_path():
    return Path(os.environ.get('LOCALAPPDATA',str(ROOT/'data')))/'ChatAI'/'login.dpapi'

def save_login(session):
    payload=_dpapi(json.dumps(session).encode('utf-8'))
    path=credentials_path();path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_bytes(payload);temp.replace(path)

def load_login():
    path=credentials_path()
    if not path.is_file():return None
    return json.loads(_dpapi(path.read_bytes(),True).decode('utf-8'))

def forget_login():
    credentials_path().unlink(missing_ok=True)

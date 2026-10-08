"""Cloudflare text chat through the application's Worker, never an API key in desktop."""
import json
import secrets
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

CLOUD_MODEL = 'Cloudflare AI'
NVIDIA_MODEL = 'NVIDIA AI'
DEEPSEEK_MODEL = 'DeepSeek API'
GEMINI_MODEL = 'Gemini API'
REMOTE_MODELS = {NVIDIA_MODEL:'nvidia', DEEPSEEK_MODEL:'deepseek', GEMINI_MODEL:'gemini', CLOUD_MODEL:'cloudflare'}
PROVIDER_NAMES = {v:k for k,v in REMOTE_MODELS.items()}
CUSTOM_PROVIDER_TYPES={}
SWITCH_MESSAGE = 'Chọn AI phù hợp với tác vụ bạn muốn thực hiện.'


class CloudError(RuntimeError):
    def __init__(self, message, code=''):
        super().__init__(message)
        self.code = code


def guest_token(store):
    with store.connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', ('cloud_guest_token', secrets.token_hex(32)))
        return db.execute('SELECT value FROM settings WHERE key=?', ('cloud_guest_token',)).fetchone()[0]


def parse_events(lines):
    event, data = '', []
    for raw in lines:
        line = raw.decode('utf-8').rstrip('\r\n') if isinstance(raw, bytes) else raw.rstrip('\r\n')
        if len(line) > 100000:
            raise CloudError('Phản hồi server quá lớn.')
        if not line:
            if data:
                value = json.loads('\n'.join(data))
                if event == 'error':
                    raise CloudError(value.get('message', 'Luồng AI bị ngắt.'))
                yield event, value
            event, data = '', []
        elif line.startswith('event:'):
            event = line[6:].strip()
        elif line.startswith('data:'):
            data.append(line[5:].strip())


def cloud_events(endpoint, body, opener=urlopen):
    url = urlparse(endpoint)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
        raise ValueError('URL server phải là URL gốc HTTPS.')
    request = Request(endpoint.rstrip('/') + '/api/cloud/chat', data=json.dumps(body).encode(),
                      headers={'Content-Type': 'application/json', 'Accept': 'text/event-stream', 'User-Agent': 'ChatAI-Desktop/2.6.6'})
    try:
        with opener(request, timeout=150 if body.get('deep_analysis') else 75) as response:
            yield from parse_events(response)
    except HTTPError as error:
        try:
            detail = json.loads(error.read(20000))
        except (ValueError, UnicodeDecodeError):
            detail = {}
        raise CloudError(detail.get('message', 'Server HTTP ' + str(error.code)), detail.get('code', '')) from None
    except (URLError, TimeoutError):
        raise CloudError('Không kết nối được AI trên server. Bạn có thể chọn mô hình trên máy.') from None


class CloudDocumentClient:
    """Ollama-compatible small-model calls for desktop document preparation."""
    def __init__(self,session): self.session=session
    def list(self): return {'models':[{'model':'document-small'}]}
    def chat(self,model,messages,**kwargs):
        from .accounts import request_account
        result=request_account(self.session['endpoint'],'/api/document/model',
            {'username':self.session['username'],'key':self.session['key'],
             'messages':messages,'format':kwargs.get('format'),
             'max_tokens':min(kwargs.get('options',{}).get('num_predict',700),1000)},timeout=90)
        if not result.get('success') or not result.get('answer'):raise CloudError(result.get('message','Chưa tổng hợp được tài liệu'))
        return {'message':{'content':result['answer']}}


API_ENDPOINTS = {'nvidia':'https://integrate.api.nvidia.com/v1/chat/completions',
                 'deepseek':'https://api.deepseek.com/chat/completions',
                 'gemini':'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'}
API_DEFAULT_MODELS = {'nvidia':'meta/llama-3.3-70b-instruct','deepseek':'deepseek-flash','gemini':'gemini-3.8-flash'}


def _protect_key(value, decrypt=False):
    """Windows DPAPI binds saved API credentials to the current OS account."""
    import ctypes, os
    from ctypes import wintypes
    if os.name != 'nt':
        raise CloudError('Lưu API key được bảo vệ hỗ trợ Windows; trên máy khác dùng biến môi trường NVIDIA_API_KEY / DEEPSEEK_API_KEY / GEMINI_API_KEY.')
    class Blob(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_char))]
    buffer=ctypes.create_string_buffer(value);source=Blob(len(value),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_char)));output=Blob()
    crypt=ctypes.windll.crypt32;kernel=ctypes.windll.kernel32
    function=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    function.restype=wintypes.BOOL
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if not function(ctypes.byref(source),None,None,None,None,1,ctypes.byref(output)):
        raise CloudError('Không mở/lưu được API key cho tài khoản Windows hiện tại. Hãy nhập lại key.')
    try:return ctypes.string_at(output.data,output.size)
    finally:kernel.LocalFree(output.data)


def save_api_key(store,provider,key):
    import base64
    if provider not in API_ENDPOINTS:raise ValueError('Dịch vụ API không hợp lệ.')
    encrypted=base64.b64encode(_protect_key(key.strip().encode())).decode() if key.strip() else ''
    with store.connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('api_key_'+provider,encrypted))


def api_key(store,provider):
    import os,base64
    if provider not in API_ENDPOINTS:raise ValueError('Dịch vụ API không hợp lệ.')
    with store.connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        row=db.execute('SELECT value FROM settings WHERE key=?',('api_key_'+provider,)).fetchone()
    if row and row[0]:return _protect_key(base64.b64decode(row[0]),True).decode()
    return os.environ.get(provider.upper()+'_API_KEY','').strip()


class ApiDocumentClient:
    """OpenAI-compatible adapter, used for intent, full-text map-reduce and final answer."""
    def __init__(self,provider,key,model,opener=urlopen):
        if provider not in API_ENDPOINTS:raise ValueError('Dịch vụ API không hợp lệ.')
        if not key:raise CloudError('Chưa có API key. Vào Cài đặt → Cấu hình máy và AI để nhập key rồi lưu.')
        self.provider,self.key,self.model,self.opener=provider,key,model,opener
        self.small_model='meta/llama-3.1-8b-instruct' if provider=='nvidia' else model
    def list(self):return {'models':[{'model':self.model},{'model':'document-small'}]}
    def chat(self,model,messages,**kwargs):
        messages=[dict(m) for m in messages]
        if kwargs.get('format'):
            messages.insert(0,{'role':'system','content':'Trả về một đối tượng JSON hợp lệ, không Markdown. Schema: '+json.dumps(kwargs['format'],ensure_ascii=False)})
        options=kwargs.get('options',{})
        payload={'model':self.small_model if model=='document-small' else self.model,'messages':messages,'stream':False,
                 'max_tokens':min(max(int(options.get('num_predict',1600)),128),4096),
                 'temperature':options.get('temperature',.2)}
        if self.provider=='gemini':
            payload['reasoning_effort']='low';payload['max_tokens']+=1024
        request=Request(API_ENDPOINTS[self.provider],data=json.dumps(payload).encode(),
            headers={'Content-Type':'application/json','Authorization':'Bearer '+self.key})
        try:
            with self.opener(request,timeout=120) as response:
                data=response.read(4000001)
                if len(data)>4000000:raise CloudError('Phản hồi API quá lớn.')
                value=json.loads(data)
            content=value['choices'][0]['message'].get('content')
            if not isinstance(content,str) or not content.strip():raise CloudError('API chưa trả nội dung; kiểm tra model hoặc token trả lời.')
            truncated=value['choices'][0].get('finish_reason')=='length'
            if truncated and model=='document-small':raise CloudError('Đoạn tổng hợp bị giới hạn token, chưa đọc/tổng hợp đầy đủ.')
            return {'message':{'role':'assistant','content':content},'truncated':truncated}
        except HTTPError as error:
            # Do not echo response bodies or Authorization headers: they may contain secrets.
            hints={401:'API key không hợp lệ.',403:'API key chưa có quyền dùng model.',404:'Model không tồn tại hoặc chưa được cấp quyền.',429:'Hết hạn mức hoặc dịch vụ đang giới hạn yêu cầu.'}
            raise CloudError(PROVIDER_NAMES[self.provider]+' HTTP '+str(error.code)+': '+hints.get(error.code,'Dịch vụ chưa xử lý được yêu cầu.')) from None
        except (URLError,TimeoutError):raise CloudError('Không kết nối được '+PROVIDER_NAMES[self.provider]+'.') from None
        except (ValueError,KeyError,IndexError,TypeError):raise CloudError('Phản hồi API không đúng định dạng.') from None


def api_answer_events(client,body):
    from .prompts import FAST_SYSTEM
    from .document_pipeline import document_instruction,document_footer
    from .answer_policy import guard_answer
    result=body.get('document_result') or {}
    instruction=FAST_SYSTEM+'\nKhông có công cụ thao tác máy trong lượt API này.'
    if result.get('documents') or result.get('intent',{}).get('target_type')=='document':instruction+='\n'+document_instruction(result)
    messages=[{'role':'system','content':instruction},*body.get('history',[]),{'role':'user','content':body['text']}]
    yield 'meta',{'provider':client.provider}
    response=client.chat(client.model,messages,options=body.get('options',{}))
    answer=response['message']['content']
    if response.get('truncated'):answer+='\n\nPhản hồi bị giới hạn token; có thể yêu cầu tiếp tục.'
    if body.get('deep_analysis'):
        yield 'status',{'text':'AI đang rà soát câu trả lời và đối chiếu dữ liệu…'}
        try:
            from .quality import review_answer
            options=body.get('options',{})
            review_cfg={'num_ctx':min(8192,max(2048,int(options.get('num_ctx',4096)))),
                        'num_predict':min(2048,max(256,int(options.get('num_predict',1200))))}
            evidence={'document_result':result,'messages':messages,'web_search':bool(body.get('web_search'))}
            answer=review_answer(client,client.model,body['text'],answer,evidence,review_cfg)
        except Exception:
            answer+='\n\nLưu ý: lượt rà soát sâu chưa hoàn tất; nội dung trên là bản trả lời ban đầu.'
    answer,_=guard_answer(answer,{'messages':messages,'document_result':result},body.get('web_search',False))
    footer=document_footer(result,answer) if result else ''
    yield 'delta',{'text':answer+footer}
    yield 'done',{'success':True,'switch_required':False}


class ServerApiClient:
    """Authenticated proxy: provider API credentials never reach ordinary users."""
    def __init__(self,session,provider,on_status=None,cancel_event=None):
        if not session:raise CloudError('Đăng nhập để dùng AI trực tuyến với key do Admin cấu hình.')
        if provider not in API_ENDPOINTS and not __import__('re').fullmatch(r'ai_[a-f0-9]{32}',provider):raise ValueError('Dịch vụ API không hợp lệ.')
        self.session=dict(session);self.provider=provider;self.model=provider;self.on_status=on_status;self.cancel_event=cancel_event
    def list(self):return {'models':[{'model':self.model},{'model':'document-small'}]}
    def chat(self,model,messages,**kwargs):
        from .accounts import request_account
        options=kwargs.get('options',{})
        body={
            'username':self.session['username'],'key':self.session['key'],'provider':self.provider,
            'messages':messages,'small':model=='document-small','format':kwargs.get('format'),
            'max_tokens':options.get('num_predict',1600),'temperature':options.get('temperature',.2)}
        from .accounts import AccountAPIError
        import random,time
        from threading import Event
        cancel=self.cancel_event or Event()
        for attempt in range(3):
            if cancel.is_set():raise CloudError('Đã dừng yêu cầu.')
            try:
                result=request_account(self.session['endpoint'],'/api/provider/model',body,timeout=125)
                break
            except AccountAPIError as error:
                if CUSTOM_PROVIDER_TYPES.get(self.provider,self.provider)!='nvidia' or error.status!=429 or error.code=='QUOTA_EXHAUSTED' or attempt==2:raise
                delay=(attempt+1)*15+random.uniform(0,2)
                if error.retry_after:
                    try:delay=max(0,float(error.retry_after))
                    except (ValueError,TypeError):
                        try:
                            from email.utils import parsedate_to_datetime
                            delay=max(0,parsedate_to_datetime(str(error.retry_after)).timestamp()-time.time())
                        except (ValueError,TypeError,OverflowError):pass
                if delay>60:raise CloudError('NVIDIA yêu cầu chờ hơn 60 giây. Hãy thử lại sau hoặc chọn AI khác.') from None
                if self.on_status:self.on_status(f'NVIDIA đang giới hạn yêu cầu · chờ {int(delay+0.99)} giây · thử lại {attempt+1}/2…')
                if cancel.wait(delay):raise CloudError('Đã dừng yêu cầu.')
                if self.on_status:self.on_status('Đang kết nối lại NVIDIA AI…')
        if not result.get('success') or not result.get('answer'):raise CloudError(result.get('message','AI trên server chưa trả nội dung.'))
        if result.get('truncated') and model=='document-small':raise CloudError('Đoạn tổng hợp bị giới hạn token, chưa tổng hợp đầy đủ.')
        return {'message':{'role':'assistant','content':result['answer']},'truncated':bool(result.get('truncated'))}


def register_custom_ai(entries):
    import re
    accepted=[]
    for item in entries or []:
        identifier=item.get('id','');label=item.get('label','')
        if not re.fullmatch(r'ai_[a-f0-9]{32}',identifier) or item.get('provider') not in ('nvidia','deepseek','gemini') or not isinstance(label,str) or not 1<=len(label)<=80:continue
        name=label
        if name in REMOTE_MODELS and REMOTE_MODELS[name]!=identifier:continue
        REMOTE_MODELS[name]=identifier;PROVIDER_NAMES[identifier]=name;CUSTOM_PROVIDER_TYPES[identifier]=item['provider']
        accepted.append({k:item.get(k,'') for k in ('id','label','provider','model')})
    return accepted

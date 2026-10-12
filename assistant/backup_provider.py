"""Provider administration addressed only to the chosen backup server."""
import re
from .accounts import request_account

PROVIDERS={'nvidia','deepseek','gemini','groq','openai','cloudflare'}

def backup_provider_request(session, action, provider, api_key='', model=''):
    if action not in {'status','save','test','models'} or provider not in PROVIDERS:
        raise ValueError('Thao tác hoặc nhà cung cấp không hợp lệ.')
    if model and not re.fullmatch(r'[A-Za-z0-9._/-]{1,160}',model):
        raise ValueError('Model không hợp lệ.')
    if api_key and not 10<=len(api_key)<=4096:
        raise ValueError('Khóa API phải từ 10 đến 4096 ký tự.')
    body={'username':session['username'],'key':session['key']}
    path='/api/admin/providers/'+action
    if action=='save':
        if provider=='cloudflare':raise ValueError('Cloudflare dùng binding AI, không nhập khóa.')
        if not api_key and not model:raise ValueError('Nhập khóa hoặc model để lưu.')
        body.update(providers={provider:api_key} if api_key else {},models={provider:model} if model else {})
    elif action=='test':
        if provider=='cloudflare':
            path='/api/provider/model'
            body.update(provider=provider,messages=[{'role':'user','content':'Chỉ trả lời OK.'}],max_tokens=64,temperature=0)
        else:body.update(provider=provider,api_key=api_key,model=model)
    elif action=='models':
        if provider=='cloudflare':raise ValueError('Cloudflare chưa có danh sách model qua công cụ này.')
        body.update(provider=provider,api_key=api_key)
    # No failover here: a configuration write/test must address this exact server.
    try:return request_account(session['endpoint'],path,body,timeout=125 if action=='test' else 30)
    except Exception as error:
        if api_key:raise RuntimeError(str(error).replace(api_key,'[ẨN]')) from None
        raise

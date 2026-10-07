"""AI viết Python; mạng đi qua bridge web_search/web_read, code chạy Docker không mạng."""
import json

PREFIX = '__CHAT_AI_WEB_REQUEST__'
PRELUDE = '''import json as _json
with open('/workspace/search-data.json',encoding='utf-8') as _file:
    _search_cache=_json.load(_file)
def _web_request(kind,value):
    _key=_json.dumps([kind,value],ensure_ascii=False)
    if _key not in _search_cache:
        print('__CHAT_AI_WEB_REQUEST__'+_json.dumps({'kind':kind,'value':value},ensure_ascii=False),flush=True)
        raise SystemExit(75)
    return _search_cache[_key]
def web_search(query):
    return _web_request('search',query)
def web_read(url):
    return _web_request('read',url)
'''

class PythonSearch:
    def __init__(self,runner,web,audit):
        self.runner,self.web,self.audit=runner,web,audit
    def prepare(self,code):
        if not isinstance(code,str) or not code.strip() or len(code)>12000:
            raise ValueError('Code tra cứu tối đa12000 ký tự.')
        self.runner.prepare('python_run',{'code':PRELUDE+code})
        return {'action':'python_search','code':code,'limits':'Docker không mạng. Tối đa4 truy vấn web qua bridge, mỗi lần chạy30 giây.'}
    def commit(self,plan):
        cache={};sources=[]
        for attempt in range(5):
            step=self.runner.prepare('python_run',{'code':PRELUDE+plan['code']})
            step['search_data']=cache
            result=self.runner.commit(step)
            if result.get('ok'):
                return {**result,'sources':sources,'web_requests':len(cache)}
            requests=[line[len(PREFIX):] for line in result.get('stdout','').splitlines() if line.startswith(PREFIX)]
            if result.get('exit_code')!=75 or not requests or attempt==4:
                return {**result,'sources':sources,'note':'Lỗi code hoặc hết4 truy vấn web; AI có thể sửa code trong giới hạn lượt.'}
            query=json.loads(requests[-1]);kind,value=query.get('kind'),query.get('value')
            if not isinstance(value,str):raise ValueError('Truy vấn phải là chuỗi.')
            if kind=='search':
                data=self.web.web_search(value);sources.extend(data.get('sources',[]))
            elif kind=='read':
                data=self.web.web_read(value);sources.append({'url':data['url'],'title':data['url']})
            else:raise ValueError('Bridge chỉ hỗ trợ search/read.')
            key=json.dumps([kind,value],ensure_ascii=False)
            cache[key]=data
            if len(json.dumps(cache))>50000:raise ValueError('Dữ liệu tra cứu vượt giới hạn50k ký tự.')
            self.audit('python_web_request',{'kind':kind,'query':value})
        raise RuntimeError('Hết giới hạn tra cứu.')

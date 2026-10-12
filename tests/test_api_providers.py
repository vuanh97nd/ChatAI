"""Network-free contract tests; live keys and Windows DPAPI are not exercised."""
import io,json,sqlite3,unittest,sys,tempfile,os
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from assistant.cloud import (ApiDocumentClient,API_ENDPOINTS,API_DEFAULT_MODELS,REMOTE_MODELS,
    NVIDIA_MODEL,DEEPSEEK_WEB_MODEL,api_answer_events,CloudError,save_api_key,api_key,
    DeepSeekWebClient,save_deepseek_web_token,deepseek_web_token,_DEEPSEEK_WEB_ENDPOINT)
from assistant.model_preferences import valid_model,load_model

class Response(io.BytesIO):
    pass
class Store:
    def __init__(self):self.db=sqlite3.connect(':memory:')
    def connection(self):return self.db

class ApiTests(unittest.TestCase):
    def test_provider_routes_and_payload(self):
        for provider,url in API_ENDPOINTS.items():
            seen=[]
            def opener(req,timeout):
                seen.append((req,timeout));return Response(json.dumps({'choices':[{'message':{'content':'OK'}}]}).encode())
            client=ApiDocumentClient(provider,'dummy-secret',API_DEFAULT_MODELS[provider],opener)
            answer=client.chat('document-small',[{'role':'user','content':'Xin chào'}],format={'type':'object'})
            req,timeout=seen[0];payload=json.loads(req.data)
            self.assertEqual(req.full_url,url);self.assertEqual(req.get_header('Authorization'),'Bearer dummy-secret')
            self.assertEqual(payload['model'],client.small_model);self.assertFalse(payload['stream'])
            self.assertIn('JSON',payload['messages'][0]['content']);self.assertEqual(answer['message']['content'],'OK')
            self.assertEqual(timeout,120)
    def test_missing_key(self):
        with self.assertRaises(CloudError):ApiDocumentClient('nvidia','','model')
    def test_unknown_provider(self):
        with self.assertRaises(ValueError):ApiDocumentClient('untrusted','key','model')
    def test_errors_do_not_echo_secrets(self):
        for status in (401,403,404,429,500):
            def opener(req,timeout):raise HTTPError(req.full_url,status,'bad',{},io.BytesIO(b'dummy-secret'))
            with self.assertRaises(CloudError) as error:ApiDocumentClient('nvidia','dummy-secret','model',opener).chat('x',[])
            self.assertNotIn('dummy-secret',str(error.exception));self.assertIn(str(status),str(error.exception))
    def test_malformed_and_empty_responses(self):
        for data in (b'not-json',b'{}',b'{"choices":[{"message":{"content":""}}]}'):
            with self.assertRaises(CloudError):ApiDocumentClient('nvidia','key','model',lambda *a,**kw:Response(data)).chat('x',[])
    def test_saved_key_encrypted_and_retained(self):
        store=Store()
        def protect(data,decrypt=False):return data[::-1] if decrypt else data[::-1]
        with patch('assistant.cloud._protect_key',protect):
            save_api_key(store,'gemini','dummy-secret')
            raw=store.db.execute('SELECT value FROM settings').fetchone()[0]
            self.assertNotIn('dummy-secret',raw);self.assertEqual(api_key(store,'gemini'),'dummy-secret')
            save_api_key(store,'gemini','');self.assertEqual(api_key(store,'gemini'),'')
    def test_environment_fallback(self):
        with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'dummy-env'}):self.assertEqual(api_key(Store(),'deepseek'),'dummy-env')
    def test_account_models_accept_remote_and_default_nvidia(self):
        for name in REMOTE_MODELS:self.assertTrue(valid_model(name))
        self.assertEqual(load_model(Store(),None),NVIDIA_MODEL)
        self.assertEqual(load_model(Store(),{'endpoint':'https://example.com','username':'new'}),NVIDIA_MODEL)
    def test_history_evidence_and_conditional_sources(self):
        captured=[]
        class Client:
            provider='nvidia';model='model'
            def chat(self,model,messages,**kw):captured.extend(messages);return {'message':{'content':'Kết quả [D1].'}}
        result={'intent':{'target_type':'document'},'documents':[{'id':'D1','origin':'web','site':'Trang chính thức','title':'Tài liệu','url':'https://example.com/doc','full_document':True}]}
        body={'text':'Tóm tắt tiếp','history':[{'role':'user','content':'Tài liệu A'},{'role':'assistant','content':'A'}],'document_result':result}
        events=list(api_answer_events(Client(),body));answer=events[1][1]['text']
        self.assertEqual(captured[1:3],body['history']);self.assertIn('Tài liệu',captured[0]['content'])
        self.assertIn('example.com - Tài liệu - https://example.com/doc',answer)
        self.assertFalse(events[-1][1]['switch_required'])
    def test_uncited_document_does_not_add_footer(self):
        class Client:
            provider='deepseek';model='m'
            def chat(self,*a,**kw):return {'message':{'content':'Xin chào.'}}
        answer=list(api_answer_events(Client(),{'text':'Chào','document_result':{'documents':[{'id':'D1','origin':'web','url':'https://example.com'}]}}))[1][1]['text']
        self.assertNotIn('Nguồn:',answer)
    def test_default_migration_and_config(self):
        from assistant.config import validate_config
        cfg={'ollama_host':'http://localhost:11434','default_model':'qwen2.5:3b','code_model':'qwen2.5-coder:7b','num_ctx':4096,'max_rounds':8,'whitelist':['workspace'],'chat_provider':'cloudflare'}
        with tempfile.TemporaryDirectory() as d,patch('assistant.config.ROOT',Path(d)):
            migrated=validate_config(cfg);self.assertEqual(migrated['chat_provider'],'nvidia')
            migrated['chat_provider']='gemini';self.assertEqual(validate_config(migrated)['chat_provider'],'gemini')
            migrated['gemini_model']='invalid name';self.assertRaises(ValueError,validate_config,migrated)
    def test_config_accepts_deepseek_web_provider(self):
        from assistant.config import validate_config
        cfg={'ollama_host':'http://localhost:11434','default_model':'qwen2.5:3b','code_model':'qwen2.5-coder:7b','num_ctx':4096,'max_rounds':8,'whitelist':['workspace'],'api_provider_revision':1,'chat_provider':'deepseek_web'}
        with tempfile.TemporaryDirectory() as d,patch('assistant.config.ROOT',Path(d)):
            result=validate_config(cfg);self.assertEqual(result['chat_provider'],'deepseek_web')

class DeepSeekWebTests(unittest.TestCase):
    def _make_sse(self,chunks,include_done=True):
        """Build a fake SSE response iterable from text chunks."""
        import io
        lines=[]
        for chunk in chunks:
            payload=json.dumps({'choices':[{'delta':{'content':chunk},'finish_reason':None}]})
            lines.append(('data: '+payload+'\n').encode())
        if include_done:lines.append(b'data: [DONE]\n')
        return io.BytesIO(b''.join(lines))

    def test_missing_token_raises(self):
        with self.assertRaises(CloudError):DeepSeekWebClient('')

    def test_chat_success(self):
        body=json.dumps({'choices':[{'message':{'content':'Xin chào.'},'finish_reason':'stop'}]}).encode()
        client=DeepSeekWebClient('tok',opener=lambda req,timeout:Response(body))
        result=client.chat(client.model,[{'role':'user','content':'Hi'}])
        self.assertEqual(result['message']['content'],'Xin chào.')
        self.assertFalse(result['truncated'])

    def test_chat_empty_content_raises(self):
        for body in (b'{"choices":[{"message":{"content":""},"finish_reason":"stop"}]}',
                     b'{"choices":[{"message":{},"finish_reason":"stop"}]}',b'not-json'):
            with self.assertRaises(CloudError):
                DeepSeekWebClient('tok',opener=lambda req,timeout:Response(body)).chat('m',[])

    def test_chat_http_errors(self):
        codes_and_keywords={401:'hết hạn',403:'thu hồi',429:'giới hạn',500:'HTTP 500'}
        for code,keyword in codes_and_keywords.items():
            def opener(req,timeout,c=code):raise HTTPError(req.full_url,c,'bad',{},Response(b''))
            with self.assertRaises(CloudError) as ctx:DeepSeekWebClient('tok',opener=opener).chat('m',[])
            self.assertIn(keyword,str(ctx.exception))

    def test_chat_does_not_echo_token(self):
        def opener(req,timeout):raise HTTPError(req.full_url,401,'bad',{},Response(b'secret-tok'))
        with self.assertRaises(CloudError) as ctx:DeepSeekWebClient('secret-tok',opener=opener).chat('m',[])
        self.assertNotIn('secret-tok',str(ctx.exception))

    def test_chat_request_uses_endpoint_and_bearer(self):
        captured=[]
        body=json.dumps({'choices':[{'message':{'content':'OK'},'finish_reason':'stop'}]}).encode()
        def opener(req,timeout):captured.append(req);return Response(body)
        DeepSeekWebClient('my-token',opener=opener).chat('m',[{'role':'user','content':'Hi'}])
        req=captured[0]
        self.assertEqual(req.full_url,_DEEPSEEK_WEB_ENDPOINT)
        self.assertEqual(req.get_header('Authorization'),'Bearer my-token')

    def test_stream_answer_yields_text_chunks(self):
        def opener(req,timeout):
            lines=[
                b'data: '+json.dumps({'choices':[{'delta':{'content':'Xin '},'finish_reason':None}]}).encode()+b'\n',
                b'data: '+json.dumps({'choices':[{'delta':{'content':'chào.'},'finish_reason':None}]}).encode()+b'\n',
                b'data: [DONE]\n',
            ]
            class FakeResp:
                def __enter__(self):return self
                def __exit__(self,*a):pass
                def __iter__(self):return iter(lines)
            return FakeResp()
        client=DeepSeekWebClient('tok',opener=opener)
        chunks=list(client.stream_answer(client.model,[{'role':'user','content':'Hi'}]))
        texts=[c for kind,c in chunks if kind=='text']
        self.assertEqual(''.join(texts),'Xin chào.')

    def test_stream_answer_yields_reasoning(self):
        def opener(req,timeout):
            lines=[
                b'data: '+json.dumps({'choices':[{'delta':{'reasoning_content':'Suy nghĩ...'},'finish_reason':None}]}).encode()+b'\n',
                b'data: '+json.dumps({'choices':[{'delta':{'content':'OK'},'finish_reason':None}]}).encode()+b'\n',
                b'data: [DONE]\n',
            ]
            class FakeResp:
                def __enter__(self):return self
                def __exit__(self,*a):pass
                def __iter__(self):return iter(lines)
            return FakeResp()
        client=DeepSeekWebClient('tok',opener=opener)
        chunks=list(client.stream_answer(client.model,[]))
        self.assertIn(('reasoning','Suy nghĩ...'),chunks)
        self.assertIn(('text','OK'),chunks)

    def test_deepseek_web_token_save_and_load(self):
        store=Store()
        def protect(data,decrypt=False):return data[::-1] if decrypt else data[::-1]
        with patch('assistant.cloud._protect_key',protect):
            save_deepseek_web_token(store,'my-token')
            raw=store.db.execute("SELECT value FROM settings WHERE key='deepseek_web_token'").fetchone()[0]
            self.assertNotIn('my-token',raw)
            self.assertEqual(deepseek_web_token(store),'my-token')

    def test_deepseek_web_token_clear(self):
        store=Store()
        def protect(data,decrypt=False):return data[::-1] if decrypt else data[::-1]
        with patch('assistant.cloud._protect_key',protect):
            save_deepseek_web_token(store,'my-token')
            save_deepseek_web_token(store,'')
            self.assertEqual(deepseek_web_token(store),'')

    def test_deepseek_web_token_env_fallback(self):
        with patch.dict(os.environ,{'DEEPSEEK_WEB_TOKEN':'env-tok'}):
            self.assertEqual(deepseek_web_token(Store()),'env-tok')

    def test_api_answer_events_uses_streaming_path(self):
        stream_calls=[]
        class StreamClient:
            provider='deepseek_web';model='deepseek-chat'
            def stream_answer(self,model,messages,**kw):
                stream_calls.append(True)
                yield 'text','Kết quả streaming.'
        body={'text':'Xin chào','document_result':{}}
        events=list(api_answer_events(StreamClient(),body))
        self.assertTrue(stream_calls,'stream_answer should be called')
        texts=[v['text'] for t,v in events if t=='delta']
        self.assertIn('Kết quả streaming.',''.join(texts))
        done_events=[v for t,v in events if t=='done']
        self.assertTrue(done_events);self.assertFalse(done_events[-1]['switch_required'])

    def test_deepseek_web_model_in_remote_models(self):
        self.assertIn(DEEPSEEK_WEB_MODEL,REMOTE_MODELS)
        self.assertEqual(REMOTE_MODELS[DEEPSEEK_WEB_MODEL],'deepseek_web')

if __name__=='__main__':unittest.main()

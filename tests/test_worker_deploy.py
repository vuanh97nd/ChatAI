import io
import json
import unittest
from scripts.deploy_worker import deploy, multipart

class WorkerDeployTests(unittest.TestCase):
    def test_preserves_all_existing_binding_types(self):
        body,mime=multipart(b'export default {};',{'compatibility_date':'2026-10-01','compatibility_flags':['nodejs_compat'],'bindings':[{'type':'secret_text','name':'DEEPSEEK_API_KEY'},{'type':'d1','name':'DB'},{'type':'kv_namespace','name':'MEMORY_KV'},{'type':'plain_text','name':'MODEL'},{'type':'ai','name':'AI'}]})
        metadata=json.loads(body.split(b'\r\n\r\n',1)[1].split(b'\r\n--',1)[0])
        self.assertEqual(metadata['keep_bindings'],['ai','d1','kv_namespace','plain_text','secret_text'])
        self.assertNotIn('bindings',metadata)
        self.assertEqual(metadata['main_module'],'work.js')
        self.assertEqual(metadata['compatibility_flags'],['nodejs_compat'])
        self.assertIn(b'export default {};',body)
        self.assertIn('boundary=',mime)

    def test_missing_credentials_never_calls_cloudflare(self):
        with self.assertRaisesRegex(ValueError,'secrets'):
            deploy({},lambda *a,**kw:self.fail('network called'))

    def test_missing_bindings_refuses_upload(self):
        with self.assertRaisesRegex(ValueError,'bindings'):
            multipart(b'code',{'compatibility_date':'2026-10-01'})

    def test_fetch_settings_then_upload_existing_worker(self):
        calls=[]
        def request(req,**kw):
            calls.append(req)
            result={'bindings':[],'compatibility_date':'2026-10-01'} if len(calls)==1 else {}
            return io.BytesIO(json.dumps({'success':True,'result':result}).encode())
        deploy({'CF_API_TOKEN':'fake-token','CF_ACCOUNT_ID':'a'*32,'CF_WORKER_NAME':'chatai'},request)
        self.assertEqual(calls[0].get_method(),'GET')
        self.assertTrue(calls[0].full_url.endswith('/chatai/settings'))
        self.assertEqual(calls[1].get_method(),'PUT')
        self.assertTrue(calls[1].full_url.endswith('/chatai'))

    def test_cloudflare_error_stops_before_upload(self):
        calls=[]
        def request(req,**kw):
            calls.append(req)
            return io.BytesIO(b'{"success":false,"errors":[{"code":10000}]}')
        with self.assertRaisesRegex(RuntimeError,'10000'):
            deploy({'CF_API_TOKEN':'fake','CF_ACCOUNT_ID':'a'*32},request)
        self.assertEqual(len(calls),1)

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from assistant.application_transport import ApplicationTransport,TransportBackend,validate_connections,LIMIT
from assistant.communication import MethodRequired
from assistant.plugin_bridge import BridgeServer
from assistant.windows_apps import resume_automation,stop_automation

class TransportTests(unittest.TestCase):
    def setUp(self):
        resume_automation()
        self.cfg={'communication_methods':{'plugin':True,'http':True,'ipc':True},'application_connections':{}}
        self.audit=[]
        self.tools=ApplicationTransport(self.cfg,lambda event,data:self.audit.append((event,data)))
        self.servers=[]
    def tearDown(self):
        for bridge in self.servers:bridge.close()
        resume_automation()
    def bridge(self,transport,token=''):
        server=BridgeServer({'sum':lambda args:sum(args)},token=token)
        port=getattr(server,'start_'+transport)()
        self.servers.append(server)
        entry={'transport':transport,'actions':['capabilities','sum'],'timeout':2}
        if transport=='tcp':entry.update(host='127.0.0.1',port=port)
        else:entry['url']=('ws' if transport=='websocket' else 'http')+'://127.0.0.1:'+str(port)+'/'
        self.cfg['application_connections']['demo']=entry
        return entry
    def test_real_http_websocket_tcp_rpc_roundtrips(self):
        for transport in ('http','websocket','tcp'):
            with self.subTest(transport=transport):
                self.bridge(transport)
                result=self.tools.commit(self.tools.prepare('plugin_call',{'connection':'demo','function':'sum','payload':'[2,3,7]'}))
                self.assertTrue(result['ok'],result);self.assertEqual(result['result'],12)
                self.assertTrue(result['response_received'])
    def test_raw_http_and_websocket_tools_receive_actual_response(self):
        for transport,tool in [('http','application_http'),('websocket','application_websocket')]:
            self.bridge(transport)
            payload=json.dumps({'id':'manual','action':'sum','arguments':[1,9]})
            args={'connection':'demo','payload':payload}
            if transport=='http':args['method']='POST'
            result=self.tools.commit(self.tools.prepare(tool,args))
            self.assertTrue(result['ok'],result)
            self.assertEqual(result['result']['result'],10)
    def test_ipc_tool_correlates_response(self):
        self.bridge('tcp')
        result=self.tools.commit(self.tools.prepare('application_ipc',{'connection':'demo','function':'sum','payload':'[4,5]'}))
        self.assertTrue(result['ok']);self.assertEqual(result['result'],9)
    def test_missing_method_endpoint_and_action_do_not_send(self):
        self.bridge('http')
        self.cfg['communication_methods']['plugin']=False
        with self.assertRaisesRegex(MethodRequired,'Cần bật phương thức Plugin'):
            self.tools.prepare('plugin_call',{'connection':'demo','function':'sum'})
        self.cfg['communication_methods']['plugin']=True
        with self.assertRaisesRegex(MethodRequired,'khai báo kết nối'):
            self.tools.prepare('plugin_call',{'connection':'missing','function':'sum'})
        with self.assertRaises(PermissionError):
            self.tools.prepare('plugin_call',{'connection':'demo','function':'delete_everything'})
        self.assertEqual(self.audit,[])
    def test_configuration_or_permission_change_invalidates_plan(self):
        self.bridge('http')
        plan=self.tools.prepare('plugin_call',{'connection':'demo','function':'sum','payload':'[1]'} )
        self.cfg['application_connections']['demo']['url']='http://127.0.0.1:1/'
        with self.assertRaises(PermissionError):self.tools.commit(plan)
        self.cfg['communication_methods']['plugin']=False
        with self.assertRaises(MethodRequired):self.tools.commit(plan)
    def test_token_is_resolved_from_environment_and_not_listed_or_audited(self):
        for transport in ('http','websocket','tcp'):
            entry=self.bridge(transport,token='secret-test-token')
            entry['token_env']='CHATAI_TEST_TOKEN'
            plan=self.tools.prepare('plugin_call',{'connection':'demo','function':'sum','payload':'[6]'} )
            with patch.dict(os.environ,{'CHATAI_TEST_TOKEN':'secret-test-token'}):
                result=self.tools.commit(plan)
            self.assertTrue(result['ok'],result)
            listing=self.tools.commit(self.tools.prepare('application_connections',{}))
            self.assertNotIn('secret-test-token',json.dumps([listing,plan,self.audit]))
    def test_wrong_correlation_and_timeout_never_retry(self):
        from types import SimpleNamespace
        self.cfg['application_connections']['demo']={'transport':'tcp','port':1,'actions':['sum']}
        calls=[]
        def tcp(entry,payload):calls.append(payload);return {'id':'wrong','ok':True,'result':1}
        self.tools.backend=SimpleNamespace(tcp=tcp)
        result=self.tools.commit(self.tools.prepare('plugin_call',{'connection':'demo','function':'sum'}))
        self.assertFalse(result['ok']);self.assertTrue(result['uncertain']);self.assertEqual(len(calls),1)
        def timeout(entry,payload):calls.append(payload);raise TimeoutError('secret URL')
        self.tools.backend.tcp=timeout
        result=self.tools.commit(self.tools.prepare('plugin_call',{'connection':'demo','function':'sum'}))
        self.assertFalse(result['ok']);self.assertNotIn('secret URL',json.dumps(result));self.assertEqual(len(calls),2)
    def test_invalid_endpoint_configuration_and_paths(self):
        entries=[{'transport':'http','url':'http://example.com'},
                 {'transport':'websocket','url':'ws://example.com'},
                 {'transport':'http','url':'https://u:p@example.com'},
                 {'transport':'tcp','host':'example.com','port':123},
                 {'transport':'pipe','pipe':r'\\remote\pipe\bad'},
                 {'transport':'http','url':None},
                 {'transport':'http','url':'https://example.com','token':'plain-secret'}]
        for entry in entries:
            with self.subTest(entry=entry),self.assertRaises(ValueError):validate_connections({'application_connections':{'x':entry}})
        self.bridge('http')
        for path in ('../escape','//other','https://other','a%2fb','a?b','a\\b'):
            with self.assertRaises(ValueError):self.tools.prepare('application_http',{'connection':'demo','path':path})
    def test_plugin_sdk_rejects_unknown_action_before_handler_and_auth(self):
        calls=[];bridge=BridgeServer({'work':lambda args:calls.append(args)},token='expected')
        result=bridge.dispatch({'id':'req','action':'work','arguments':1})
        self.assertFalse(result['ok']);self.assertEqual(calls,[])
        result=bridge.dispatch({'id':'req','action':'unknown','token':'expected'})
        self.assertFalse(result['ok']);self.assertEqual(calls,[])
        result=bridge.dispatch({'id':'req','action':'capabilities','token':'expected'})
        self.assertTrue(result['ok']);self.assertIn({'name':'work','description':''},result['result']['actions'])
    def test_stop_blocks_sending(self):
        self.bridge('http')
        plan=self.tools.prepare('plugin_call',{'connection':'demo','function':'sum'})
        stop_automation()
        with self.assertRaises(PermissionError):self.tools.commit(plan)

    def test_rpc_failure_cannot_echo_authentication_token(self):
        from types import SimpleNamespace
        self.cfg['application_connections']['demo']={'transport':'tcp','port':1,'actions':['sum'],'token_env':'CHATAI_TEST_TOKEN'}
        self.tools.backend=SimpleNamespace(tcp=lambda entry,payload:{'id':payload['id'],'ok':False,'error':'rejected '+payload['token']})
        with patch.dict(os.environ,{'CHATAI_TEST_TOKEN':'test-secret-value'}):
            result=self.tools.commit(self.tools.prepare('plugin_call',{'connection':'demo','function':'sum'}))
        self.assertFalse(result['ok']);self.assertNotIn('test-secret-value',json.dumps(result))

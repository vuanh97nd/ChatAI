import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from assistant.browser import public_url, steps_from_json, BrowserTools
from assistant.online_automation import OnlineAutomation, search_call, requested_automation
from assistant.storage import Store
from assistant.windows_apps import resume_automation,stop_automation


class BrowserPolicyTest(unittest.TestCase):
    def setUp(self):resume_automation()
    def tearDown(self):resume_automation()
    def test_challenge_detection_and_search_engine(self):
        from assistant.browser import challenge_detected
        self.assertTrue(challenge_detected('https://www.google.com/sorry/index',''))
        self.assertTrue(challenge_detected('https://www.bing.com/turing/captcha',''))
        self.assertTrue(challenge_detected('https://www.bing.com/search?q=test','Verify you are human'))
        self.assertFalse(challenge_detected('https://example.org/article','Bài viết giải thích CAPTCHA và unusual traffic.'))
    def test_dependency_error_names_the_running_runtime(self):
        from assistant.browser import dependency_error
        import builtins
        original_import=builtins.__import__
        def unavailable(name,*args,**kwargs):
            if name=='playwright.sync_api':raise ModuleNotFoundError('missing')
            return original_import(name,*args,**kwargs)
        with patch('assistant.browser.os.name','nt'), patch('assistant.browser.sys.executable','/tmp/runtime/pythonw.exe'), patch('builtins.__import__',side_effect=unavailable):
            # Path selection on Linux must stay POSIX despite the mocked platform.
            with patch('assistant.browser.Path',__import__('pathlib').PosixPath):
                message=dependency_error()
        self.assertIn('/tmp/runtime/pythonw.exe',message)
        self.assertIn("& '/tmp/runtime/python.exe' -m pip install",message)
    def test_public_https_only(self):
        for url in ('file:///C:/secret','http://example.org','https://u:p@example.org','https://example.org:8443'):
            with self.assertRaises(ValueError):public_url(url)
        with patch('assistant.browser.socket.getaddrinfo',return_value=[(0,0,0,'',('127.0.0.1',443))]):
            with self.assertRaises(ValueError):public_url('https://example.org')
        with patch('assistant.browser.socket.getaddrinfo',return_value=[(0,0,0,'',('93.184.216.34',443))]):
            self.assertEqual(public_url('https://example.org'),'https://example.org')
    def test_steps_reject_code_and_unbounded_workflows(self):
        invalid=[[{'action':'evaluate','script':'alert(1)'}],[{'action':'read'}],
                 [{'action':'navigate','url':'file:///secret'}], [{'action':'read'}]*13]
        for steps in invalid:
            with self.assertRaises(ValueError):steps_from_json(json.dumps(steps))
    def test_browser_evidence_is_recognized_without_claiming_full_document(self):
        from assistant.answer_policy import evidence_record,guard_answer
        result={'ok':True,'results':[{'text':'Nguồn đã đọc','url':'https://example.org',
                                    'links':[{'url':'https://example.org/document'}]}]}
        state={'messages':[{'role':'user','content':'mở chrome'},
                           {'role':'tool','tool_name':'browser_search','content':json.dumps(result)}]}
        record=evidence_record(state,False)
        self.assertIn('https://example.org/document',record['urls'])
        self.assertEqual(record['coverage'],'partial')
        self.assertEqual(guard_answer('Đã tìm trên web.',state)[1],[])
    def test_saved_policy_and_executable_rechecked_before_launch(self):
        with tempfile.TemporaryDirectory() as folder, patch('assistant.browser.dependency_error',return_value=None):
            path=Path(folder)/'chrome.exe';path.write_bytes(b'fixture')
            cfg={'windows_apps_enabled':True,'windows_apps_allowed':[str(path)]}
            policy=Path(folder)/'config.json';policy.write_text(json.dumps(cfg))
            browser=BrowserTools(cfg,lambda *a:None,policy_path=policy)
            plan=browser.prepare('browser_search',{'path':str(path),'query':'tiêu chuẩn 41-2022'})
            self.assertIn('q=',plan['steps'][0]['url'])
            self.assertTrue(plan['steps'][0]['url'].startswith('https://www.bing.com/search?'))
            policy.write_text(json.dumps(dict(cfg,windows_apps_allowed=[])))
            with self.assertRaises(PermissionError):browser.commit(plan)
            policy.write_text(json.dumps(cfg));path.write_bytes(b'changed')
            with self.assertRaises(PermissionError):browser.commit(plan)
            stop_automation()
            with self.assertRaises(PermissionError):browser.prepare('browser_search',{'path':str(path),'query':'a'})


class OnlineAutomationTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'history.db')
        self.cid=self.store.create();self.state=self.store.load(self.cid)
        self.cfg={'windows_apps_enabled':True,'windows_apps_allowed':[r'C:\Apps\chrome.exe']}
        self.committed=[];self.requests=[];self.responses=[]
        def prepare(name,args):return {'action':name,**args}
        def commit(plan):self.committed.append(plan);return {'ok':True,'text':'Nguồn 41-2022','url':'https://example.org'}
        tools=SimpleNamespace(prepare=prepare,commit=commit)
        def chat(model,messages,**kwargs):
            self.requests.append(messages)
            return {'message':{'content':self.responses.pop(0)}}
        client=SimpleNamespace(model='deepseek',chat=chat)
        self.agent=OnlineAutomation(client,self.cfg,self.store,self.cid,tools,tools)
    def tearDown(self):self.tmp.cleanup()
    def test_one_time_permission_executes_without_step_dialog(self):
        self.cfg.update(windows_apps_enabled=True,windows_apps_auto_execute=True)
        self.agent.windows.check=lambda:dict(self.cfg)
        self.agent.start(self.state,'mở Word','DeepSeek API','admin')
        self.responses=[json.dumps({'answer':'Đã kiểm tra danh sách','tool':'','arguments':{}})]
        events=list(self.agent.run(self.state))
        self.assertFalse(any(e['type']=='pending' for e in events))
        self.assertEqual(self.committed[0]['action'],'windows_list_apps')
        self.assertIsNone(self.state['pending'])

    def test_previously_pending_step_uses_permission_granted_later(self):
        self.cfg.update(windows_apps_enabled=True)
        self.agent.windows.check=lambda:dict(self.cfg)
        self.agent.start(self.state,'mở Word','DeepSeek API','admin')
        self.assertEqual(list(self.agent.run(self.state))[-1]['type'],'pending')
        self.cfg['windows_apps_auto_execute']=True
        self.responses=[json.dumps({'answer':'Đã kiểm tra','tool':'','arguments':{}})]
        events=list(self.agent.run(self.state))
        self.assertFalse(any(e['type']=='pending' for e in events))
        self.assertEqual(len(self.committed),1)

    def test_revoking_one_time_permission_restores_step_approval(self):
        self.cfg.update(windows_apps_enabled=True,windows_apps_auto_execute=True)
        self.agent.windows.check=lambda:{'windows_apps_enabled':True,'windows_apps_auto_execute':False}
        self.agent.start(self.state,'mở Word','DeepSeek API','admin')
        self.assertEqual(list(self.agent.run(self.state))[-1]['type'],'pending')
        self.assertEqual(self.committed,[])

    def test_deepseek_cad_plan_uses_saved_permission(self):
        self.cfg.update(windows_apps_enabled=True,windows_apps_auto_execute=True)
        self.agent.windows.check=lambda:dict(self.cfg)
        self.agent.cad_app=self.agent.windows
        from assistant.tools import EXTRA_TOOLS
        self.agent.schemas.extend(s for m,s in EXTRA_TOOLS if m=='cad_app')
        self.responses=[json.dumps({'answer':'','tool':'cad_create_open','arguments':{'app':r'C:\CAD\acad.exe','units':'mm','entities':[{'type':'circle','center':[0,0],'radius':50}]}}),
                        json.dumps({'answer':'Đã tạo bản vẽ','tool':'','arguments':{}})]
        self.agent.start(self.state,'Vẽ đường tròn bán kính 50 mm trong AutoCAD','DeepSeek API','admin')
        events=list(self.agent.run(self.state))
        self.assertFalse(any(e['type']=='pending' for e in events))
        self.assertEqual(self.committed[0]['action'],'cad_create_open')
        self.assertEqual(json.loads(self.committed[0]['entities'])[0]['radius'],50)

    def test_song_name_reply_stays_in_online_tool_workflow(self):
        from assistant.online_automation import use_automation
        cfg={'windows_apps_enabled':True}
        self.assertTrue(use_automation('tình yêu màu nắng',cfg,{'online_automation':True}))
        self.assertFalse(use_automation('tình yêu màu nắng',cfg,{}))
        self.assertFalse(use_automation('tình yêu màu nắng',{'windows_apps_enabled':False},{'online_automation':True}))

    def test_registered_word_is_discovered_before_model_or_launch(self):
        self.cfg.update(windows_apps_enabled=True,windows_apps_all_installed=True)
        self.agent.start(self.state,'hãy mở word và viết một bài văn tả mẹ','DeepSeek API','admin')
        self.assertEqual(list(self.agent.run(self.state))[-1]['type'],'pending')
        self.assertEqual(self.state['pending']['plan'],{'action':'windows_list_apps','query':'word'})
        self.assertEqual(self.requests,[])
        self.assertEqual(self.committed,[])
        self.agent.approve(self.state,True,self.state['pending'])
        self.responses=[json.dumps({'answer':'','tool':'windows_open','arguments':{'path':r'C:\Office\WINWORD.EXE'}})]
        self.assertEqual(list(self.agent.run(self.state))[-1]['type'],'pending')
        self.assertEqual(self.state['pending']['plan']['action'],'windows_open')
        self.assertIn('KHÔNG phải toàn bộ',self.requests[-1][0]['content'])

    def test_generic_app_discovery_respects_negative_requests(self):
        from assistant.online_automation import application_call
        cfg={'windows_apps_enabled':True,'windows_apps_all_installed':True}
        for app in ('Excel','Photoshop','Foxit PDF Editor','Chrome'):
            self.assertEqual(application_call('hãy mở '+app+' và làm việc',cfg)['function']['arguments']['query'],app)
        for prompt in ('đừng mở Word','cách mở Word','mở rộng ý tưởng'):
            self.assertIsNone(application_call(prompt,cfg))
        self.assertIsNone(application_call('mở Word',{}))

    def test_chrome_search_routes_without_model_and_approval_is_required(self):
        self.agent.start(self.state,'hãy mở ứng dụng chorme và tìm kiếm thông tin về tiêu chuẩn 41-2022','DeepSeek API','admin')
        events=list(self.agent.run(self.state))
        self.assertEqual(events[-1]['type'],'pending');self.assertEqual(self.requests,[]);self.assertEqual(self.committed,[])
        pending=self.state['pending']
        self.agent.approve(self.state,True,pending)
        self.assertEqual(len(self.committed),1)
        self.responses=[json.dumps({'answer':'Đã tìm thấy nguồn: https://example.org','tool':'','arguments':'{}'})]
        events=list(self.agent.run(self.state))
        self.assertIn('https://example.org',events[-1]['text'])
        self.assertTrue(any('Nguồn 41-2022' in m['content'] for m in self.requests[0]))
        self.assertFalse(self.state['running'])
    def test_deepseek_can_plan_windows_app_action_without_ollama(self):
        self.responses=[json.dumps({'answer':'','tool':'windows_open','arguments':json.dumps({'path':r'C:\Apps\word.exe'})})]
        self.agent.start(self.state,'Tiếp tục mở ứng dụng Word','DeepSeek API','admin')
        self.assertEqual(list(self.agent.run(self.state))[-1]['type'],'pending')
        self.assertIn('windows_inspect',self.requests[0][0]['content'])
        self.assertEqual(self.committed,[])
        self.agent.approve(self.state,False,self.state['pending'])
        self.assertEqual(self.committed,[])
        self.assertIn('từ chối',self.state['messages'][-1]['content'])
    def test_invalid_model_tools_never_execute(self):
        self.responses=[json.dumps({'answer':'','tool':'run_command','arguments':'{"command":"bad"}'})]*2
        self.agent.start(self.state,'Tiếp tục mở ứng dụng Word','DeepSeek API','admin')
        list(self.agent.run(self.state))
        self.assertFalse(self.state['running']);self.assertEqual(self.committed,[])
    def test_markdown_and_object_arguments_are_accepted_but_wait_for_approval(self):
        self.responses=['```json\n'+json.dumps({'tool':'windows_open','arguments':{'path':r'C:\Apps\word.exe'}})+'\n```']
        self.agent.start(self.state,'Tiếp tục mở ứng dụng Word','DeepSeek API','admin')
        self.assertEqual(list(self.agent.run(self.state))[-1]['type'],'pending')
        self.assertEqual(self.committed,[])
    def test_invalid_json_is_repaired_before_any_side_effect(self):
        self.responses=['Để tôi mở Word.',json.dumps({'answer':'','tool':'windows_open','arguments':{'path':r'C:\Apps\word.exe'}})]
        self.agent.start(self.state,'Tiếp tục mở ứng dụng Word','DeepSeek API','admin')
        events=list(self.agent.run(self.state))
        self.assertTrue(any('sửa định dạng' in event.get('text','') for event in events))
        self.assertEqual(events[-1]['type'],'pending');self.assertEqual(self.committed,[])
        self.assertEqual(len(self.requests),2)
    def test_local_model_chrome_search_also_waits_for_approval(self):
        import test_app as fixtures
        from assistant.agent import Agent
        from assistant.tools import EXTRA_TOOLS
        cfg=dict(self.cfg,roots=[],num_ctx=4096,num_predict=500,max_rounds=4)
        tools=SimpleNamespace(schemas=[s for m,s in EXTRA_TOOLS if m=='browser'],
            prepare=lambda name,args:{'action':name,**args},commit=lambda plan:self.committed.append(plan))
        agent=Agent(fixtures.FakeClient([]),None,cfg,self.store,self.cid,tools)
        agent.start(self.state,'Mở Chrome và tìm thông tin tiêu chuẩn 41-2022','qwen3:8b')
        self.assertEqual(list(agent.run(self.state))[-1]['type'],'pending')
        self.assertEqual(self.state['pending']['plan']['action'],'browser_search')
        self.assertEqual(self.committed,[])
    def test_stale_or_started_approval_cannot_execute_twice(self):
        self.agent.start(self.state,'mở chrome và tìm thông tin abc','DeepSeek API','admin')
        list(self.agent.run(self.state));pending=self.state['pending']
        with self.assertRaises(RuntimeError):self.agent.approve(self.state,True,{})
        pending['decision_started']=True
        with self.assertRaises(RuntimeError):self.agent.approve(self.state,True,pending)
        self.assertEqual(self.committed,[])
    def test_intent_excludes_discussion_and_preserves_exact_query(self):
        self.assertTrue(requested_automation('Mở Word và đọc giao diện'))
        self.assertTrue(requested_automation('Hãy mở Photoshop'))
        self.assertFalse(requested_automation('Hãy mở rộng giải thích về vật lý'))
        self.assertFalse(requested_automation('Tiêu chuẩn 41-2022 là gì'))
        self.assertIsNone(search_call('Đừng mở chrome và tìm abc',self.cfg))
        self.assertIsNone(search_call('Cách mở chrome và tìm abc',self.cfg))
        call=search_call('Mở Chrome và tìm kiếm thông tin về tiêu chuẩn 41-2022',self.cfg)
        self.assertEqual(call['function']['arguments']['query'],'tiêu chuẩn 41-2022')

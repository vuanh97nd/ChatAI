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

    def test_explicit_task_grant_executes_model_proposal_without_confirmation(self):
        self.cfg['ai_tools_auto_execute']=True
        self.agent.windows.check=lambda:dict(self.cfg)
        self.responses=[json.dumps({'tool':'windows_open','arguments':{'path':r'C:\Apps\word.exe'}}),
                        json.dumps({'answer':'Đã kiểm tra kết quả.','tool':'','arguments':{}})]
        self.agent.start(self.state,'Tiếp tục','DeepSeek Flash','admin')
        events=list(self.agent.run(self.state))
        self.assertFalse(any(e['type']=='pending' for e in events))
        self.assertEqual(self.committed[0]['action'],'windows_open')
        self.assertFalse(self.state['running'])

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

    def test_fully_specified_circle_executes_without_model_rounds(self):
        self.cfg.update(windows_apps_enabled=True,windows_apps_auto_execute=True,windows_apps_allowed=[r'C:\CAD\acad.exe'])
        self.agent.windows.check=lambda:dict(self.cfg)
        self.agent.cad_app=SimpleNamespace(prepare=lambda name,args:{'action':name,**args},commit=lambda plan:{'ok':True,'document_created':True,'path':'drawing.dxf'})
        from assistant.tools import EXTRA_TOOLS
        self.agent.schemas.extend(s for m,s in EXTRA_TOOLS if m=='cad_app')
        self.agent.start(self.state,'Vẽ trong AutoCAD đường tròn tâm (0,0), bán kính 50 mm','DeepSeek API','admin')
        list(self.agent.run(self.state))
        self.assertEqual(self.requests,[])
        self.assertFalse(self.state['running'])
        self.assertIn('drawing.dxf',self.state['messages'][-1]['content'])
        from assistant.online_automation import drawing_call
        self.assertIsNone(drawing_call('Vẽ trong AutoCAD đường tròn bán kính 50 mm',self.cfg))
        self.assertIsNone(drawing_call('Đừng vẽ đường tròn tâm (0,0), bán kính 50 mm',self.cfg))

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

    def test_3d_flange_plan_uses_saved_permission_without_extra_dialog(self):
        self.cfg.update(windows_apps_enabled=True,windows_apps_auto_execute=True)
        self.agent.windows.check=lambda:dict(self.cfg)
        self.agent.cad3d_app=self.agent.windows
        from assistant.tools import EXTRA_TOOLS
        self.agent.schemas.extend(s for m,s in EXTRA_TOOLS if m=='cad3d_app')
        shape={'type':'flange','origin':[0,0,0],'outer_radius':120,'inner_radius':40,'height':20,'hole_radius':9,'hole_count':8,'bolt_radius':90}
        self.responses=[json.dumps({'answer':'','tool':'cad3d_create_open','arguments':{'app':r'C:\CAD\acad.exe','units':'mm','shape':shape}}),
                        json.dumps({'answer':'Đã tạo lưới 3D','tool':'','arguments':{}})]
        prompt='Tạo mặt bích 3D trong AutoCAD'
        self.assertTrue(requested_automation('Tạo mặt bích 3D'))
        self.agent.start(self.state,prompt,'DeepSeek API','admin')
        events=list(self.agent.run(self.state))
        self.assertFalse(any(e['type']=='pending' for e in events))
        self.assertEqual(self.committed[0]['action'],'cad3d_create_open')
        self.assertEqual(json.loads(self.committed[0]['shape']),shape)

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

    def test_search_discovery_separates_app_and_task_when_chrome_paths_are_ambiguous(self):
        from assistant.online_automation import application_call
        cfg={'windows_apps_enabled':True,'windows_apps_allowed':[r'C:\Apps\Chrome\chrome.exe',r'D:\Apps\Chrome\chrome.exe']}
        for app in ('chrome','chorme','google chrome','google chorme'):
            prompt='Hãy mở '+app+' tìm tiêu chuẩn 41-2022 và tóm tắt'
            self.assertIsNone(search_call(prompt,cfg))
            self.assertEqual(application_call(prompt,cfg)['function']['arguments']['query'],'Chrome')

    def test_chrome_path_aliases_and_summary_instruction_do_not_pollute_search(self):
        cfg={'windows_apps_enabled':True,'windows_apps_allowed':[r'C:\Apps\Chrome\chrome.exe','C:/Apps/Chrome/chrome.exe']}
        call=search_call('Hãy mở google chorme tìm tiêu chuẩn 41-2022 và tóm tắt',cfg)
        self.assertEqual(call['function']['name'],'browser_search')
        self.assertEqual(call['function']['arguments']['query'],'tiêu chuẩn 41-2022')

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

    def test_two_plain_plans_recover_in_separate_request_before_execution(self):
        self.responses=['Tôi sẽ mở Word.','Tôi sẽ tiếp tục mở Word.',
                        json.dumps({'tool':'windows_open','arguments':{'path':r'C:\Apps\word.exe'}})]
        self.agent.start(self.state,'Tiếp tục','DeepSeek Flash','admin')
        events=list(self.agent.run(self.state))
        self.assertEqual(events[-1]['type'],'pending')
        self.assertEqual(self.committed,[])
        self.assertEqual(len(self.requests),3)
        self.assertEqual(len(self.requests[2]),2)
        self.assertTrue(any('JSON riêng' in e.get('text','') for e in events))

    def test_yes_keeps_recent_proposal_in_planning_context(self):
        self.state['messages']=[{'role':'assistant','content':'Tôi sẽ tìm hướng dẫn Seequent bằng Chrome. Bạn đồng ý không?'}]
        self.responses=[json.dumps({'answer':'Cần kiểm tra Chrome.','tool':'','arguments':{}})]
        self.agent.start(self.state,'có','DeepSeek Flash','admin')
        list(self.agent.run(self.state))
        self.assertIn('Seequent',self.requests[0][0]['content'])
        self.assertIn('vừa chấp thuận',self.requests[0][0]['content'])
    def test_truncated_plan_retries_with_larger_budget_before_execution(self):
        budgets=[]
        def chat(model,messages,**kwargs):
            budgets.append(kwargs['options']['num_predict'])
            if len(budgets)==1:return {'truncated':True,'message':{'content':'{"answer":'}}
            return {'message':{'content':json.dumps({'answer':'Đã hiểu','tool':'','arguments':{}})}}
        self.agent.client.chat=chat
        self.agent.start(self.state,'Tiếp tục','DeepSeek Flash','admin')
        list(self.agent.run(self.state))
        self.assertEqual(budgets,[4096,8192])
        self.assertEqual(self.committed,[])
        self.assertEqual(self.state['messages'][-1]['content'],'Đã hiểu')

    def test_plain_help_request_is_shown_after_format_repair_fails(self):
        self.responses=['Bạn cần tính bài toán nào?']*2
        self.agent.start(self.state,'Tiếp tục','DeepSeek Flash','admin')
        events=list(self.agent.run(self.state))
        self.assertFalse(self.state['running'])
        self.assertEqual(self.committed,[])
        self.assertIn('Bạn cần tính bài toán nào?',events[-1]['text'])
        self.assertIn('chưa thực hiện thao tác',events[-1]['text'])
        self.assertNotIn('AI chưa trả kế hoạch hợp lệ',events[-1]['text'])
        self.assertIn('trợ giúp',self.requests[0][0]['content'])

    def test_preparation_error_is_replanned_before_any_execution(self):
        attempts=[]
        def prepare(name,args):
            attempts.append(args['path'])
            if args['path'].endswith('missing.exe'):raise ValueError('EXE không tồn tại')
            return {'action':name,**args}
        self.agent.windows.prepare=prepare
        self.responses=[json.dumps({'answer':'','tool':'windows_open','arguments':{'path':r'C:\Apps\missing.exe'}}),
                        json.dumps({'answer':'','tool':'windows_open','arguments':{'path':r'C:\Apps\chrome.exe'}})]
        self.agent.start(self.state,'Tiếp tục','DeepSeek Flash','admin')
        events=list(self.agent.run(self.state))
        self.assertEqual(len(attempts),2)
        self.assertTrue(any('sửa kế hoạch' in e.get('text','') for e in events))
        self.assertEqual(self.committed,[])
        self.assertEqual(self.state['pending']['plan']['path'],r'C:\Apps\chrome.exe')

    def test_known_plaxis_material_error_regenerates_exact_problem_once(self):
        args={'version':'2d','problem':'{"type":"slope_stability"}','project_name':'Test'}
        prepared=[];committed=[]
        def prepare(name,received):
            prepared.append(received);return {'action':name,'script':'corrected script'}
        def commit(plan):
            committed.append(plan['script'])
            if len(committed)==1:return {'ok':False,'error':'InitialPhase Soil has no material assigned'}
            return {'ok':True,'note':'Đã tính'}
        self.agent.plaxis_remote=SimpleNamespace(prepare=prepare,commit=commit)
        self.state.update(running=True,queue=[{'function':{'name':'plaxis_run_problem','arguments':args}}],
                          pending={'plan':{'action':'plaxis_run_problem','script':'old script'},'decision_started':False})
        self.agent.approve(self.state,True,self.state['pending'])
        self.assertEqual(prepared,[args]);self.assertEqual(committed,['old script','corrected script'])
        self.assertFalse(self.state['running']);self.assertEqual(self.state['plaxis_repairs'],1)

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

    def test_cdm_layout_call_extracts_all_params(self):
        from assistant.online_automation import cdm_layout_call
        cfg={'windows_apps_enabled':True,'windows_apps_allowed':[r'C:\CAD\acad.exe']}
        prompt='Vẽ bố trí cọc CDM B=12m L=100m D=0.8m H=12m lưới 2×2m trong AutoCAD'
        call=cdm_layout_call(prompt,cfg)
        self.assertIsNotNone(call)
        self.assertEqual(call['function']['name'],'cad_cdm_layout')
        args=call['function']['arguments']
        self.assertEqual(args['b_road'],12.0)
        self.assertEqual(args['l_treatment'],100.0)
        self.assertEqual(args['d_pile'],0.8)
        self.assertEqual(args['pile_depth'],12.0)
        self.assertEqual(args['spacing_x'],2.0)
        self.assertEqual(args['spacing_y'],2.0)

    def test_cdm_layout_call_returns_none_without_cdm_keyword(self):
        from assistant.online_automation import cdm_layout_call
        cfg={'windows_apps_enabled':True,'windows_apps_allowed':[r'C:\CAD\acad.exe']}
        self.assertIsNone(cdm_layout_call('Vẽ bố trí cọc B=12m L=100m D=0.8m H=12m lưới 2×2m',cfg))
        self.assertIsNone(cdm_layout_call('Vẽ CDM B=12m',cfg))  # missing params

    def test_cdm_layout_call_returns_none_when_windows_disabled(self):
        from assistant.online_automation import cdm_layout_call
        cfg={'windows_apps_enabled':False,'windows_apps_allowed':[r'C:\CAD\acad.exe']}
        prompt='Vẽ bố trí cọc CDM B=12m L=100m D=0.8m H=12m lưới 2×2m'
        self.assertIsNone(cdm_layout_call(prompt,cfg))

    def test_cdm_layout_in_schemas_when_cdm_layout_passed(self):
        from assistant.tools import EXTRA_TOOLS
        from assistant.online_automation import OnlineAutomation
        from types import SimpleNamespace
        tools=SimpleNamespace(prepare=lambda n,a:{'action':n,**a},commit=lambda p:{'ok':True})
        agent=OnlineAutomation(None,{},self.store,self.cid,tools,tools,cdm_layout=tools)
        names=[s['function']['name'] for s in agent.schemas]
        self.assertIn('cad_cdm_layout',names)

    def test_cdm_layout_not_in_schemas_when_not_passed(self):
        from assistant.online_automation import OnlineAutomation
        from types import SimpleNamespace
        tools=SimpleNamespace(prepare=lambda n,a:{'action':n,**a},commit=lambda p:{'ok':True})
        agent=OnlineAutomation(None,{},self.store,self.cid,tools,tools)
        names=[s['function']['name'] for s in agent.schemas]
        self.assertNotIn('cad_cdm_layout',names)

class AutomationImageTests(unittest.TestCase):
    def encoded(self,color='white'):
        import base64,io
        from PIL import Image
        out=io.BytesIO();Image.new('RGB',(16,16),color).save(out,format='JPEG')
        return base64.b64encode(out.getvalue()).decode()
    def test_latest_image_is_forwarded_without_text_truncation(self):
        from assistant.online_automation import planning_messages
        first=self.encoded();second=self.encoded('red')
        state={'messages':[{'role':'user','content':'ảnh trước','images':[first]},
                           {'role':'assistant','content':'Đã đọc'},
                           {'role':'user','content':'rồi nhé','images':[second]},
                           {'role':'tool','tool_name':'windows_inspect','content':'đã kiểm tra'}]}
        messages=planning_messages(state,'Chỉ dẫn hệ thống')
        images=[part for m in messages if isinstance(m['content'],list) for part in m['content'] if part['type']=='image_url']
        self.assertEqual(len(images),1)
        self.assertEqual(images[0]['image_url']['url'],'data:image/jpeg;base64,'+second)
        self.assertEqual(messages[3]['content'][0]['text'],'rồi nhé')
    def test_invalid_or_oversized_image_is_rejected(self):
        from assistant.online_automation import image_message_content
        for value in ('https://example.org/image.jpg','abc', 'A'*1400000):
            with self.assertRaises(ValueError):image_message_content('test',value)
    def test_image_is_saved_and_planned_before_direct_app_action(self):
        from assistant.online_automation import OnlineAutomation
        with tempfile.TemporaryDirectory() as td:
            store=Store(Path(td)/'history.db');cid=store.create();state=store.load(cid)
            calls=[]
            def chat(model,messages,**kw):
                calls.append(messages)
                return {'message':{'content':json.dumps({'answer':'Tôi đã xem ảnh bạn gửi.','tool':'','arguments':{}})}}
            client=SimpleNamespace(model='deepseek_flash',chat=chat)
            tools=SimpleNamespace()
            agent=OnlineAutomation(client,{},store,cid,tools,tools)
            encoded=self.encoded()
            from assistant.automation_start import start_automation
            start_automation(agent,state,'mở word theo ảnh này','DeepSeek Flash','admin',image=encoded)
            self.assertEqual(state['queue'],[])
            self.assertEqual(store.load(cid)['messages'][-1]['images'],[encoded])
            list(agent.run(state))
            self.assertTrue(any(isinstance(m['content'],list) for m in calls[0]))
            self.assertEqual(state['messages'][-1]['content'],'Tôi đã xem ảnh bạn gửi.')


class EmptyPlanResponseTests(unittest.TestCase):
    """An empty provider response must not surface the raw server error to the user."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'history.db')
        self.cid=self.store.create();self.state=self.store.load(self.cid)
        tools=SimpleNamespace(prepare=lambda name,args:{'action':name,**args},commit=lambda plan:{'ok':True})
        self.tools=tools
    def tearDown(self):self.tmp.cleanup()

    def agent_for(self,chat):
        return OnlineAutomation(SimpleNamespace(model='deepseek',chat=chat),{},self.store,self.cid,self.tools,self.tools)

    def test_empty_response_retries_without_json_mode(self):
        from assistant.cloud import CloudError
        formats=[]
        def chat(model,messages,**kwargs):
            formats.append(kwargs.get('format'))
            if len(formats)==1:raise CloudError('API đã nhận yêu cầu nhưng trả văn bản rỗng.')
            return {'message':{'content':json.dumps({'answer':'Bạn cần PLAXIS 2D hay 3D?','tool':'','arguments':'{}'})}}
        agent=self.agent_for(chat)
        agent.start(self.state,'chạy plaxis','DeepSeek API','admin')
        events=list(agent.run(self.state))
        self.assertEqual(len(formats),2)
        self.assertIsNone(formats[1])
        self.assertEqual(self.state['messages'][-1]['content'],'Bạn cần PLAXIS 2D hay 3D?')
        self.assertTrue(any('PLAXIS' in e.get('text','') for e in events if e['type']=='token'))

    def test_persistent_empty_response_ends_with_a_message(self):
        from assistant.cloud import CloudError
        def chat(model,messages,**kwargs):raise CloudError('API đã nhận yêu cầu nhưng trả văn bản rỗng.')
        agent=self.agent_for(chat)
        agent.start(self.state,'chào bạn','DeepSeek API','admin')
        events=list(agent.run(self.state))
        self.assertFalse(self.state['running'])
        self.assertTrue([e for e in events if e['type']=='token'])

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from assistant.windows_apps import WindowsApps, validate_settings, stop_automation, resume_automation
from assistant.tools import EXTRA_TOOLS, WRITES, validate_call


class FakeBackend:
    def __init__(self):
        self.actions=[];self.launches=[];self.valid=True
        self.window=self.control('Demo', 'Window', 1)
        self.button=self.control('Run test', 'Button', 2)
        self.edit=self.control('Input', 'Edit', 3)
        self.password=self.control('secret password', 'Edit', 4, password=True)
        self.foreign=self.control('Other app', 'Button', 5, pid=99)
        self.window.children=[self.button,self.edit,self.password,self.foreign]
    def control(self,name,kind,identity,password=False,pid=42):
        return SimpleNamespace(description={'name':name,'type':kind,'identity':(identity,),
                                          'password':password,'pid':pid},children=[])
    def launch(self,path):self.launches.append(path);return 42,123
    def windows(self,session):
        if not self.valid:raise PermissionError('PID changed')
        return [self.window]
    def describe(self,control):return dict(control.description)
    def children(self,control):return control.children
    def action(self,control,operation,text):self.actions.append((control,operation,text))


class WindowsAppsTest(unittest.TestCase):
    def setUp(self):
        resume_automation()
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.exe=self.root/'demo.exe';self.exe.write_bytes(b'test executable fixture')
        self.cfg={'windows_apps_enabled':True,'windows_apps_allowed':[str(self.exe)]}
        self.backend=FakeBackend();self.events=[]
        self.tools=WindowsApps(self.cfg,lambda *row:self.events.append(row),owner='alice',backend=self.backend)
    def tearDown(self):resume_automation();self.tmp.cleanup()
    def open(self):return self.tools.commit(self.tools.prepare('windows_open',{'path':str(self.exe)}))['session']
    def inspect(self,session):return self.tools.commit(self.tools.prepare('windows_inspect',{'session':session}))['controls']
    def test_launch_has_no_side_effect_until_approved(self):
        plan=self.tools.prepare('windows_open',{'path':str(self.exe)})
        self.assertEqual(self.backend.launches,[])
        self.assertTrue(self.tools.commit(plan)['ok']);self.assertEqual(self.backend.launches,[self.exe])
    def test_unlisted_or_changed_executable_rejected(self):
        other=self.root/'other.exe';other.write_bytes(b'other')
        with self.assertRaises(PermissionError):self.tools.prepare('windows_open',{'path':str(other)})
        plan=self.tools.prepare('windows_open',{'path':str(self.exe)});self.exe.write_bytes(b'changed')
        with self.assertRaises(PermissionError):self.tools.commit(plan)
        self.assertEqual(self.backend.launches,[])
    def test_inspect_redacts_password_and_excludes_other_process(self):
        rows=self.inspect(self.open())
        self.assertEqual([r['name'] for r in rows],['Demo','Run test','Input'])
        self.assertNotIn('secret password',json.dumps(rows))
    def test_click_requires_fresh_target_and_followup_inspection(self):
        session=self.open();rows=self.inspect(session)
        plan=self.tools.prepare('windows_action',{'session':session,'control':rows[1]['control'],'operation':'click'})
        self.assertEqual(self.backend.actions,[])
        self.assertTrue(self.tools.commit(plan)['ok']);self.assertEqual(len(self.backend.actions),1)
        with self.assertRaises(PermissionError):self.tools.commit(plan)
    def test_changed_or_removed_control_is_not_clicked(self):
        session=self.open();rows=self.inspect(session)
        plan=self.tools.prepare('windows_action',{'session':session,'control':rows[1]['control'],'operation':'click'})
        self.backend.window.children=[]
        with self.assertRaises(PermissionError):self.tools.commit(plan)
        self.assertEqual(self.backend.actions,[])
    def test_text_is_limited_to_edit_and_password_controls_are_denied(self):
        session=self.open();rows=self.inspect(session)
        with self.assertRaises(PermissionError):self.tools.prepare('windows_action',{'session':session,'control':rows[1]['control'],'operation':'set_text','text':'hello'})
        plan=self.tools.prepare('windows_action',{'session':session,'control':rows[2]['control'],'operation':'set_text','text':'hello'})
        self.backend.edit.description['password']=True
        with self.assertRaises(PermissionError):self.tools.commit(plan)
        self.assertEqual(self.backend.actions,[])
    def test_owner_pid_and_stop_revalidated_after_approval(self):
        session=self.open();plan=self.tools.prepare('windows_inspect',{'session':session})
        other=WindowsApps(self.cfg,lambda *args:None,owner='bob',backend=self.backend)
        with self.assertRaises(PermissionError):other.prepare('windows_inspect',{'session':session})
        self.backend.valid=False
        with self.assertRaises(PermissionError):self.tools.commit(plan)
        self.backend.valid=True;stop_automation()
        with self.assertRaises(PermissionError):self.tools.commit(plan)
        resume_automation();self.assertTrue(self.tools.commit(plan)['ok'])
    def test_current_saved_policy_revocation_blocks_pending_plan(self):
        policy=self.root/'config.json';policy.write_text(json.dumps(self.cfg))
        self.tools.policy_path=policy
        plan=self.tools.prepare('windows_open',{'path':str(self.exe)})
        policy.write_text(json.dumps(dict(self.cfg,windows_apps_allowed=[])))
        with self.assertRaises(PermissionError):self.tools.commit(plan)
        self.assertEqual(self.backend.launches,[])
    def test_settings_default_disabled_and_validate_paths(self):
        cfg={};validate_settings(cfg);self.assertFalse(cfg['windows_apps_enabled'])
        validate_settings({'windows_apps_enabled':True,'windows_apps_allowed':[r'C:\Apps\demo.exe']})
        for cfg in [{'windows_apps_enabled':'yes'}, {'windows_apps_allowed':['cmd']},
                    {'windows_apps_allowed':[r'\\server\share\demo.exe']},
                    {'windows_apps_allowed':[r'C:\demo.bat']}]:
            with self.assertRaises(ValueError):validate_settings(cfg)
    def test_registry_requires_approval_and_rejects_shell_arguments(self):
        specs=[s for module,s in EXTRA_TOOLS if module=='windows']
        self.assertEqual({s['function']['name'] for s in specs},{'windows_open','windows_inspect','windows_action','windows_list_apps'})
        self.assertTrue(all(s['function']['name'] in WRITES for s in specs))
        with self.assertRaises(ValueError):validate_call('windows_open',{'path':'demo.exe','args':'/c command'},specs)
        with self.assertRaises(ValueError):self.tools.prepare('windows_action',{'session':self.open(),'control':'bad','operation':'shell'})


class WindowsAgentApprovalTest(unittest.TestCase):
    def test_agent_never_auto_approves_app_launch(self):
        import test_app as fixtures
        from assistant.agent import Agent
        from assistant.storage import Store
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'demo.exe';path.write_bytes(b'fixture')
            backend=FakeBackend();cfg={'windows_apps_enabled':True,'windows_apps_allowed':[str(path)],
                'roots':[],'num_ctx':4096,'num_predict':500,'max_rounds':4,'auto_python':True}
            tools=WindowsApps(cfg,lambda *args:None,owner='approval-test',backend=backend)
            caps=SimpleNamespace(schemas=[s for module,s in EXTRA_TOOLS if module=='windows'],
                prepare=tools.prepare,commit=tools.commit)
            client=fixtures.FakeClient([[fixtures.chunk(calls=[fixtures.FakeCall('windows_open',{'path':str(path)})])]])
            store=Store(Path(folder)/'history.db');cid=store.create();state=store.load(cid)
            agent=Agent(client,None,cfg,store,cid,caps)
            agent.start(state,'Mở app demo được phép','qwen2.5:7b')
            events=list(agent.run(state))
            self.assertTrue(any(e['type']=='pending' for e in events))
            self.assertEqual(backend.launches,[])
            agent.approve(state,False)
            self.assertEqual(backend.launches,[])
            self.assertIn('từ chối',state['messages'][-1]['content'])


class UIAPatternTest(unittest.TestCase):
    def test_readiness_reports_missing_libraries_and_permissions(self):
        from unittest.mock import patch
        from assistant.windows_apps import readiness
        resume_automation()
        with patch('assistant.windows_apps.os.name','nt'), patch('assistant.windows_apps.importlib.util.find_spec',return_value=None):
            self.assertIn('requirements-windows-automation.txt',readiness({}))
        with patch('assistant.windows_apps.os.name','nt'), patch('assistant.windows_apps.importlib.util.find_spec',return_value=object()):
            self.assertIn('Chưa bật quyền',readiness({}))
            self.assertIn('Chưa có app',readiness({'windows_apps_enabled':True}))
            cfg={'windows_apps_enabled':True,'windows_apps_allowed':['demo.exe']}
            self.assertIn('Sẵn sàng',readiness(cfg))
            stop_automation()
            try:self.assertIn('đang dừng',readiness(cfg))
            finally:resume_automation()

    def test_actions_use_only_targeted_patterns(self):
        from assistant.windows_apps import WindowsBackend
        actions=[]
        control=SimpleNamespace(
            iface_invoke=SimpleNamespace(Invoke=lambda:actions.append('click')),
            iface_value=SimpleNamespace(CurrentIsReadOnly=False,SetValue=lambda text:actions.append(text)),
            iface_window=SimpleNamespace(Close=lambda:actions.append('close')))
        backend=WindowsBackend()
        backend.action(control,'click','');backend.action(control,'set_text','hello');backend.action(control,'close','')
        self.assertEqual(actions,['click','hello','close'])
        control.iface_value.CurrentIsReadOnly=True
        with self.assertRaises(PermissionError):backend.action(control,'set_text','changed')
        self.assertEqual(actions,['click','hello','close'])

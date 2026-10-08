import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch


class LoginLatencyTest(unittest.TestCase):
    def methods(self,*names):
        source=ast.parse((Path(__file__).parents[1]/'desktop_ui.py').read_text())
        window=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='Window')
        module=ast.Module(body=[n for n in window.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
        namespace={'time':__import__('time'),'measure':__import__('assistant.performance',fromlist=['measure']).measure,'record':__import__('assistant.performance',fromlist=['record']).record};exec(compile(ast.fix_missing_locations(module),'login-test','exec'),namespace)
        return namespace

    def test_login_critical_path_only_authenticates_not_optional_requests(self):
        methods=self.methods('perform_login')
        captured={}
        def work(fn,callback):captured.update(task=fn,done=callback)
        host=SimpleNamespace(account_status=Mock(),device_id='fixture',cfg={'custom_ai':[]},store=Mock(),trial=Mock(),worker=Mock(),work=work)
        session={'endpoint':'https://example.org','username':'alice','key':'fixture'}
        methods['perform_login'](host,session)
        with patch('assistant.accounts.request_account',return_value={'success':True,'session_token':'new-token','role':'user','fullname':'Alice'}) as request,patch('assistant.accounts.save_login'),patch('assistant.model_preferences.load_model',return_value='DeepSeek API'):
            result=captured['task'](Mock())
        self.assertEqual(request.call_count,1)
        self.assertEqual(request.call_args.args[1],'/api/login')
        self.assertEqual(session['key'],'new-token')
        self.assertEqual(result[0]['fullname'],'Alice')
        host.trial.adopt.assert_called_once_with('alice')
        timings=result[0]['_login_timings']
        self.assertEqual(set(timings),{'server_seconds','local_seconds'})
        self.assertTrue(all(isinstance(v,(int,float)) and v>=0 for v in timings.values()))

    def test_late_enrichment_cannot_modify_new_login_or_role(self):
        methods=self.methods('apply_account_enrichment')
        current={'endpoint':'https://example.org','username':'alice','key':'new','role':'user'}
        host=SimpleNamespace(server_session=current,refresh_account_ui=Mock())
        old=dict(current,key='old')
        result={'section':'profile','result':{'profile':{'fullname':'Stale','role':'admin'}}}
        methods['apply_account_enrichment'](host,old,result)
        self.assertNotIn('fullname',current)
        methods['apply_account_enrichment'](host,dict(current),result)
        self.assertEqual(current['fullname'],'Stale')
        self.assertEqual(current['role'],'user')

    def test_late_saved_credentials_cannot_replace_logged_in_account(self):
        methods=self.methods('apply_restored_login')
        host=SimpleNamespace(restore_login_loading=True,server_session={'username':'current'},perform_login=Mock())
        methods['apply_restored_login'](host,{'session':{'username':'old','key':'fixture'}})
        self.assertFalse(host.restore_login_loading)
        host.perform_login.assert_not_called()

    def test_saved_credentials_file_read_does_not_block_gui(self):
        import threading
        methods=self.methods('restore_login')
        entered=threading.Event();release=threading.Event();done=threading.Event()
        signal=SimpleNamespace(emit=lambda value:done.set())
        host=SimpleNamespace(server_session=None,restore_login_loading=False,busy=lambda:False,login_restore_finished=signal)
        def blocked_read():entered.set();release.wait(2);return None
        with patch('assistant.accounts.load_login',side_effect=blocked_read):
            try:
                methods['restore_login'](host)
                self.assertTrue(entered.wait(1))
                self.assertFalse(done.is_set())
                self.assertTrue(host.restore_login_loading)
            finally:release.set();self.assertTrue(done.wait(1))

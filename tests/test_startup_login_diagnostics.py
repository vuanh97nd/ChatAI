import ast
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from assistant.performance import measure,record,report


class StartupPerformanceTest(unittest.TestCase):
    def test_ui_runtime_does_not_import_ollama(self):
        completed=subprocess.run([sys.executable,'-c',"import sys;from assistant import initialize_runtime;initialize_runtime();assert 'ollama' not in sys.modules;assert 'httpx' not in sys.modules"],capture_output=True,text=True,timeout=15)
        self.assertEqual(completed.returncode,0,completed.stderr)

    def test_online_startup_does_not_probe_local_models_and_busy_local_defers(self):
        source=ast.parse((Path(__file__).parents[1]/'desktop_ui.py').read_text())
        window=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='Window')
        method=next(n for n in window.body if isinstance(n,ast.FunctionDef) and n.name=='refresh_startup_models')
        namespace={'REMOTE_MODELS':{'DeepSeek API'},'QTimer':Mock()}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),'startup-test','exec'),namespace)
        host=SimpleNamespace(model=Mock(),busy=Mock(return_value=False),refresh_models=Mock(),refresh_startup_models=Mock())
        host.model.currentText.return_value='DeepSeek API'
        namespace['refresh_startup_models'](host);host.refresh_models.assert_not_called()
        host.model.currentText.return_value='qwen2.5:7b';host.busy.return_value=True
        namespace['refresh_startup_models'](host);host.refresh_models.assert_not_called()
        namespace['QTimer'].singleShot.assert_called_once_with(500,host.refresh_startup_models)
        host.busy.return_value=False
        namespace['refresh_startup_models'](host);host.refresh_models.assert_called_once_with()

    def test_timings_are_numeric_bounded_and_do_not_capture_context_secrets(self):
        secret='fixture-secret-not-to-be-reported'
        with measure('test.phase'):unused=secret
        record('test.zero',0)
        for invalid in (float('nan'),float('inf'),-1,'bad'):
            with self.assertRaises(ValueError):record('test.invalid',invalid)
        value=report()
        self.assertIn('startup-login-3',value);self.assertIn('test.phase:',value)
        self.assertNotIn(secret,value)

    def test_login_network_measurements_cover_headers_and_body(self):
        from assistant.accounts import request_account
        response=Mock();response.read.return_value=b'{"success":true}'
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        with patch('assistant.accounts.urlopen',return_value=response),patch('assistant.accounts.record') as record_time:
            self.assertTrue(request_account('https://example.org','/api/login',{'key':'fixture-secret'})['success'])
        self.assertEqual([c.args[0] for c in record_time.call_args_list],['login.network_wait_headers','login.network_read_body'])
        self.assertTrue(all(isinstance(c.args[1],float) and c.args[1]>=0 for c in record_time.call_args_list))

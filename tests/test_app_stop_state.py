import ast
import unittest
from pathlib import Path
from assistant.windows_apps import _STOP,_PAUSED,stop_automation,resume_automation,pause_automation

class AppStopStateTest(unittest.TestCase):
    def setUp(self):
        source=ast.parse((Path(__file__).parents[1]/'desktop_ui.py').read_text())
        window=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='Window')
        methods=[n for n in window.body if isinstance(n,ast.FunctionDef) and n.name=='begin_app_request']
        klass=ast.ClassDef(name='Window',bases=[],keywords=[],body=methods,decorator_list=[])
        ns={};exec(compile(ast.fix_missing_locations(ast.Module(body=[klass],type_ignores=[])),'stop-state','exec'),ns)
        self.view=ns['Window']();self.view.cfg={'windows_apps_enabled':True};self.view.busy=lambda:False
        self.addCleanup(resume_automation)
    def test_new_request_resumes_after_previous_task_stopped(self):
        stop_automation();pause_automation(True)
        self.view.begin_app_request()
        self.assertFalse(_STOP.is_set());self.assertFalse(_PAUSED.is_set())
        stop_automation();self.view.begin_app_request();self.assertFalse(_STOP.is_set())
    def test_new_request_cannot_resume_active_or_disabled_task(self):
        stop_automation();self.view.busy=lambda:True;self.view.begin_app_request()
        self.assertTrue(_STOP.is_set())
        self.view.busy=lambda:False;self.view.cfg['windows_apps_enabled']=False
        self.view.begin_app_request();self.assertTrue(_STOP.is_set())

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from assistant.application_macros import ApplicationMacros
from assistant.communication import MethodRequired
from assistant.files import FileTools

class MacroTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.app_path=self.root/'excel.exe';self.app_path.write_bytes(b'exe')
        self.policy={'communication_methods':{'macro':True,'plugin':True,'com':True,'files':True}}
        self.windows=SimpleNamespace(check=lambda:self.policy,allowed_path=lambda raw:Path(raw).resolve())
        self.files=FileTools([self.root],self.root/'backup',lambda *a:None)
        self.runs=[];self.removed=[];self.modules={}
        def add(kind):
            module=SimpleNamespace(Name='',CodeModule=SimpleNamespace(CountOfLines=0))
            def code(source):module.source=source;module.CodeModule.CountOfLines=len(source.splitlines())
            module.CodeModule.AddFromString=code
            module.CodeModule.Lines=lambda a,b:module.source
            self.modules['created']=module;return module
        components=SimpleNamespace(Add=add,Remove=lambda mod:self.removed.append(mod),Item=lambda name:self.modules[name])
        self.doc=SimpleNamespace(Name='Book1',VBProject=SimpleNamespace(Name='Project',VBComponents=components))
        def run(*args):self.runs.append(args);return 42
        self.app=SimpleNamespace(ActiveWorkbook=self.doc,Run=run)
        @contextmanager
        def connect(*args,**kwargs):yield self.app
        self.tools=ApplicationMacros(self.windows,self.files,lambda *a:None,SimpleNamespace(connect=connect,process_path=lambda app:str(self.app_path)))
    def tearDown(self):self.temp.cleanup()
    def plan(self,**kwargs):
        return self.tools.prepare('vba_execute',dict(app=str(self.app_path),application='excel',code='Function Test()\nTest = 42\nEnd Function',entrypoint='Test',**kwargs))
    def test_new_vba_module_verified_then_run_in_active_workbook(self):
        plan=self.plan();result=self.tools.commit(plan)
        self.assertTrue(result['macro_completed']);self.assertFalse(result['saved'])
        self.assertEqual(result['result'],42)
        self.assertEqual(self.runs,[ ("'Book1'!"+plan['module']+'.Test',) ])
    def test_vba_readback_mismatch_removes_module_and_never_runs(self):
        add=self.doc.VBProject.VBComponents.Add
        def mismatch(kind):
            module=add(kind);module.CodeModule.Lines=lambda a,b:'Sub Other()\nEnd Sub';return module
        self.doc.VBProject.VBComponents.Add=mismatch
        with self.assertRaisesRegex(RuntimeError,'không khớp'):self.tools.commit(self.plan())
        self.assertEqual(self.runs,[]);self.assertEqual(len(self.removed),1)
    def test_macro_failure_does_not_retry_and_marks_uncertain(self):
        calls=[]
        def fail(*args):calls.append(args);raise RuntimeError('error')
        self.app.Run=fail
        result=self.tools.commit(self.plan())
        self.assertFalse(result['ok']);self.assertTrue(result['uncertain']);self.assertEqual(len(calls),1)
    def test_permission_revocation_blocks_macro_and_com_is_required(self):
        plan=self.plan();self.policy['communication_methods']['macro']=False
        with self.assertRaises(MethodRequired):self.tools.commit(plan)
        self.policy['communication_methods'].update(macro=True,com=False)
        with self.assertRaisesRegex(MethodRequired,'COM'):self.plan()
        self.assertEqual(self.runs,[])
    def test_existing_office_addin_state_is_read_back(self):
        addon=SimpleNamespace(ProgId='Example.Addin',Description='Example',Connect=False)
        self.app.COMAddIns=SimpleNamespace(Count=1,Item=lambda key:addon)
        def plan(operation):return self.tools.prepare('office_addin',{'app':str(self.app_path),'application':'excel','operation':operation,'progid':'Example.Addin'})
        self.assertFalse(self.tools.commit(plan('list'))['addins'][0]['connected'])
        self.assertTrue(self.tools.commit(plan('enable'))['connected'])
        self.assertFalse(self.tools.commit(plan('disable'))['connected'])
    def test_autolisp_requires_correlated_completion_not_only_send_command(self):
        self.app_path=self.root/'acad.exe';self.app_path.write_bytes(b'cad')
        plan=self.tools.prepare('autolisp_execute',{'app':str(self.app_path),'code':'(+ 1 2)','timeout':1})
        sent=[]
        def send(command):
            sent.append(command)
            Path(plan['output']).write_text(plan['request_id']+'\nOK\n3\nDONE '+plan['request_id']+'\n',encoding='utf-8')
        self.app.ActiveDocument=SimpleNamespace(SendCommand=send)
        result=self.tools.commit(plan)
        self.assertTrue(result['execution_completed']);self.assertEqual(result['result'],'3');self.assertEqual(len(sent),1)
        self.assertIn('(+ 1 2)',Path(plan['script']).read_text())
    def test_autocad_vba_uses_permitted_dvb_and_runmacro(self):
        self.app_path=self.root/'acad.exe';self.app_path.write_bytes(b'cad')
        dvb=self.root/'sample.dvb';dvb.write_bytes(b'fixture')
        loaded=[];ran=[]
        self.app.LoadDVB=lambda path:loaded.append(path)
        self.app.RunMacro=lambda macro:ran.append(macro)
        plan=self.tools.prepare('vba_execute',{'app':str(self.app_path),'application':'autocad','project_path':str(dvb),'module':'Module1','entrypoint':'Draw'})
        result=self.tools.commit(plan)
        self.assertTrue(result['macro_completed']);self.assertEqual(loaded,[str(dvb)])
        self.assertEqual(ran,[str(dvb)+'!Module1.Draw'])

    def test_clipboard_permission_revocation_and_verified_backend_result(self):
        calls=[]
        def perform(operation,text):
            calls.append((operation,text));return {'ok':True,'verified':True,'text':text}
        self.tools.clipboard_backend=SimpleNamespace(perform=perform)
        with self.assertRaises(MethodRequired):self.tools.prepare('windows_clipboard',{'operation':'write','text':'Tiếng Việt γ'})
        self.policy['communication_methods']['clipboard']=True
        plan=self.tools.prepare('windows_clipboard',{'operation':'write','text':'Tiếng Việt γ'})
        result=self.tools.commit(plan)
        self.assertEqual(result['text'],'Tiếng Việt γ');self.assertTrue(result['verified'])
        self.policy['communication_methods']['clipboard']=False
        with self.assertRaises(MethodRequired):self.tools.commit(plan)
        self.assertEqual(len(calls),1)

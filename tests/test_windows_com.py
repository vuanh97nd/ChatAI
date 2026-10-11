import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from assistant.files import FileTools
from assistant.windows_com import WindowsCOM


class COMTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.app=self.root/'excel.exe';self.app.write_bytes(b'excel-fixture')
        self.enabled=True
        def check():
            if not self.enabled:raise PermissionError('revoked')
            return {'windows_apps_enabled':True,'communication_methods':{'com':True}}
        self.windows=SimpleNamespace(check=check,allowed_path=lambda raw:Path(raw).resolve())
        self.files=FileTools([self.root],self.root/'backups',lambda *a:None)
        self.area=SimpleNamespace(Value2=None,Rows=SimpleNamespace(Item=lambda n:SimpleNamespace(Font=SimpleNamespace(Bold=False))),Columns=SimpleNamespace(AutoFit=lambda:None))
        self.sheet=SimpleNamespace(Name='Sheet1',Range=lambda c:SimpleNamespace(Resize=lambda h,w:self.area))
        self.book=SimpleNamespace(Name='Book1',ActiveSheet=self.sheet)
        self.new_books=[]
        def add():self.new_books.append(True);return self.book
        self.excel=SimpleNamespace(Visible=False,ActiveWorkbook=self.book,Workbooks=SimpleNamespace(Add=add))
        @contextmanager
        def connect(*args,**kwargs):yield self.excel
        self.backend=SimpleNamespace(connect=connect,process_path=lambda app:str(self.app))
        self.tools=WindowsCOM(self.windows,self.files,lambda *a:None,self.backend)
    def tearDown(self):self.temp.cleanup()
    def plan(self,**kwargs):
        return self.tools.prepare('excel_com',dict(app=str(self.app),operation='write',mode='active',rows='[["γ", "kN/m³"], [18, "=literal"]]',**kwargs))
    def test_active_workbook_writes_verifies_and_does_not_save_or_create(self):
        result=self.tools.commit(self.plan())
        self.assertTrue(result['verified']);self.assertFalse(result['saved'])
        self.assertEqual(result['values'],[['γ','kN/m³'],[18,'=literal']])
        self.assertEqual(self.area.NumberFormat,'@');self.assertEqual(self.new_books,[])
        self.assertEqual(list(self.root.glob('*.xlsx')),[])
    def test_new_workbook_does_not_require_template(self):
        plan=self.plan();plan['mode']='new'
        self.tools.commit(plan);self.assertEqual(self.new_books,[True])
    def test_permission_revoked_after_prepare_prevents_write(self):
        plan=self.plan();self.enabled=False
        with self.assertRaises(PermissionError):self.tools.commit(plan)
        self.assertIsNone(self.area.Value2)
    def test_wrong_running_application_is_rejected(self):
        plan=self.plan();self.backend.process_path=lambda app:str(self.root/'other.exe')
        with self.assertRaises(PermissionError):self.tools.commit(plan)
        self.assertIsNone(self.area.Value2)
    def test_invalid_table_and_range_rejected_before_com(self):
        for rows in ('[]','[[1],[1,2]]','[[{"x":1}]]','[[NaN]]'):
            with self.assertRaises(ValueError):
                self.tools.prepare('excel_com',dict(app=str(self.app),rows=rows))
        with self.assertRaises(ValueError):self.plan(cell='XFD1048576')
    def test_no_saving_active_workbook_or_overwriting_existing_file(self):
        with self.assertRaises(ValueError):self.plan(path=str(self.root/'test.xlsx'))
        dest=self.root/'test.xlsx';dest.write_bytes(b'original')
        with self.assertRaises(ValueError):
            self.tools.prepare('excel_com',dict(app=str(self.app),mode='new',rows='[[1]]',path=str(dest)))
        self.assertEqual(dest.read_bytes(),b'original')
    def test_online_schemas_and_dispatch_include_com_only_when_available(self):
        from assistant.online_automation import OnlineAutomation
        agent=OnlineAutomation(None,{'communication_methods':{'com':True}},None,'c',self.windows,None,windows_com=self.tools)
        names={spec['function']['name'] for spec in agent.schemas}
        self.assertTrue({'excel_com','word_com','powerpoint_com','autocad_com'}<=names)
        self.assertIs(agent.component('excel_com'),self.tools)
        disabled=OnlineAutomation(None,{},None,'c',self.windows,None)
        self.assertNotIn('excel_com',{spec['function']['name'] for spec in disabled.schemas})

    def test_word_creates_and_verifies_unsaved_document(self):
        self.app=self.root/'winword.exe';self.app.write_bytes(b'word')
        doc=SimpleNamespace(Content=SimpleNamespace(Text=''))
        self.excel=SimpleNamespace(Documents=SimpleNamespace(Add=lambda:doc),Visible=False)
        plan=self.tools.prepare('word_com',{'app':str(self.app),'content':'Bảng thông số γ, φ, E'})
        result=self.tools.commit(plan)
        self.assertTrue(result['verified']);self.assertFalse(result['saved'])
        self.assertEqual(doc.Content.Text,'Bảng thông số γ, φ, E')

    def test_powerpoint_verifies_titles_and_content(self):
        self.app=self.root/'powerpnt.exe';self.app.write_bytes(b'ppt')
        created=[]
        class Slides:
            Count=0
            def Add(self,index,layout):
                self.Count+=1
                title=SimpleNamespace(TextFrame=SimpleNamespace(TextRange=SimpleNamespace(Text='')))
                body=SimpleNamespace(TextFrame=SimpleNamespace(TextRange=SimpleNamespace(Text='')))
                slide=SimpleNamespace(Shapes=SimpleNamespace(Title=title,Placeholders=SimpleNamespace(Item=lambda n:body)))
                created.append((title,body));return slide
        doc=SimpleNamespace(Slides=Slides())
        self.excel=SimpleNamespace(Presentations=SimpleNamespace(Add=lambda:doc),Visible=False)
        result=self.tools.commit(self.tools.prepare('powerpoint_com',{'app':str(self.app),'slides':'[{"title":"A","content":"B"}]'}))
        self.assertTrue(result['verified']);self.assertEqual(result['slides_created'],1)
        self.assertEqual(created[0][1].TextFrame.TextRange.Text,'B')

    def test_autocad_verifies_created_coordinates(self):
        self.app=self.root/'acad.exe';self.app.write_bytes(b'cad')
        lines=[]
        def add(start,end):
            line=SimpleNamespace(StartPoint=tuple(start),EndPoint=tuple(end),Handle='AB')
            lines.append(line);return line
        self.excel=SimpleNamespace(ActiveDocument=SimpleNamespace(ModelSpace=SimpleNamespace(AddLine=add)),Visible=False)
        result=self.tools.commit(self.tools.prepare('autocad_com',{'app':str(self.app),'points':'[[0,0,0],[1,2,3]]'}))
        self.assertTrue(result['verified']);self.assertEqual(result['handles'],['AB'])
        self.assertEqual(lines[0].EndPoint,(1.,2.,3.))

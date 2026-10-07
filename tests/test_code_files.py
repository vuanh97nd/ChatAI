import ast
import difflib
import html
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from assistant.code_files import CodeFiles,fences,source_record,suggested_name
from assistant.context import compact_evidence


class CodeFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path.cwd())
        self.root=Path(self.tmp.name);self.workspace=self.root/'workspace';self.workspace.mkdir()
        self.logs=[]
        self.service=CodeFiles([self.workspace],self.root/'backup',lambda action,row:self.logs.append((action,row)))
    def tearDown(self):self.tmp.cleanup()
    def test_fence_preserves_code(self):
        text='Giải thích\n```python\r\nif True:\r\n    print("Tiếng Việt <>&")\r\n```\r\nSau'
        block=fences(text)[0]
        self.assertTrue(block.complete);self.assertEqual(block.code,'if True:\r\n    print("Tiếng Việt <>&")\r\n')
        self.assertEqual(text[block.end:],'Sau')
    def test_multiple_open_and_tilde(self):
        blocks=fences('~~~~js\n```\n~~~~\n\n```python\n    unfinished')
        self.assertEqual(len(blocks),2);self.assertEqual(blocks[0].code,'```\n');self.assertFalse(blocks[1].complete)
    def test_short_closing_fence_is_code(self):
        block=fences('````python\n```\nprint(1)\n````\n')[0]
        self.assertEqual(block.code,'```\nprint(1)\n')
    def test_no_fence_and_default_name(self):
        self.assertEqual(fences('abc `inline`'),[])
        self.assertEqual(suggested_name('python'),'chat_ai_code.py')
        self.assertEqual(suggested_name('python','a.py'),'a_edited.py')
    def test_whitelist_escape(self):
        with self.assertRaises(PermissionError):self.service.prepare(self.root/'outside.py','print(1)')
    def test_new_file_approved_plan(self):
        target=self.workspace/'new.py';plan=self.service.prepare(target,'print("Xin chào")\n')
        self.assertFalse(target.exists());self.service.commit(plan)
        self.assertEqual(target.read_text(),'print("Xin chào")\n');self.assertEqual(self.logs[-1][0],'file_success')
    def test_backup_bom_newlines(self):
        target=self.workspace/'a.py';original=b'\xef\xbb\xbfprint(1)\r\n';target.write_bytes(original)
        source=source_record(target);plan=self.service.prepare(target,'print(2)\n',source)
        result=self.service.commit(plan)
        self.assertEqual(target.read_bytes(),b'\xef\xbb\xbfprint(2)\r\n');self.assertEqual(Path(result['backup']).read_bytes(),original)
    def test_changed_since_attachment(self):
        target=self.workspace/'a.py';target.write_text('old');source=source_record(target);target.write_text('other')
        with self.assertRaises(RuntimeError):self.service.prepare(target,'new',source)
        self.assertEqual(target.read_text(),'other')
    def test_changed_after_preview(self):
        target=self.workspace/'a.py';target.write_text('old');plan=self.service.prepare(target,'new');target.write_text('other')
        with self.assertRaises(RuntimeError):self.service.commit(plan)
    def test_new_file_collision(self):
        target=self.workspace/'a.py';plan=self.service.prepare(target,'new');target.write_text('other')
        with self.assertRaises(RuntimeError):self.service.commit(plan)
        self.assertEqual(target.read_text(),'other')
    def test_truncated_source_blocked(self):
        target=self.workspace/'a.py';target.write_text('old');source=source_record(target,1)
        with self.assertRaises(ValueError):self.service.prepare(target,'new',source)
    def test_symlink_outside(self):
        target=self.root/'outside.py';target.write_text('old');link=self.workspace/'link.py'
        try:link.symlink_to(target)
        except OSError:self.skipTest('Symlink unsupported')
        with self.assertRaises(PermissionError):self.service.prepare(link,'new')
    def test_evidence_reports_cut(self):
        state={'attached_documents':[{'file':'a.py','text':'A'*4000,'truncated':False}]}
        evidence=compact_evidence(state,budget=500)
        self.assertTrue(evidence['attachments'][0]['truncated']);self.assertFalse(state['attached_documents'][0]['truncated'])
    def test_render_actions_escape_and_stream(self):
        tree=ast.parse((Path(__file__).parents[1]/'assistant/code_ui.py').read_text())
        method=next(m for cls in tree.body if isinstance(cls,ast.ClassDef) for m in cls.body if isinstance(m,ast.FunctionDef) and m.name=='render_code_content')
        ns={'fences':fences,'uuid':uuid,'html':html,'time':time,'Path':Path}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'<render>','exec'),ns)
        mock=SimpleNamespace(code_actions={},copied_codes={},saved_code_files=[])
        result=ns['render_code_content'](mock,'```html\n<script>danger</script>\n```',html.escape,3)
        self.assertIn('Lưu file',result);self.assertIn('&lt;script&gt;',result);self.assertNotIn('<script>',result)
        stream=ns['render_code_content'](mock,'```py\nprint(',html.escape,None)
        self.assertNotIn('Lưu file',stream);self.assertIn('Đang viết',stream)

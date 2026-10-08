import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from pypdf import PdfWriter
from assistant.files import FileTools
from assistant.pdf_source import PDFSource


class PDFSourceTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.app=self.root/'FoxitPDFReader.exe';self.app.write_bytes(b'fixture')
        self.allowed=True
        def allowed(raw):
            if not self.allowed:raise PermissionError('Revoked')
            if Path(raw)!=self.app:raise PermissionError('Unlisted')
            return self.app
        self.windows=SimpleNamespace(allowed_path=allowed,check=lambda:allowed(str(self.app)))
        self.files=FileTools([self.root],self.root/'backups',lambda *a:None)
        self.tools=PDFSource(self.windows,self.files,lambda *a:None)
        self.urlpatch=patch('assistant.pdf_source.public_url',side_effect=lambda url:url);self.urlpatch.start()
    def tearDown(self):self.urlpatch.stop();self.tmp.cleanup()
    def plan(self):return self.tools.prepare('pdf_source_open',{'url':'https://example.org/source.pdf','app':str(self.app)})
    def test_local_pdf_opens_without_download_and_rechecks_file(self):
        document=self.root/'attached.pdf'
        writer=PdfWriter();writer.add_blank_page(width=100,height=100)
        with document.open('wb') as stream:writer.write(stream)
        original=document.read_bytes()
        with patch('assistant.pdf_source.subprocess.Popen') as launch,patch('assistant.pdf_source.build_opener') as download:
            launch.return_value.pid=12
            plan=self.tools.prepare('pdf_local_open',{'path':str(document),'app':str(self.app)})
            launch.assert_not_called()
            result=self.tools.commit(plan)
            self.assertTrue(result['foxit_launch_requested'])
            self.assertEqual(launch.call_args.args[0],[str(self.app),str(document)])
            self.assertEqual(document.read_bytes(),original)
            download.assert_not_called()
            document.write_bytes(original+b'changed')
            with self.assertRaises(PermissionError):self.tools.commit(plan)
            self.assertEqual(launch.call_count,1)
        with tempfile.TemporaryDirectory() as outside:
            other=Path(outside)/'other.pdf';other.write_bytes(original)
            with self.assertRaises(PermissionError):
                self.tools.prepare('pdf_local_open',{'path':str(other),'app':str(self.app)})

    def test_pdf_read_requests_ocr_and_reports_failure_without_looping(self):
        with patch('assistant.documents.read_document_range',side_effect=ValueError('PDF không có text; cần OCR.')) as read,patch('assistant.foxit_ocr_automation.foxit_ocr') as ocr:
            result=self.tools.read(self.root/'scan.pdf')
        self.assertFalse(read.call_args.kwargs['foxit_ocr'])
        ocr.assert_not_called()
        self.assertFalse(result['read_ok']);self.assertEqual(result['coverage'],'none')
        self.assertIn('không tự mở Foxit OCR',result['note'])

    def test_download_and_open_only_after_approval(self):
        writer=PdfWriter();writer.add_blank_page(width=100,height=100)
        stream=io.BytesIO();writer.write(stream);raw=stream.getvalue()
        response=io.BytesIO(raw);response.geturl=lambda:'https://example.org/source.pdf'
        with patch('assistant.pdf_source.build_opener') as opener,patch('assistant.pdf_source.subprocess.Popen') as launch:
            opener.return_value.open.return_value=response;launch.return_value.pid=42
            plan=self.plan();self.assertFalse(Path(plan['path']).exists());launch.assert_not_called();opener.assert_not_called()
            result=self.tools.commit(plan)
            self.assertTrue(result['downloaded']);self.assertTrue(Path(result['path']).exists())
            self.assertEqual(launch.call_args.args[0],[str(self.app),result['path']])
            self.assertFalse(launch.call_args.kwargs['shell'])
            self.assertNotEqual(result['coverage'],'full_text')
            self.assertFalse(result['read_ok'])
            self.assertEqual(result['content'],'')
    def test_html_and_revoked_permission_do_not_launch(self):
        plan=self.plan();response=io.BytesIO(b'<html>CAPTCHA</html>');response.geturl=lambda:plan['url']
        with patch('assistant.pdf_source.build_opener') as opener,patch('assistant.pdf_source.subprocess.Popen') as launch:
            opener.return_value.open.return_value=response
            with self.assertRaises(ValueError):self.tools.commit(plan)
            launch.assert_not_called();self.assertFalse(Path(plan['path']).exists())
            self.allowed=False
            with self.assertRaises(PermissionError):self.tools.commit(plan)
            launch.assert_not_called()
    def test_no_overwrite_or_changed_executable(self):
        plan=self.plan();Path(plan['path']).write_bytes(b'user file')
        with self.assertRaises(ValueError):self.tools.commit(plan)
        self.assertEqual(Path(plan['path']).read_bytes(),b'user file')
        plan=self.plan();self.app.write_bytes(b'changed')
        with self.assertRaises(PermissionError):self.tools.commit(plan)
    def test_foxit_pdf_editor_is_supported(self):
        self.app=self.root/'FoxitPDFEditor.exe';self.app.write_bytes(b'editor fixture')
        plan=self.plan()
        self.assertEqual(plan['app'],str(self.app))
    def test_text_pdf_is_read_with_real_pdf_parser(self):
        from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
        writer=PdfWriter();page=writer.add_blank_page(width=200,height=200)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        content=DecodedStreamObject();content.set_data(b'BT /F1 12 Tf 10 50 Td (TCCS 41-2022 source text) Tj ET')
        page[NameObject('/Contents')]=writer._add_object(content)
        path=self.root/'text.pdf'
        with path.open('wb') as stream:writer.write(stream)
        plan=self.tools.prepare('pdf_read',{'path':str(path)})
        result=self.tools.commit(plan)
        self.assertTrue(result['read_ok']);self.assertIn('TCCS 41-2022 source text',result['content'])
        self.assertEqual(result['coverage'],'full_text')

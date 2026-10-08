import io
import unittest
from assistant.online_documents import online_pdf_reader
from assistant.documents import read_bytes
from pypdf import PdfWriter

class OnlineDocumentsTests(unittest.TestCase):
    def test_both_permissions_required(self):
        def forbidden(*a,**kw):raise AssertionError('API called without consent')
        for cfg in ({},{'online_tools_enabled':True},{'online_document_upload':True}):
            self.assertIsNone(online_pdf_reader(cfg,{},client_factory=forbidden))

    def test_scan_is_bounded_cached_and_labeled(self):
        calls=[];providers=[]
        class Client:
            def __init__(self,session,provider,**kw):providers.append(provider)
            def chat(self,**kwargs):
                calls.append(kwargs)
                return {'message':{'content':'Nội dung trang đã đọc'}}
        writer=PdfWriter();writer.add_blank_page(width=300,height=400);writer.add_blank_page(width=300,height=400)
        output=io.BytesIO();writer.write(output);raw=output.getvalue()
        reader=online_pdf_reader({'online_tools_enabled':True,'online_document_upload':True,'online_document_pages':1},{'username':'test'},client_factory=Client)
        result=read_bytes(raw,name='scan.pdf',pdf_ocr=reader)
        self.assertEqual(providers,['deepseek_flash'])
        self.assertEqual(len(calls),1)
        self.assertFalse(result['full_text'])
        self.assertIn('giới hạn đọc ảnh PDF 1 trang',' '.join(result['issues']))
        self.assertNotIn('không nhận được chữ',' '.join(result['issues']))
        self.assertEqual(reader(raw,0),'Nội dung trang đã đọc')
        self.assertEqual(len(calls),1)
        message=calls[0]['messages'][1]
        self.assertNotIn('images',message)
        self.assertTrue(message['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,'))
        self.assertIn('API trực tuyến',result['coverage_note'])

    def test_enabled_requires_login(self):
        with self.assertRaisesRegex(ValueError,'Đăng nhập'):
            online_pdf_reader({'online_tools_enabled':True,'online_document_upload':True},None)


    def test_default_reads_thirteen_pages_not_five(self):
        calls=[]
        class Client:
            def __init__(self,*a,**kw):pass
            def chat(self,**kw):
                calls.append(kw)
                return {'message':{'content':'Chữ của trang'}}
        writer=PdfWriter()
        for _ in range(13):writer.add_blank_page(width=100,height=100)
        output=io.BytesIO();writer.write(output)
        reader=online_pdf_reader({'online_tools_enabled':True,'online_document_upload':True},{'username':'test'},client_factory=Client)
        result=read_bytes(output.getvalue(),name='scan.pdf',pdf_ocr=reader)
        self.assertEqual(len(calls),13)
        self.assertTrue(result['full_text'])
        self.assertEqual(len(result['ocr_pages']),13)

    def test_old_five_page_setting_migrates_once(self):
        import json
        from pathlib import Path
        from assistant.config import validate_config
        cfg=json.loads((Path(__file__).resolve().parents[1]/'config.json').read_text())
        cfg['online_document_pages']=5;cfg.pop('online_document_revision',None)
        updated=validate_config(cfg)
        self.assertEqual(updated['online_document_pages'],40)
        updated['online_document_pages']=5
        self.assertEqual(validate_config(updated)['online_document_pages'],5)
        updated['online_document_pages']=200
        self.assertEqual(validate_config(updated)['online_document_pages'],200)
        updated['online_document_pages']=201
        with self.assertRaises(ValueError):validate_config(updated)

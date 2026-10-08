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
        self.assertEqual(reader(raw,0),'Nội dung trang đã đọc')
        self.assertEqual(len(calls),1)
        message=calls[0]['messages'][1]
        self.assertNotIn('images',message)
        self.assertTrue(message['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,'))
        self.assertIn('API trực tuyến',result['coverage_note'])

    def test_enabled_requires_login(self):
        with self.assertRaisesRegex(ValueError,'Đăng nhập'):
            online_pdf_reader({'online_tools_enabled':True,'online_document_upload':True},None)

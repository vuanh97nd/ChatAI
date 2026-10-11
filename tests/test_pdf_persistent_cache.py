import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from assistant.online_documents import online_pdf_reader
from assistant.runtime_cache import RuntimeCache


class PersistentPDFCacheTests(unittest.TestCase):
    def test_reader_recreation_reuses_pages_but_changed_file_account_server_do_not(self):
        with tempfile.TemporaryDirectory() as folder:
            cache=RuntimeCache(Path(folder)/'cache.db')
            read=Mock(return_value='Số liệu trang 14')
            cfg={'online_tools_enabled':True,'online_document_upload':True}
            session={'username':'a','endpoint':'https://primary.example'}
            with patch('assistant.online_documents.optional_cache',return_value=cache),patch('assistant.online_documents.pdf_vision_ocr',return_value=read):
                factory=lambda *a,**kw:Mock()
                def reader(s=session):return online_pdf_reader(cfg,s,client_factory=factory)
                self.assertEqual(reader()(b'PDF one',13),'Số liệu trang 14')
                self.assertEqual(reader()(b'PDF one',13),'Số liệu trang 14')
                self.assertEqual(read.call_count,1)
                reader()(b'PDF changed',13)
                reader({'username':'b','endpoint':session['endpoint']})(b'PDF one',13)
                reader({'username':'a','endpoint':'https://backup.example'})(b'PDF one',13)
                reader()(b'PDF one',14)
                self.assertEqual(read.call_count,5)

    def test_failed_or_empty_ocr_is_not_persisted(self):
        with tempfile.TemporaryDirectory() as folder:
            cache=RuntimeCache(Path(folder)/'cache.db')
            read=Mock(side_effect=[RuntimeError('network'),'', 'Valid text'])
            with patch('assistant.online_documents.optional_cache',return_value=cache),patch('assistant.online_documents.pdf_vision_ocr',return_value=read):
                def reader():return online_pdf_reader({'online_tools_enabled':True,'online_document_upload':True},
                                                     {'username':'a'},client_factory=lambda *a,**kw:Mock())
                with self.assertRaises(RuntimeError):reader()(b'PDF',0)
                self.assertEqual(reader()(b'PDF',0),'')
                self.assertEqual(reader()(b'PDF',0),'Valid text')
                self.assertEqual(reader()(b'PDF',0),'Valid text')
                self.assertEqual(read.call_count,3)

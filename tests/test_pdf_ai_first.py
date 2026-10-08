import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from assistant.documents import read_local

class PdfAIFirstTests(unittest.TestCase):
    def test_ai_success_never_launches_foxit(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'scan.pdf';path.write_bytes(b'%PDF-test')
            with patch('assistant.documents.read_bytes',return_value={'text':'AI read','full_text':True}) as read,patch('assistant.foxit_ocr_automation.foxit_ocr') as foxit:
                reader=object();result=read_local(path,pdf_ocr=reader,foxit_ocr=True)
                self.assertEqual(result['text'],'AI read');foxit.assert_not_called()
                self.assertIs(read.call_args.kwargs['pdf_ocr'],reader)
    def test_failed_ai_falls_back_once_without_sending_ocr_pdf_to_ai_again(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'scan.pdf';path.write_bytes(b'%PDF-test')
            with patch('assistant.documents.read_bytes',side_effect=[RuntimeError('vision API unavailable'),{'text':'OCR read'}]) as read,patch('assistant.foxit_ocr_automation.available',return_value=True),patch('assistant.foxit_ocr_automation.foxit_ocr',return_value=path) as foxit:
                result=read_local(path,pdf_ocr=object(),foxit_ocr=True)
                self.assertEqual(result['text'],'OCR read');foxit.assert_called_once()
                self.assertIsNone(read.call_args.kwargs['pdf_ocr'])
    def test_cancel_does_not_start_ocr(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'scan.pdf';path.write_bytes(b'%PDF-test')
            with patch('assistant.documents.read_bytes',side_effect=RuntimeError('Đã dừng đọc PDF')),patch('assistant.foxit_ocr_automation.foxit_ocr') as foxit:
                with self.assertRaisesRegex(RuntimeError,'Đã dừng'):read_local(path,pdf_ocr=object(),foxit_ocr=True)
                foxit.assert_not_called()

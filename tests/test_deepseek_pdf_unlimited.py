import io
import unittest
from pypdf import PdfWriter
from assistant.documents import read_bytes

class UnlimitedPdfTests(unittest.TestCase):
    def test_no_hidden_two_hundred_page_cap(self):
        writer=PdfWriter()
        for _ in range(205):writer.add_blank_page(width=100,height=100)
        output=io.BytesIO();writer.write(output)
        calls=[]
        def vision(raw,index):calls.append(index);return 'Page '+str(index+1)
        vision.max_pages=0
        result=read_bytes(output.getvalue(),name='long.pdf',pdf_ocr=vision)
        self.assertEqual(len(calls),205)
        self.assertEqual(len(result['ocr_pages']),205)
        self.assertTrue(result['full_text'])

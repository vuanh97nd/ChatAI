import io
import unittest
from pypdf import PdfWriter
from assistant.documents import read_bytes

class PdfProgressTests(unittest.TestCase):
    def test_progress_reports_each_page_and_total_before_reading(self):
        writer=PdfWriter();writer.add_blank_page(width=200,height=300);writer.add_blank_page(width=200,height=300)
        data=io.BytesIO();writer.write(data)
        events=[]
        result=read_bytes(data.getvalue(),name='3D-1-Tutorial.pdf',pdf_ocr=lambda raw,index:'Page '+str(index+1),progress=events.append)
        self.assertEqual(len(events),2)
        self.assertIn('trang 1/2',events[0]);self.assertIn('trang 2/2',events[1])
        self.assertIn('Page 2',result['text'])

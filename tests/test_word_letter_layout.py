import unittest,tempfile
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH as Align
from assistant.files import FileTools
from assistant.office import OfficeTools

class ProfessionalLetterTest(unittest.TestCase):
    def test_real_docx_has_semantic_layout_without_duplicate_title(self):
        content='**Đơn xin nghỉ việc**\nCỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập – Tự do – Hạnh phúc\n\\-------------------\nĐƠN XIN NGHỈ VIỆC\nKính gửi: Công ty A\nTôi tên là: Nguyễn Văn A\nTôi xin nghỉ việc từ ngày 01/11/2026.\nHà Nội, ngày 08 tháng 10 năm 2026\nNgười làm đơn\n(Ký và ghi rõ họ tên)\nNguyễn Văn A'
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);tool=OfficeTools(FileTools([root],root/'backups',lambda *a:None))
            result=tool.commit(tool.prepare('office_create',{'path':str(root/'don.docx'),'title':'Đơn xin nghỉ việc','content':content,'font_name':'Times New Roman','font_size':'13','alignment':'justify','line_spacing':'1.15'}))
            doc=Document(result['path']);paragraphs=doc.paragraphs
            self.assertEqual(sum(p.text.casefold()=='đơn xin nghỉ việc' for p in paragraphs),1)
            self.assertEqual(paragraphs[2].runs[0].font.size.pt,16)
            self.assertEqual(paragraphs[2].alignment,Align.CENTER)
            self.assertEqual(paragraphs[3].alignment,Align.LEFT)
            self.assertEqual(paragraphs[5].alignment,Align.JUSTIFY)
            self.assertEqual(paragraphs[-1].alignment,Align.RIGHT)
            self.assertEqual(paragraphs[-2].paragraph_format.space_after.pt,36)
            self.assertTrue(paragraphs[0].runs[0].bold)
            self.assertEqual(paragraphs[5].runs[0].font.size.pt,13)
            self.assertNotIn('-------------------','\n'.join(p.text for p in paragraphs))

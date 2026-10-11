import unittest
from docx import Document
from assistant.math_format import formulas,word_math,excel_math,math_png

class MathFormatTests(unittest.TestCase):
    def test_code_is_not_converted(self):
        self.assertEqual(len(list(formulas('`$x$`\n```python\n$x$\n```\n$y^2$'))),1)
    def test_word_native_editable_fraction_and_exponent(self):
        paragraph=word_math(Document().add_paragraph(),r'Công thức $\frac{a}{b}+x^2$ kết thúc')
        ns={'m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
        self.assertIsNotNone(paragraph._p.find('.//m:f',ns))
        self.assertIsNotNone(paragraph._p.find('.//m:sSup',ns))
        self.assertIn('kết thúc',paragraph.text)
    def test_excel_symbols_and_formula_safety(self):
        self.assertEqual(excel_math(r'$x^2+\sqrt{a}+\alpha$'),'x²+√(a)+α')
        self.assertEqual(excel_math('=SUM(A1:A3)'),'=SUM(A1:A3)')
        self.assertEqual(excel_math(42),42)
    def test_desktop_fraction_image(self):
        self.assertTrue(math_png(r'\frac{a}{b}+\sqrt{x}').startswith(b'\x89PNG'))

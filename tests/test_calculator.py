import unittest
from assistant.calculator import calculate
class CalculatorTest(unittest.TestCase):
    def test_decimal_units_statistics_dates(self):
        self.assertEqual(calculate('expression',expression='0.1+0.2')['result'],'0.3')
        self.assertEqual(calculate('expression',expression='-3//2')['result'],'-2')
        self.assertEqual(calculate('expression',expression='-3%2')['result'],'1')
        self.assertEqual(calculate('expression',expression='sqrt(81)+2**3')['result'],'17')
        self.assertEqual(calculate('convert',value=1.5,from_unit='km',to_unit='m')['result'],'1500.0')
        self.assertEqual(calculate('convert',value=32,from_unit='f',to_unit='c')['result'],'0')
        self.assertEqual(calculate('statistics',values=[1,2,8,9])['median'],'5')
        self.assertEqual(calculate('date_difference',start='2024-02-28',end='2024-03-01')['days'],2)
    def test_reject_code_resource_abuse_invalid_math(self):
        for expression in ['__import__("os").system("dir")','open("secret")','[1]*100000','9**999999','1/0','sqrt(-1)','x+1']:
            with self.subTest(expression=expression),self.assertRaises(Exception):calculate('expression',expression=expression)
        with self.assertRaises(ValueError):calculate('convert',value=1,from_unit='kg',to_unit='m')

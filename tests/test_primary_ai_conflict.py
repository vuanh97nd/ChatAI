import ast
import unittest
from scripts.resolve_primary_ai_cherry_pick import integrate


class PrimaryAIConflictTests(unittest.TestCase):
    def test_preserves_extra_local_features_while_removing_backup_actions(self):
        source='''class Window:
    def setup(self):
        self.keep_local_feature()
<<<<<<< HEAD
        self.button(box,'AI backup',self.backup_login_dialog)
        self.button(box,'Local API',self.custom_local_api_dialog)
=======
>>>>>>> 60d9921 (Remove AI backup configuration and keep online AI on primary)
        self.keep_payments()
    def backup_login_dialog(self):
        pass
    def custom_local_api_dialog(self):
        self.keep_direct_settings()
'''
        result=integrate(source)
        ast.parse(result)
        self.assertIn('self.keep_local_feature()',result)
        self.assertIn('self.keep_payments()',result)
        self.assertIn('self.custom_local_api_dialog',result)
        self.assertNotIn('backup_login_dialog',result)

    def test_other_conflicts_are_refused(self):
        with self.assertRaises(ValueError):
            integrate('<<<<<<< HEAD\nx=1\n=======\nx=2\n>>>>>>> unrelated\n')

    def test_handles_diff3_and_is_repeatable(self):
        source='x=1\n<<<<<<< HEAD\ny=2\n||||||| base\ny=0\n=======\ny=3\n>>>>>>> 60d9921 (Remove AI backup)\n'
        result=integrate(source)
        self.assertEqual(result,'x=1\ny=2\n')
        self.assertEqual(integrate(result),result)
        self.assertEqual(integrate(source.replace('\n','\r\n')),result)

    def test_syntax_error_stops_before_writing(self):
        with self.assertRaises(SyntaxError):integrate('def broken(\n')

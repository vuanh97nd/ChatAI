import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('verify_apk', Path(__file__).resolve().parents[1] / 'mobile/tool/verify_apk.py')
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class ApkIdentityTests(unittest.TestCase):
    def test_actual_manifest_must_match_name_and_code(self):
        valid = "package: name='vn.chatai.chatai_mobile' versionCode='10' versionName='0.8.2' platformBuildVersionName='15'"
        self.assertEqual(verify.check_manifest(valid, '0.8.2+10'), ('0.8.2', '10'))
        for invalid in (valid.replace("'10'", "'9'"), valid.replace("'0.8.2'", "'0.8.1'"), valid.replace('vn.chatai.chatai_mobile', 'other.app'), ''):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                verify.check_manifest(invalid, '0.8.2+10')

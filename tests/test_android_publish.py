import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('publish_android',Path(__file__).resolve().parents[1]/'mobile/tool/publish_android.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class AndroidPublishTests(unittest.TestCase):
    def test_only_matching_signer_can_replace_auto_update(self):
        current={'version':'1.0.1','build':50,'signature_verification':'Signer #1 certificate SHA-256 digest: abc123'}
        self.assertEqual(module.choose_tag(current,dict(current)),'android-latest')
        self.assertEqual(module.choose_tag(current,{'signature_verification':'certificate SHA-256 digest: other'}),'android-1.0.1-build50')
        self.assertEqual(module.choose_tag(current,{}),'android-1.0.1-build50')

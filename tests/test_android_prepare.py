import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('android_prepare', Path(__file__).resolve().parents[1] / 'mobile/tool/prepare_android.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)

class AndroidPrepareTests(unittest.TestCase):
    def test_android_permissions_and_signing_are_repeatable(self):
        with tempfile.TemporaryDirectory() as folder:
            android = Path(folder)
            manifest = android / 'app/src/main/AndroidManifest.xml'
            manifest.parent.mkdir(parents=True)
            manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n<application\n android:label="chatai_mobile">\n</application></manifest>')
            build = android / 'app/build.gradle.kts'
            build.write_text('android {\n minSdk = flutter.minSdkVersion\n    buildTypes {\n release { signingConfig = signingConfigs.getByName("debug") }\n }\n}')
            prepare.configure(android)
            before = (manifest.read_text(), build.read_text())
            prepare.configure(android)
            self.assertEqual(before, (manifest.read_text(), build.read_text()))
            self.assertEqual(before[0].count('android.permission.INTERNET'), 1)
            self.assertIn('android:allowBackup="false"', before[0])
            self.assertIn('android:usesCleartextTraffic="false"', before[0])
            self.assertIn('android:label="Chat AI"', before[0])
            self.assertIn('minSdk = 23', before[1])
            self.assertIn('System.getenv("ANDROID_KEYSTORE")', before[1])
            self.assertNotIn('signingConfigs.getByName("debug")', before[1])

if __name__ == '__main__':
    unittest.main()

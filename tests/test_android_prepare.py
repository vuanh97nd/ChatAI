import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
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
            manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n<application\n android:label="chatai_mobile" android:icon="@mipmap/ic_launcher">\n</application></manifest>')
            build = android / 'app/build.gradle.kts'
            build.write_text('android {\n minSdk = flutter.minSdkVersion\n    buildTypes {\n release { signingConfig = signingConfigs.getByName("debug") }\n }\n}')
            prepare.configure(android)
            before = (manifest.read_text(), build.read_text())
            resources_before = {str(p.relative_to(android)): p.read_bytes() for p in android.rglob('*') if p.is_file()}
            prepare.configure(android)
            self.assertEqual(before, (manifest.read_text(), build.read_text()))
            self.assertEqual(resources_before, {str(p.relative_to(android)): p.read_bytes() for p in android.rglob('*') if p.is_file()})
            self.assertIn('android:icon="@mipmap/chatai_launcher"', before[0])
            res = android / 'app/src/main/res'
            self.assertEqual((res / 'drawable-nodpi/chatai_logo.png').read_bytes(), (prepare.ROOT / 'assets/chat_ai.png').read_bytes())
            for resource in res.rglob('*.xml'):
                ET.parse(resource)
            self.assertEqual(ET.parse(res / 'mipmap-anydpi-v26/chatai_launcher.xml').getroot().tag, 'adaptive-icon')
            self.assertEqual(ET.parse(res / 'mipmap-anydpi/chatai_launcher.xml').getroot().tag, 'layer-list')
            for variant in ('values', 'values-night', 'values-v31', 'values-night-v31'):
                theme = ET.parse(res / variant / 'styles.xml').getroot()
                launch = theme.find("style[@name='LaunchTheme']")
                self.assertEqual(launch.find("item[@name='android:windowBackground']").text, '@drawable/chatai_launch')
                if 'v31' in variant:
                    self.assertEqual(launch.find("item[@name='android:windowSplashScreenAnimatedIcon']").text, '@drawable/chatai_foreground')
            self.assertEqual(before[0].count('android.permission.INTERNET'), 1)
            self.assertEqual(before[0].count('android.permission.RECORD_AUDIO'), 1)
            self.assertEqual(before[0].count('android.permission.CAMERA'), 1)
            self.assertEqual(before[0].count('android.speech.RecognitionService'), 1)
            self.assertEqual(before[0].count('android.intent.action.TTS_SERVICE'), 1)
            self.assertIn('android:required="false"', before[0])
            self.assertIn('android:allowBackup="false"', before[0])
            self.assertIn('android:usesCleartextTraffic="false"', before[0])
            self.assertIn('android:label="Chat AI"', before[0])
            self.assertIn('minSdk = 23', before[1])
            self.assertIn('System.getenv("ANDROID_KEYSTORE")', before[1])
            self.assertNotIn('signingConfigs.getByName("debug")', before[1])

if __name__ == '__main__':
    unittest.main()

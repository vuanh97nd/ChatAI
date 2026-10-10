"""Generate Flutter's Android scaffold and apply repeatable ChatAI settings."""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def configure(android):
    manifest = android / 'app/src/main/AndroidManifest.xml'
    text = manifest.read_text()
    text = text.replace('android:label="chatai_mobile"', 'android:label="Chat AI"')
    if 'android.permission.INTERNET' not in text:
        text = text.replace('<application', '<uses-permission android:name="android.permission.INTERNET"/>\n    <application', 1)
    text = text.replace('<application\n', '<application android:allowBackup="false" android:usesCleartextTraffic="false"\n', 1)
    manifest.write_text(text)
    build = android / 'app/build.gradle.kts'
    text = build.read_text().replace('minSdk = flutter.minSdkVersion', 'minSdk = 23')
    text = text.replace('signingConfig = signingConfigs.getByName("debug")',
                        'signingConfig = signingConfigs.findByName("chataiRelease")')
    marker = '    buildTypes {'
    signing = '''    signingConfigs {
        if (System.getenv("ANDROID_KEYSTORE") != null) {
            create("chataiRelease") {
                storeFile = file(System.getenv("ANDROID_KEYSTORE"))
                storePassword = System.getenv("ANDROID_STORE_PASSWORD")
                keyAlias = System.getenv("ANDROID_KEY_ALIAS")
                keyPassword = System.getenv("ANDROID_KEY_PASSWORD")
            }
        }
    }

'''
    if 'create("chataiRelease")' not in text:
        text = text.replace(marker, signing + marker)
    build.write_text(text)


def main():
    android = ROOT / 'android'
    if not android.exists():
        with tempfile.TemporaryDirectory() as folder:
            subprocess.run(['flutter', 'create', '--platforms=android', '--org=vn.chatai',
                            '--project-name=chatai_mobile', '--no-pub', folder], check=True)
            shutil.copytree(Path(folder) / 'android', android)
    configure(android)

if __name__ == '__main__':
    main()

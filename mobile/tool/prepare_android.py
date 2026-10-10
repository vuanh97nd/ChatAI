"""Generate Flutter's Android scaffold and apply repeatable ChatAI settings."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

def branding(android):
    res = android / 'app/src/main/res'
    def resource(name, text):
        path = res / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    logo = res / 'drawable-nodpi/chatai_logo.png'
    logo.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'assets/chat_ai.png', logo)
    resource('drawable/chatai_notification.xml', '''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#FFFFFFFF" android:pathData="M4,3h16v14H8l-4,4z"/></vector>''')
    resource('values/chatai_colors.xml', '<resources><color name="chatai_background">#202020</color></resources>')
    resource('drawable/chatai_launch.xml', '''<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
    <item android:drawable="@color/chatai_background"/>
    <item android:width="112dp" android:height="112dp" android:gravity="center" android:drawable="@drawable/chatai_logo"/>
</layer-list>''')
    resource('mipmap-anydpi/chatai_launcher.xml', '''<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
    <item><bitmap android:src="@drawable/chatai_logo" android:gravity="fill"/></item>
</layer-list>''')
    resource('drawable/chatai_foreground.xml', '''<inset xmlns:android="http://schemas.android.com/apk/res/android" android:drawable="@drawable/chatai_logo" android:inset="25%"/>''')
    resource('mipmap-anydpi-v26/chatai_launcher.xml', '''<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/chatai_background"/>
    <foreground android:drawable="@drawable/chatai_foreground"/>
</adaptive-icon>''')
    # Preserve Flutter's theme names and embedding metadata on every scaffold version.
    for directory in ('values', 'values-night', 'values-v31', 'values-night-v31'):
        path = res / directory / 'styles.xml'
        path.parent.mkdir(parents=True, exist_ok=True)
        tree = ET.parse(path) if path.exists() else ET.ElementTree(ET.Element('resources'))
        root = tree.getroot()
        for name in ('LaunchTheme', 'NormalTheme'):
            style = root.find(f"style[@name='{name}']")
            if style is None:
                style = ET.SubElement(root, 'style', {'name': name, 'parent': '@android:style/Theme.Black.NoTitleBar'})
            values = {'android:windowBackground': '@drawable/chatai_launch' if name == 'LaunchTheme' else '@color/chatai_background',
                      'android:statusBarColor': '@color/chatai_background',
                      'android:navigationBarColor': '@color/chatai_background',
                      'android:windowLightStatusBar': 'false'}
            if 'v31' in directory and name == 'LaunchTheme':
                values.update({'android:windowSplashScreenBackground': '@color/chatai_background',
                               'android:windowSplashScreenAnimatedIcon': '@drawable/chatai_foreground',
                               'android:windowSplashScreenIconBackgroundColor': '@color/chatai_background'})
            for key, value in values.items():
                item = style.find(f"item[@name='{key}']")
                if item is None: item = ET.SubElement(style, 'item', {'name': key})
                item.text = value
        tree.write(path, encoding='unicode')


def configure(android):
    manifest = android / 'app/src/main/AndroidManifest.xml'
    text = manifest.read_text()
    text = text.replace('android:label="chatai_mobile"', 'android:label="Chat AI"')
    text = text.replace('android:icon="@mipmap/ic_launcher"', 'android:icon="@mipmap/chatai_launcher"')
    if 'android.permission.POST_NOTIFICATIONS' not in text:
        text = text.replace('<application', '<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>\n    <application', 1)
    if 'android.permission.INTERNET' not in text:
        text = text.replace('<application', '<uses-permission android:name="android.permission.INTERNET"/>\n    <application', 1)
    if 'android.permission.RECORD_AUDIO' not in text:
        text = text.replace('<application', '<uses-permission android:name="android.permission.RECORD_AUDIO"/>\n    <uses-feature android:name="android.hardware.microphone" android:required="false"/>\n    <application', 1)
    if 'android.permission.CAMERA' not in text:
        text = text.replace('<application', '<uses-permission android:name="android.permission.CAMERA"/>\n    <uses-feature android:name="android.hardware.camera" android:required="false"/>\n    <application', 1)
    intents = ''
    for action in ('android.speech.RecognitionService', 'android.intent.action.TTS_SERVICE'):
        if action not in text:
            intents += f'<intent><action android:name="{action}"/></intent>\n'
    if intents:
        if '<queries>' in text:
            text = text.replace('<queries>', '<queries>\n' + intents, 1)
        else:
            text = text.replace('</manifest>', '<queries>\n' + intents + '</queries>\n</manifest>', 1)
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
    text = text.replace('JavaVersion.VERSION_11', 'JavaVersion.VERSION_17').replace('jvmTarget = JavaVersion.VERSION_11', 'jvmTarget = JavaVersion.VERSION_17')
    if 'isCoreLibraryDesugaringEnabled = true' not in text:
        text = text.replace('    compileOptions {', '    compileOptions {\n        isCoreLibraryDesugaringEnabled = true', 1)
    if 'coreLibraryDesugaring("com.android.tools:desugar_jdk_libs' not in text:
        text += '\ndependencies {\n    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")\n}\n'
    build.write_text(text)
    branding(android)


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

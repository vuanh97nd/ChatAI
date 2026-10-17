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
    resource('values/chatai_colors.xml', '<resources><color name="chatai_background">#141414</color></resources>')
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
    if 'android.permission.ACCESS_COARSE_LOCATION' not in text:
        text = text.replace('<application', '<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>\n    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>\n    <application', 1)
    if 'android.permission.CAMERA' not in text:
        text = text.replace('<application', '<uses-permission android:name="android.permission.CAMERA"/>\n    <uses-feature android:name="android.hardware.camera" android:required="false"/>\n    <application', 1)
    intents = ''
    for action in ('android.speech.RecognitionService', 'android.intent.action.TTS_SERVICE'):
        if action not in text:
            intents += f'<intent><action android:name="{action}"/></intent>\n'
    for package in ('com.google.android.apps.maps', 'com.google.android.apps.docs', 'com.google.android.gm', 'com.grabtaxi.passenger', 'xyz.be.customer', 'com.gsm.customer'):
        if f'<package android:name="{package}"' not in text:
            intents += f'<package android:name="{package}"/>\n'
    if intents:
        if '<queries>' in text:
            text = text.replace('<queries>', '<queries>\n' + intents, 1)
        else:
            text = text.replace('</manifest>', '<queries>\n' + intents + '</queries>\n</manifest>', 1)
    text = text.replace('<application\n', '<application android:allowBackup="false" android:usesCleartextTraffic="false"\n', 1)
    if 'android.intent.action.ASSIST' not in text:
        text = text.replace('</activity>', '<intent-filter><action android:name="android.intent.action.ASSIST"/><category android:name="android.intent.category.DEFAULT"/></intent-filter>\n        </activity>', 1)
    manifest.write_text(text)
    build = android / 'app/build.gradle.kts'
    text = build.read_text().replace('minSdk = flutter.minSdkVersion', 'minSdk = 23')
    text = text.replace('signingConfig = signingConfigs.getByName("debug")',
                        'signingConfig = signingConfigs.findByName("chataiRelease")')
    marker = '    buildTypes {'
    signing = '''    signingConfigs {
        if (System.getenv("CHATAI_DEBUG_KEYSTORE") != null) {
            getByName("debug") {
                storeFile = file(System.getenv("CHATAI_DEBUG_KEYSTORE"))
                storePassword = "android"
                keyAlias = "androiddebugkey"
                keyPassword = "android"
            }
        }
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
    activity = android / 'app/src/main/kotlin/vn/chatai/chatai_mobile/MainActivity.kt'
    activity.parent.mkdir(parents=True, exist_ok=True)
    activity.write_text("""package vn.chatai.chatai_mobile
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.content.pm.PackageManager
import java.security.MessageDigest
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
class MainActivity: FlutterActivity() {
  private var assistantChannel: MethodChannel? = null
  private var pendingAssist = false
  override fun onNewIntent(intent: Intent) {
    super.onNewIntent(intent)
    setIntent(intent)
    if (intent.action == Intent.ACTION_ASSIST) {
      pendingAssist = true
      assistantChannel?.invokeMethod("activate", null)
    }
  }
  override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
    super.configureFlutterEngine(flutterEngine)
    pendingAssist = pendingAssist || intent?.action == Intent.ACTION_ASSIST
    assistantChannel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "vn.chatai/assistant")
    assistantChannel?.setMethodCallHandler { call, result ->
      if (call.method == "consumeLaunch") {
        result.success(pendingAssist)
        pendingAssist = false
      } else { result.notImplemented() }
    }
    MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "vn.chatai/sound_effects").setMethodCallHandler { call, result ->
      if (call.method != "play") { result.notImplemented() }
      else {
        val manager = getSystemService(android.content.Context.AUDIO_SERVICE) as android.media.AudioManager
        if (manager.ringerMode != android.media.AudioManager.RINGER_MODE_NORMAL || manager.mode != android.media.AudioManager.MODE_NORMAL || isFinishing) {
          result.success(null)
        } else {
          try {
            val tone = when (call.arguments as? String) {
              "sent" -> android.media.ToneGenerator.TONE_PROP_BEEP
              "reply" -> android.media.ToneGenerator.TONE_PROP_ACK
              "created" -> android.media.ToneGenerator.TONE_PROP_BEEP2
              else -> -1
            }
            if (tone >= 0) {
              val player = android.media.ToneGenerator(android.media.AudioManager.STREAM_SYSTEM, 12)
              player.startTone(tone, 100)
              android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({ player.release() }, 250)
            }
          } catch (_: Exception) { /* Device sound is optional. */ }
          result.success(null)
        }
      }
    }
    MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "vn.chatai/linked_apps").setMethodCallHandler { call, result ->
      val allowed = setOf("com.google.android.apps.maps", "com.google.android.apps.docs", "com.google.android.gm", "com.grabtaxi.passenger", "xyz.be.customer", "com.gsm.customer")
      val target = call.arguments as? String
      if (call.method != "open" || target !in allowed) { result.notImplemented() }
      else {
        try {
          val intent = packageManager.getLaunchIntentForPackage(target!!)
          if (intent == null) result.success(false)
          else { startActivity(intent); result.success(true) }
        } catch (_: Exception) { result.success(false) }
      }
    }
    MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "vn.chatai/app_identity").setMethodCallHandler { call, result ->
      if (call.method != "signerSha256") { result.notImplemented() }
      else {
        try {
          @Suppress("DEPRECATION")
          val signature = if (Build.VERSION.SDK_INT >= 28) {
            packageManager.getPackageInfo(packageName, PackageManager.GET_SIGNING_CERTIFICATES).signingInfo?.apkContentsSigners?.firstOrNull()
          } else { packageManager.getPackageInfo(packageName, PackageManager.GET_SIGNATURES).signatures?.firstOrNull() }
          if (signature == null) result.error("identity", "Không đọc được chữ ký ứng dụng", null)
          else result.success(MessageDigest.getInstance("SHA-256").digest(signature.toByteArray()).joinToString("") { "%02x".format(it.toInt() and 0xff) })
        } catch (e: Exception) { result.error("identity", "Không đọc được chữ ký ứng dụng", null) }
      }
    }
    MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "vn.chatai/voice_settings").setMethodCallHandler { call, result ->
      if (call.method != "tts" && call.method != "speech") { result.notImplemented() }
      else {
        try {
          val action = if (call.method == "tts") "com.android.settings.TTS_SETTINGS" else "android.settings.VOICE_INPUT_SETTINGS"
          try { startActivity(Intent(action)) }
          catch (e: Exception) { startActivity(Intent("android.settings.APPLICATION_DETAILS_SETTINGS", Uri.parse("package:$packageName"))) }
          result.success(null)
        } catch (e: Exception) { result.error("settings", "Không mở được cài đặt giọng nói", null) }
      }
    }
  }
}
""")
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

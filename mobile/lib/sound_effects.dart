import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

enum AppSound { sent, reply, created }

class SoundEffects {
  static final enabled = ValueNotifier<bool>(true);
  static bool suspended = false;
  static const channel = MethodChannel('vn.chatai/sound_effects');
  static Future<void> play(AppSound sound) async {
    if (!enabled.value || suspended) return;
    final lifecycle = WidgetsBinding.instance.lifecycleState;
    if (lifecycle != null && lifecycle != AppLifecycleState.resumed) return;
    try { await channel.invokeMethod<void>('play', sound.name); }
    catch (_) { /* Optional sound must never interrupt a chat request. */ }
  }
}

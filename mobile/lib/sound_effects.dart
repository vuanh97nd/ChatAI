import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

enum AppSound { sent, reply, created, listening, ended, saved, error }

class SoundEffects {
  static final enabled = ValueNotifier<bool>(true);
  static final volume = ValueNotifier<double>(.35);
  static bool suspended = false;
  static bool microphoneActive = false;
  static const channel = MethodChannel('vn.chatai/sound_effects');
  static Future<void> play(AppSound sound, {bool voiceBoundary = false}) async {
    if (!enabled.value || microphoneActive || volume.value <= 0 || (suspended && !voiceBoundary)) return;
    final lifecycle = WidgetsBinding.instance.lifecycleState;
    if (lifecycle != null && lifecycle != AppLifecycleState.resumed) return;
    try { await channel.invokeMethod<void>('play', {'name': sound.name, 'volume': volume.value.clamp(0.0, 1.0)}); }
    catch (_) { /* Optional sound must never interrupt a chat request. */ }
  }
}

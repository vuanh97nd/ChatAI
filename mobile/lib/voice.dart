import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_to_text.dart';

/// Allows permission/lifecycle behavior to be tested without a microphone.
abstract class VoiceEngine {
  Future<bool> initialize(void Function(String) status, void Function(String) error);
  Future<List<String>> locales();
  Future<void> listen(String locale, void Function(String) words);
  Future<void> cancel();
  Future<void> speak(String text);
  Future<void> stopSpeaking();
}

class AndroidVoiceEngine implements VoiceEngine {
  final SpeechToText speech = SpeechToText();
  final FlutterTts tts = FlutterTts();
  @override
  Future<bool> initialize(void Function(String) status, void Function(String) error) =>
      speech.initialize(onStatus: status, onError: (e) => error(e.errorMsg));
  @override
  Future<List<String>> locales() async => (await speech.locales()).map((l) => l.localeId).toList();
  @override
  Future<void> listen(String locale, void Function(String) words) async {
    await speech.listen(localeId: locale, listenFor: const Duration(seconds: 60),
      pauseFor: const Duration(seconds: 4),
      listenOptions: SpeechListenOptions(partialResults: true, cancelOnError: true,
        listenMode: ListenMode.dictation),
      onResult: (result) => words(result.recognizedWords));
  }
  @override
  Future<void> cancel() => speech.cancel();
  @override
  Future<void> speak(String text) async {
    final run = ++_readRun;
    final available = await tts.isLanguageAvailable('vi-VN');
    if (run != _readRun) return;
    if (available != true) {
      throw Exception('Chưa có giọng tiếng Việt. Cài giọng đọc trong cài đặt Android.');
    }
    await tts.setLanguage('vi-VN');
    await tts.setSpeechRate(0.45);
    await tts.awaitSpeakCompletion(true);
    // Keep each utterance within Android's TTS input limit; preserve full answer.
    final limit = await tts.getMaxSpeechInputLength ?? 4000;
    final size = limit > 0 ? limit : 4000;
    for (var offset = 0; offset < text.length; offset += size) {
      if (run != _readRun) break;
      final end = (offset + size).clamp(0, text.length).toInt();
      await tts.speak(text.substring(offset, end));
    }
  }
  int _readRun = 0;
  @override
  Future<void> stopSpeaking() async { _readRun++; await tts.stop(); }
}

class VoiceController extends ChangeNotifier {
  final VoiceEngine engine;
  bool listening = false, speaking = false, starting = false;
  String? error;
  bool _disposed = false;
  int _generation = 0;
  VoiceController({VoiceEngine? engine}) : engine = engine ?? AndroidVoiceEngine();
  void _changed() { if (!_disposed) notifyListeners(); }

  Future<void> start(void Function(String) onWords) async {
    if (_disposed || starting || listening) return;
    final run = ++_generation;
    starting = true; error = null; _changed();
    try {
      await engine.stopSpeaking();
      if (run != _generation || _disposed) return;
      speaking = false;
      final available = await engine.initialize((status) {
        if (status == 'done' || status == 'notListening') {
          listening = false; _changed();
        }
      }, (message) {
        listening = false;
        error = 'Chưa nhận dạng được giọng nói: $message. Bạn vẫn có thể nhập chữ.';
        _changed();
      });
      if (run != _generation || _disposed) return;
      if (!available) {
        throw Exception('Chưa được cấp quyền micro hoặc máy chưa có dịch vụ nhận dạng giọng nói.');
      }
      final locales = await engine.locales();
      if (run != _generation || _disposed) return;
      final vietnamese = locales.where((l) => l.toLowerCase().replaceAll('-', '_').startsWith('vi_')).toList();
      if (vietnamese.isEmpty) {
        throw Exception('Chưa có nhận dạng tiếng Việt. Cài hoặc bật tiếng Việt trong dịch vụ giọng nói Android.');
      }
      listening = true; _changed();
      await engine.listen(vietnamese.first, (words) {
        if (!_disposed && run == _generation) onWords(words);
      });
    } catch (e) {
      if (run == _generation && !_disposed) {
        listening = false; error = '$e';
      }
    } finally {
      if (run == _generation && !_disposed) { starting = false; _changed(); }
    }
  }

  Future<void> read(String text) async {
    if (_disposed || text.trim().isEmpty) return;
    final run = ++_generation;
    listening = false; starting = false; speaking = true; error = null; _changed();
    try {
      await engine.cancel(); await engine.stopSpeaking();
      if (run != _generation || _disposed) return;
      await engine.speak(text);
    } catch (e) {
      if (run == _generation && !_disposed) error = '$e';
    } finally {
      if (run == _generation && !_disposed) { speaking = false; _changed(); }
    }
  }

  Future<void> stop() async {
    _generation++; listening = false; speaking = false; starting = false; _changed();
    try { await engine.cancel(); } catch (_) {}
    try { await engine.stopSpeaking(); } catch (_) {}
  }
  @override
  void dispose() {
    _disposed = true; _generation++;
    // Plugin cleanup is asynchronous; late callbacks must never update the UI.
    engine.cancel().catchError((Object _) {});
    engine.stopSpeaking().catchError((Object _) {});
    super.dispose();
  }
}

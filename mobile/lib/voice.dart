import 'speech_transcript.dart';
import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_to_text.dart';

/// Allows permission/lifecycle behavior to be tested without a microphone.
abstract class VoiceEngine {
  bool get recordsAudio => false;
  Future<void> finish() => cancel();
  Future<void> close() => cancel();
  Future<bool> initialize(void Function(String) status, void Function(String) error);
  Future<List<String>> locales();
  Future<void> listen(String locale, void Function(String) words);
  Future<void> cancel();
  Future<void> speak(String text);
  Future<void> stopSpeaking();
}

bool vietnameseLocale(String value) => value.toLowerCase().replaceAll('_', '-').split('-').first == 'vi';
Map<String, String>? vietnameseVoice(dynamic values) {
  if (values is! List) return null;
  for (final value in values) {
    if (value is Map && value['locale'] is String && value['name'] is String && vietnameseLocale(value['locale'] as String)) {
      return {'name': value['name'] as String, 'locale': value['locale'] as String};
    }
  }
  return null;
}
Future<void> openVoiceSettings(bool tts) => const MethodChannel('vn.chatai/voice_settings')
    .invokeMethod<void>(tts ? 'tts' : 'speech');

class AndroidVoiceEngine extends VoiceEngine {
  void Function(double)? onLevel;
  // SpeechToText is a process-wide singleton and retains initialize callbacks.
  // Route those callbacks to the current dictation/voice-chat session.
  static void Function(String)? _status;
  static void Function(String)? _error;
  final SpeechToText speech = SpeechToText();
  final FlutterTts tts = FlutterTts();
  @override
  Future<bool> initialize(void Function(String) status, void Function(String) error) {
    _status = status; _error = error;
    return speech.initialize(onStatus: (value) => _status?.call(value),
      onError: (e) => _error?.call(e.errorMsg));
  }
  @override
  // Some Android recognizers hang while enumerating installed locales.
  // Request Vietnamese directly; the recognizer reports unsupported languages.
  Future<List<String>> locales() async => ['vi-VN'];
  @override
  Future<void> listen(String locale, void Function(String) words) async {
    await speech.listen(listenFor: const Duration(seconds: 60),
      pauseFor: const Duration(seconds: 4),
      listenOptions: SpeechListenOptions(localeId: locale, partialResults: true, cancelOnError: true,
        listenMode: ListenMode.dictation),
      onSoundLevelChange: (level) => onLevel?.call(level),
      onResult: (result) => words(result.recognizedWords));
    // Some Android recognition services return without starting or throwing.
    for (var attempt = 0; attempt < 10 && !speech.isListening; attempt++) {
      await Future<void>.delayed(const Duration(milliseconds: 100));
    }
    if (!speech.isListening) {
      throw Exception('Không mở được nhận dạng giọng nói. Kiểm tra quyền micro và bật dịch vụ nhận dạng giọng nói trong cài đặt Android.');
    }
  }
  @override
  Future<void> cancel() => speech.cancel();
  @override
  Future<void> speak(String text) async {
    final run = ++_readRun;
    var selected = vietnameseVoice(await tts.getVoices.timeout(const Duration(seconds: 12)));
    if (run != _readRun) return;
    if (selected == null) {
      final engines = await tts.getEngines.timeout(const Duration(seconds: 8));
      if (run != _readRun) return;
      if (engines is List && engines.contains('com.google.android.tts')) {
        await tts.setEngine('com.google.android.tts').timeout(const Duration(seconds: 10));
        selected = vietnameseVoice(await tts.getVoices.timeout(const Duration(seconds: 12)));
      }
    }
    if (run != _readRun) return;
    if (selected != null) {
      await tts.setLanguage(selected['locale']!);
      await tts.setVoice(selected);
    } else {
      final available = await tts.isLanguageAvailable('vi-VN').timeout(const Duration(seconds: 8));
      if (run != _readRun) return;
      if (available != true && available != 1) {
        throw Exception('Chưa có giọng đọc tiếng Việt trên máy. Mở cài đặt giọng đọc để chọn hoặc tải tiếng Việt.');
      }
      await tts.setLanguage('vi-VN');
    }
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
  bool listening = false, speaking = false, starting = false, transcribing = false;
  double soundLevel = 0;
  String? error;
  bool recognitionError = false;
  bool _disposed = false;
  int _generation = 0;
  Timer? _recognitionWatchdog;
  static const noWordsTimeout = Duration(seconds: 12);
  VoiceController({VoiceEngine? engine}) : engine = engine ?? AndroidVoiceEngine() {
    if (this.engine is AndroidVoiceEngine) {
      (this.engine as AndroidVoiceEngine).onLevel = (level) {
        if (!_disposed && listening) { soundLevel = ((level + 2) / 12).clamp(0.0, 1.0).toDouble(); _changed(); }
      };
    }
  }
  void _changed() { if (!_disposed) notifyListeners(); }

  Future<void> start(void Function(String) onWords) async {
    if (_disposed || starting || listening) return;
    _recognitionWatchdog?.cancel();
    final run = ++_generation;
    var receivedWords = false;
    var ended = false;
    starting = true; recognitionError = true; error = null; _changed();
    try {
      await engine.stopSpeaking();
      if (run != _generation || _disposed) return;
      speaking = false;
      final available = await engine.initialize((status) {
        if (run != _generation || _disposed) return;
        if (status == 'transcribing') { transcribing = true; listening = false; _recognitionWatchdog?.cancel(); _changed(); }
        if (status == 'listening') { listening = true; _changed(); }
        if (status == 'done' || status == 'notListening') {
          ended = true; transcribing = false;
          _recognitionWatchdog?.cancel();
          listening = false;
          if (!starting && !receivedWords && error == null) {
            error = 'Chưa nghe được lời nói. Hãy bấm mic và nói lại; kiểm tra quyền micro nếu vẫn không nhận chữ.';
          }
          _changed();
        }
      }, (message) {
        if (run != _generation || _disposed) return;
        ended = true; transcribing = false;
        _recognitionWatchdog?.cancel();
        listening = false;
        error = ['error_language_unavailable', 'error_language_not_supported'].contains(message)
          ? 'Dịch vụ nhận dạng trên máy chưa dùng được tiếng Việt. Chọn dịch vụ nhận dạng Google và bật hoặc tải tiếng Việt trong cài đặt giọng nói Android. Bạn vẫn có thể nhập chữ.'
          : 'Chưa nhận dạng được giọng nói: $message. Bạn vẫn có thể nhập chữ.';
        _changed();
      }).timeout(const Duration(seconds: 20), onTimeout: () => throw TimeoutException('Mở micro quá lâu. Kiểm tra quyền micro và dịch vụ nhận dạng giọng nói Android.'));
      if (run != _generation || _disposed) return;
      if (!available) {
        throw Exception('Chưa được cấp quyền micro hoặc máy chưa có dịch vụ nhận dạng giọng nói.');
      }
      final locales = await engine.locales().timeout(const Duration(seconds: 10), onTimeout: () => throw Exception('Không lấy được ngôn ngữ nhận dạng. Mở cài đặt dịch vụ giọng nói và thử lại.'));
      if (run != _generation || _disposed) return;
      final vietnamese = locales.where((l) => l.toLowerCase() == 'vi' || l.toLowerCase().replaceAll('-', '_').startsWith('vi_')).toList();
      if (vietnamese.isEmpty) {
        throw Exception('Chưa có nhận dạng tiếng Việt. Cài hoặc bật tiếng Việt trong dịch vụ giọng nói Android.');
      }
      await engine.listen(vietnamese.first, (words) {
        final cleaned=cleanRecognizedSpeech(words);
        if (!_disposed && run == _generation && cleaned.isNotEmpty) {
          receivedWords = true;
          _recognitionWatchdog?.cancel();
          onWords(cleaned);
        }
      }).timeout(const Duration(seconds: 15), onTimeout: () => throw Exception('Dịch vụ nhận dạng không mở được mic. Kiểm tra quyền micro, dịch vụ nhận dạng và kết nối mạng rồi thử lại.'));
      if (run == _generation && !_disposed && error == null) {
        if (ended && !receivedWords) {
          error = 'Chưa nghe được lời nói. Bấm mic và nói lại; kiểm tra dịch vụ nhận dạng trong cài đặt Android.';
        } else if (!ended) {
          listening = true;
          if (!receivedWords && !engine.recordsAudio) {
            _recognitionWatchdog = Timer(noWordsTimeout, () {
              if (_disposed || run != _generation || receivedWords || !listening) return;
              _generation++;
              listening = false; starting = false; soundLevel = 0;
              error = 'Chưa nhận được chữ từ micro. Kiểm tra quyền micro, kết nối mạng và dịch vụ nhận dạng giọng nói Android rồi thử lại.';
              unawaited(engine.cancel().catchError((Object _) {}));
              _changed();
            });
          }
        }
      }
    } catch (e) {
      if (run == _generation && !_disposed) {
        _generation++;
        listening = false; starting = false; error = '$e';
        unawaited(engine.cancel().catchError((Object _) {}));
        _changed();
      }
    } finally {
      if (run == _generation && !_disposed) { starting = false; _changed(); }
    }
  }

  Future<void> finishListening() async {
    if (engine.recordsAudio && listening) { await engine.finish(); }
    else { await stop(); }
  }

  Future<void> read(String text) async {
    if (_disposed || text.trim().isEmpty) return;
    _recognitionWatchdog?.cancel();
    final run = ++_generation;
    listening = false; starting = false; speaking = true; recognitionError = false; error = null; _changed();
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
    _recognitionWatchdog?.cancel();
    _generation++; transcribing = false; listening = false; speaking = false; starting = false; _changed();
    try { await engine.cancel(); } catch (_) {}
    try { await engine.stopSpeaking(); } catch (_) {}
  }
  @override
  void dispose() {
    _recognitionWatchdog?.cancel();
    _disposed = true; _generation++;
    // Plugin cleanup is asynchronous; late callbacks must never update the UI.
    engine.close().catchError((Object _) {});
    engine.stopSpeaking().catchError((Object _) {});
    super.dispose();
  }
}

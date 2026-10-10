import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:chatai_mobile/voice.dart';

class FakeVoice implements VoiceEngine {
  bool available = true;
  List<String> supported = ['en_US', 'vi_VN'];
  String? selected, readText;
  void Function(String)? recognition;
  int cancels = 0, stops = 0;
  bool failListen = false;
  void Function(String)? status;
  Completer<bool>? permission;
  Completer<void>? reading;
  @override
  Future<bool> initialize(void Function(String) status, void Function(String) error) async =>
      _initialize(status);
  Future<bool> _initialize(void Function(String) callback) async {
    status = callback;
    return permission == null ? available : await permission!.future;
  }
  @override
  Future<List<String>> locales() async => supported;
  @override
  Future<void> listen(String locale, void Function(String) words) async {
    if (failListen) throw Exception('Không mở được nhận dạng giọng nói');
    selected = locale; recognition = words;
  }
  @override
  Future<void> cancel() async { cancels++; }
  @override
  Future<void> speak(String text) async { readText = text; await reading?.future; }
  @override
  Future<void> stopSpeaking() async { stops++; }
}

void main() {
  test('recognizer start failure resets mic and shows the error', () async {
    final engine = FakeVoice()..failListen = true;
    final voice = VoiceController(engine: engine); addTearDown(voice.dispose);
    await voice.start((_) {});
    expect(voice.listening, isFalse); expect(voice.starting, isFalse);
    expect(voice.error, contains('Không mở được'));
  });
  test('empty recognition ends with guidance instead of silent failure', () async {
    final engine = FakeVoice();
    final voice = VoiceController(engine: engine); addTearDown(voice.dispose);
    await voice.start((_) {});
    engine.status!('done');
    expect(voice.listening, isFalse);
    expect(voice.error, contains('Chưa nghe được'));
  });

  test('Vietnamese bare language code can start dictation', () async {
    final engine = FakeVoice()..supported = ['vi'];
    final voice = VoiceController(engine: engine);
    addTearDown(voice.dispose);
    await voice.start((_) {});
    expect(engine.selected, 'vi');
    expect(voice.listening, isTrue);
  });

  test('Vietnamese dictation only supplies editable text, not an AI request', () async {
    final engine = FakeVoice(); final voice = VoiceController(engine: engine);
    addTearDown(voice.dispose); var draft = '';
    await voice.start((text) => draft = text);
    expect(engine.selected, 'vi_VN'); expect(voice.listening, isTrue);
    engine.recognition!('Tính bài toán hố đào');
    expect(draft, 'Tính bài toán hố đào');
    await voice.stop(); engine.recognition!('callback muộn');
    expect(draft, 'Tính bài toán hố đào'); expect(voice.listening, isFalse);
  });
  test('permission denied leaves keyboard available and reports error', () async {
    final engine = FakeVoice()..available = false;
    final voice = VoiceController(engine: engine); addTearDown(voice.dispose);
    await voice.start((_) => fail('No recognition without permission'));
    expect(voice.listening, isFalse); expect(voice.starting, isFalse);
    expect(voice.error, contains('quyền micro')); expect(engine.selected, isNull);
  });
  test('missing Vietnamese recognizer does not silently select another language', () async {
    final engine = FakeVoice()..supported = ['en_US'];
    final voice = VoiceController(engine: engine); addTearDown(voice.dispose);
    await voice.start((_) {});
    expect(engine.selected, isNull); expect(voice.error, contains('tiếng Việt'));
  });
  test('background stop during permission request prevents late microphone start', () async {
    final engine = FakeVoice()..permission = Completer<bool>();
    final voice = VoiceController(engine: engine); addTearDown(voice.dispose);
    final pending = voice.start((_) {});
    await Future<void>.delayed(Duration.zero);
    await voice.stop(); engine.permission!.complete(true); await pending;
    expect(engine.selected, isNull); expect(voice.starting, isFalse);
  });
  test('reading and microphone are mutually exclusive and stoppable', () async {
    final engine = FakeVoice()..reading = Completer<void>();
    final voice = VoiceController(engine: engine); addTearDown(voice.dispose);
    await voice.start((_) {});
    final pending = voice.read('Kết quả hệ số an toàn');
    await Future<void>.delayed(Duration.zero);
    expect(voice.speaking, isTrue); expect(voice.listening, isFalse);
    expect(engine.readText, 'Kết quả hệ số an toàn');
    await voice.stop(); engine.reading!.complete(); await pending;
    expect(voice.speaking, isFalse); expect(engine.cancels, greaterThan(0));
  });
}

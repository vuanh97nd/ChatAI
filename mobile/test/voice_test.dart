import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:chatai_mobile/voice.dart';

class FakeVoice extends VoiceEngine {
  bool available = true;
  List<String> supported = ['en_US', 'vi_VN'];
  String? selected, readText;
  void Function(String)? recognition;
  int cancels = 0, stops = 0;
  bool failListen = false;
  void Function(String)? status, recognitionError;
  Completer<bool>? permission;
  Completer<void>? reading;
  @override
  Future<bool> initialize(void Function(String) status, void Function(String) error) async {
    recognitionError = error;
    return _initialize(status);
  }
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

class FakeAudioVoice extends FakeVoice {
  @override
  bool get recordsAudio => true;
  @override
  Future<void> finish() async {
    status!('transcribing'); recognition!('Nội dung từ Cloudflare'); status!('done');
  }
}

void main() {
  testWidgets('a device recognizer that ends without words reports failure instead of silence', (tester) async {
    final engine = FakeVoice(); final voice = VoiceController(engine: engine); addTearDown(voice.dispose);
    await voice.start((_) => fail('No words were produced'));
    final finishing = voice.finishListening(); await tester.pump(); await tester.pump(const Duration(milliseconds: 600)); await finishing;
    expect(voice.listening, isFalse); expect(voice.error, contains('Bộ nhận dạng chưa trả chữ'));
  });
  testWidgets('finishing device recognition preserves words and ends a stalled listener', (tester) async {
    final engine = FakeVoice(); final voice = VoiceController(engine: engine); addTearDown(voice.dispose);
    var text = ''; await voice.start((words) => text = words); engine.recognition!('Câu hỏi đã nhận');
    final finishing = voice.finishListening(); await tester.pump(); await tester.pump(const Duration(milliseconds: 600)); await finishing;
    expect(text, 'Câu hỏi đã nhận'); expect(voice.listening, isFalse); expect(voice.error, isNull);
  });
  testWidgets('cloud capture is independent of native recognition and finishes with text', (tester) async {
    final engine = FakeAudioVoice();
    final voice = VoiceController(engine: engine); addTearDown(voice.dispose);
    var text = ''; var sawTranscribing = false;
    voice.addListener(() { if (voice.transcribing) sawTranscribing = true; });
    await voice.start((words) => text = words);
    await tester.pump(VoiceController.noWordsTimeout);
    expect(voice.listening, isTrue);
    await voice.finishListening();
    expect(sawTranscribing, isTrue); expect(text, 'Nội dung từ Cloudflare');
    expect(voice.listening, isFalse); expect(voice.transcribing, isFalse);
    expect(voice.error, isNull);
  });

  test('Vietnamese voice selection accepts Android locale formats', () {
    expect(vietnameseVoice([{'name': 'English', 'locale': 'en-US'},
      {'name': 'Vietnamese', 'locale': 'vi_VN'}]), {'name': 'Vietnamese', 'locale': 'vi_VN'});
    expect(vietnameseVoice([{'name': 'vi', 'locale': 'vi'}]), isNotNull);
    expect(vietnameseVoice([{'name': 'English', 'locale': 'en-US'}]), isNull);
  });

  test('missing recognition language directs to speech settings, not TTS', () async {
    final engine = FakeVoice();
    final voice = VoiceController(engine: engine); addTearDown(voice.dispose);
    await voice.start((_) {});
    engine.recognitionError!('error_language_unavailable');
    expect(voice.listening, isFalse);
    expect(voice.recognitionError, isTrue);
    expect(voice.error, contains('dịch vụ nhận dạng Google'));
    expect(voice.error, isNot(contains('error_language_unavailable')));
  });
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

  testWidgets('recognizer with no words cannot stay listening indefinitely', (tester) async {
    final engine = FakeVoice();
    final voice = VoiceController(engine: engine); addTearDown(voice.dispose);
    await voice.start((_) {});
    await tester.pump(VoiceController.noWordsTimeout);
    expect(voice.listening, isFalse);
    expect(voice.error, contains('Chưa nhận được chữ'));
    expect(engine.cancels, greaterThan(0));
  });
  testWidgets('partial words appear immediately and cancel the empty result timeout', (tester) async {
    final engine = FakeVoice();
    final voice = VoiceController(engine: engine); addTearDown(voice.dispose);
    var text = '';
    await voice.start((words) => text = words);
    engine.recognition!('xin');
    expect(text, 'xin');
    engine.recognition!('xin chào');
    expect(text, 'xin chào');
    await tester.pump(VoiceController.noWordsTimeout);
    expect(voice.error, isNull);
    engine.status!('done');
    expect(voice.listening, isFalse);
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

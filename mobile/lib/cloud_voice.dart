import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:record/record.dart';
import 'api.dart';
import 'voice.dart';
import 'speech_transcript.dart';
import 'tts_text.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:http/http.dart' as http;

Uint8List pcmWave(Uint8List pcm) {
  final result = Uint8List(44 + pcm.length);
  final header = ByteData.sublistView(result);
  void tag(int offset, String text) => result.setRange(offset, offset + 4, ascii.encode(text));
  tag(0, 'RIFF'); header.setUint32(4, result.length - 8, Endian.little);
  tag(8, 'WAVE'); tag(12, 'fmt '); header.setUint32(16, 16, Endian.little);
  header.setUint16(20, 1, Endian.little); header.setUint16(22, 1, Endian.little);
  header.setUint32(24, 16000, Endian.little); header.setUint32(28, 32000, Endian.little);
  header.setUint16(32, 2, Endian.little); header.setUint16(34, 16, Endian.little);
  tag(36, 'data'); header.setUint32(40, pcm.length, Endian.little);
  result.setRange(44, result.length, pcm);
  return result;
}

/// Records PCM directly. Android SpeechRecognizer is never used here.
class CloudVoiceEngine extends AndroidVoiceEngine {
  @override
  bool get recordsAudio => true;
  final ChatApi api;
  final AudioRecorder recorder = AudioRecorder();
  final AudioPlayer speaker = AudioPlayer();
  bool cloudSpeechAvailable = true;
  bool useCloudSpeech = true;
  String speechProvider = 'auto';
  int speechRun = 0;
  @override
  Future<void> speak(String text) async {
    final run = ++speechRun;
    if (!useCloudSpeech || !cloudSpeechAvailable) { onSpeechMode?.call(!useCloudSpeech ? 'Giọng trên điện thoại' : 'Giọng điện thoại · API chưa cấu hình'); await super.speak(text); return; }
    onSpeechMode?.call('Giọng AI trực tuyến');
    var localForTurn = false;
    try {
      for (final chunk in speechChunks(text, 320)) {
        if (run != speechRun) return;
        if (localForTurn) { await super.speak(chunk); continue; }
        final session = api.session;
        if (session == null) throw ApiException('Đăng nhập để dùng giọng đọc AI.', 401);
        http.Response result;
        try {
        result = await api.client.post(api.server.resolve('/api/voice/speak'),
          headers: {'Content-Type': 'application/json', 'Accept': 'audio/*, application/json', 'User-Agent': 'ChatAI-Android/1.1.2'},
          body: jsonEncode({'username': session.username, 'key': session.key, 'text': chunk, 'speech_provider': speechProvider})).timeout(const Duration(seconds: 15));
        } on TimeoutException {
          if (run != speechRun) return;
          localForTurn = true;
          onSpeechMode?.call('Giọng điện thoại · API phản hồi chậm');
          await super.speak(chunk);
          continue;
        }
        if (run != speechRun) return;
        if (result.statusCode != 200 || !(result.headers['content-type'] ?? '').startsWith('audio/')) {
          if (result.statusCode == 503) {
            final value = jsonDecode(utf8.decode(result.bodyBytes));
            if (value['code'] == 'TTS_NOT_CONFIGURED') cloudSpeechAvailable = false;
          }
          localForTurn = true;
          onSpeechMode?.call(cloudSpeechAvailable ? 'Giọng điện thoại · API tạm lỗi' : 'Giọng điện thoại · API chưa cấu hình');
          // Fall back for this remaining chunk only; never repeat spoken audio.
          await super.speak(chunk);
          continue;
        }
        final actualProvider = result.headers['x-chatai-speech-provider'];
        onSpeechMode?.call(actualProvider == 'gemini' ? 'Giọng AI · Gemini' : 'Giọng AI · OpenAI');
        final complete = Completer<void>();
        final subscription = speaker.onPlayerComplete.listen((_) { if (!complete.isCompleted) complete.complete(); });
        final deadline = DateTime.now().add(const Duration(minutes: 3));
        try {
          await speaker.play(BytesSource(result.bodyBytes, mimeType: result.headers['content-type']?.split(';').first ?? 'audio/mpeg'));
          while (!complete.isCompleted && run == speechRun) {
            if (DateTime.now().isAfter(deadline)) throw TimeoutException('Phát giọng đọc quá lâu.');
            await Future.any<void>([complete.future, Future<void>.delayed(const Duration(milliseconds: 100))]);
          }
        } finally { await subscription.cancel(); }
      }
    } on TimeoutException {
      if (run == speechRun) throw ApiException('Giọng đọc AI chờ quá lâu. Hãy thử lại hoặc dùng giọng trên máy.');
    }
  }
  @override
  Future<void> stopSpeaking() async { speechRun++; await speaker.stop(); await super.stopSpeaking(); }

  final void Function(String)? onSpeechMode;
  CloudVoiceEngine(this.api, {this.onSpeechMode});
  StreamSubscription<Uint8List>? audioSub;
  StreamSubscription<Amplitude>? levelSub;
  Timer? limit, silence;
  BytesBuilder? audio;
  void Function(String)? status, failure, words;
  bool recording = false, transcribing = false, heardSound = false;
  int generation = 0;
  double noiseFloor = -50;
  int voicedFrames = 0;
  @override
  Future<bool> initialize(void Function(String) status, void Function(String) error) async {
    this.status = status; failure = error;
    if (api.session == null) throw Exception('Đăng nhập để dùng nhận dạng giọng nói Cloudflare.');
    return recorder.hasPermission();
  }
  @override
  Future<List<String>> locales() async => ['vi-VN'];
  @override
  Future<void> listen(String locale, void Function(String) words) async {
    final run = ++generation;
    this.words = words; audio = BytesBuilder(copy: false); heardSound = false; noiseFloor = -50; voicedFrames = 0;
    final stream = await recorder.startStream(const RecordConfig(
      encoder: AudioEncoder.pcm16bits, sampleRate: 16000, numChannels: 1));
    if (run != generation) { await recorder.stop(); return; }
    recording = true; status?.call('listening');
    audioSub = stream.listen((bytes) {
      if (run != generation || !recording) return;
      final remaining = 960000 - (audio?.length ?? 0);
      if (remaining > 0) audio?.add(bytes.length <= remaining ? bytes : bytes.sublist(0, remaining));
      if ((audio?.length ?? 0) >= 960000) unawaited(finish());
    }, onError: (Object _) { unawaited(cancel()); failure?.call('Không thu được âm thanh từ micro.'); });
    levelSub = recorder.onAmplitudeChanged(const Duration(milliseconds: 150)).listen((level) {
      if (run != generation || !recording) return;
      onLevel?.call(((level.current + 60) / 60).clamp(0.0, 1.0) * 12 - 2);
      final threshold = (noiseFloor + 10).clamp(-50.0, -30.0);
      if (level.current > threshold) {
        voicedFrames++;
        if (voicedFrames >= 2) heardSound = true;
        silence?.cancel(); silence = null;
      } else {
        voicedFrames = 0;
        if (!heardSound) noiseFloor = (noiseFloor * .8 + level.current * .2).clamp(-65.0, -38.0);
        if (heardSound && silence == null) {
          silence = Timer(const Duration(milliseconds: 850), () { silence = null; unawaited(finish()); });
        }
      }
    });
    limit = Timer(const Duration(seconds: 30), () => unawaited(finish()));
  }
  @override
  Future<void> finish() async {
    if (!recording || transcribing) return;
    final run = generation;
    recording = false; transcribing = true; limit?.cancel(); silence?.cancel(); silence = null;
    status?.call('transcribing');
    try {
      await recorder.stop().timeout(const Duration(seconds: 5)); await audioSub?.cancel(); await levelSub?.cancel();
      final pcm = audio?.takeBytes() ?? Uint8List(0); audio = null;
      if (pcm.length < 3200 || !hasSpeechEnergy(pcm)) throw Exception('Chưa nghe rõ lời nói. Hãy nói gần micro rồi bấm gửi.');
      final result = await api.post('/api/voice/transcribe', {'audio': base64Encode(pcmWave(pcm))})
        .timeout(const Duration(seconds: 45));
      if (run != generation) return;
      final text=cleanRecognizedSpeech(result['text'] as String);
      if(text.isEmpty) throw Exception('Chưa nhận được lời nói rõ ràng. Vui lòng thu lại.');
      words?.call(text); status?.call('done');
    } catch (e) { if (run == generation) failure?.call('$e'); }
    finally { if (run == generation) transcribing = false; }
  }
  @override
  Future<void> cancel() async {
    generation++; recording = false; transcribing = false;
    limit?.cancel(); silence?.cancel(); silence = null;
    try { await recorder.stop().timeout(const Duration(seconds: 5)); } finally {
      await audioSub?.cancel(); await levelSub?.cancel(); audio = null;
    }
  }
  @override
  Future<void> close() async { await cancel(); await recorder.dispose(); await speaker.dispose(); }
}

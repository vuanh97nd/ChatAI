import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:record/record.dart';
import 'api.dart';
import 'voice.dart';
import 'speech_transcript.dart';

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
  CloudVoiceEngine(this.api);
  StreamSubscription<Uint8List>? audioSub;
  StreamSubscription<Amplitude>? levelSub;
  Timer? limit, silence;
  BytesBuilder? audio;
  void Function(String)? status, failure, words;
  bool recording = false, transcribing = false, heardSound = false;
  int generation = 0;
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
    this.words = words; audio = BytesBuilder(copy: false); heardSound = false;
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
      if (level.current > -40) {
        heardSound = true; silence?.cancel(); silence = null;
      } else if (heardSound && silence == null) {
        silence = Timer(const Duration(seconds: 2), () { silence = null; unawaited(finish()); });
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
  Future<void> close() async { await cancel(); await recorder.dispose(); }
}

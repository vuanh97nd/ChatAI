import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:chatai_mobile/cloud_voice.dart';
void main() {
  test('PCM is wrapped as mono 16kHz WAV without changing samples', () {
    final pcm = Uint8List.fromList([1, 2, 3, 4]);
    final wav = pcmWave(pcm);
    final header = ByteData.sublistView(wav);
    expect(String.fromCharCodes(wav.sublist(0, 4)), 'RIFF');
    expect(header.getUint32(24, Endian.little), 16000);
    expect(header.getUint16(22, Endian.little), 1);
    expect(header.getUint16(34, Endian.little), 16);
    expect(header.getUint32(40, Endian.little), 4);
    expect(wav.sublist(44), pcm);
  });
}

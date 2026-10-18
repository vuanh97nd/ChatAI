import 'dart:math' as math;
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:chatai_mobile/pcm_endpoint.dart';
Uint8List tone(int frames) {
 final bytes=Uint8List(frames*640); final view=ByteData.sublistView(bytes);
 for(var i=0;i<bytes.length~/2;i++) { view.setInt16(i*2,(math.sin(i*.17)*6000).round(),Endian.little); }
 return bytes;
}
void main(){
 test('speech resumed inside a buffered chunk keeps the microphone open',(){
  final vad=PcmEndpoint();expect(vad.add(Uint8List.fromList([...tone(20),...Uint8List(40*640),...tone(20)])),isFalse);
 });
 test('PCM silence ends an utterance without any Android amplitude events',(){
  final vad=PcmEndpoint();expect(vad.add(tone(20)),isFalse);expect(vad.heardSpeech,isTrue);
  expect(vad.add(Uint8List(39*640)),isFalse);expect(vad.add(Uint8List(640)),isTrue);
 });
 test('silence or a brief click alone does not count as speech',(){
  final vad=PcmEndpoint();expect(vad.add(Uint8List(100*640)),isFalse);expect(vad.heardSpeech,isFalse);
  expect(vad.add(tone(1)),isFalse);expect(vad.add(Uint8List(50*640)),isFalse);
 });
 test('odd byte stream boundaries retain complete PCM samples',(){
  final bytes=Uint8List.fromList([...tone(20),...Uint8List(40*640)]);final vad=PcmEndpoint();var ended=false;
  for(var i=0;i<bytes.length;i+=777){ended=vad.add(Uint8List.sublistView(bytes,i,math.min(i+777,bytes.length)))||ended;}
  expect(ended,isTrue);expect(vad.heardSpeech,isTrue);
 });
}

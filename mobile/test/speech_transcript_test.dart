import 'dart:math';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:chatai_mobile/speech_transcript.dart';
void main(){
 test('silence and microphone clicks do not qualify as speech',(){
  final pcm=Uint8List(32000);expect(hasSpeechEnergy(pcm),false);
  ByteData.sublistView(pcm).setInt16(100,30000,Endian.little);expect(hasSpeechEnergy(pcm),false);
 });
 test('sustained audible PCM qualifies',(){
  final pcm=Uint8List(16000),data=ByteData.sublistView(pcm);
  for(var i=0;i<pcm.length;i+=2){data.setInt16(i,(sin(i*pi/40)*2000).round(),Endian.little);}
  expect(hasSpeechEnergy(pcm),true);
 });
 test('known caption is stripped while the real question remains',(){
  expect(cleanRecognizedSpeech('Thời tiết Hà Nội? Các bạn hãy đăng ký cho kênh lalaschool để không bỏ lỡ những video hấp dẫn.'),'Thời tiết Hà Nội?');
  expect(cleanRecognizedSpeech('Hãy subscribe cho kênh La La School Để không bỏ lỡ những video hấp dẫn'),'');
  expect(cleanRecognizedSpeech('Thời tiết hôm nay? Hãy subscribe cho kênh La La School để không bỏ lỡ những video hấp dẫn.'),'Thời tiết hôm nay?');
  expect(cleanRecognizedSpeech('Lalaschool'),'');
  expect(cleanRecognizedSpeech('Kênh Lalaschool là gì?'),'Kênh Lalaschool là gì?');
 });
}

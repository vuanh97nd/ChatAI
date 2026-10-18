import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:chatai_mobile/api.dart';
import 'package:chatai_mobile/cloud_voice.dart';

void main() {
 testWidgets('transcription after 20 seconds is accepted without a 15-second cutoff or replay', (tester) async {
  var calls=0;
  final api=ChatApi(client:MockClient((request) async {
   calls++;
   await Future<void>.delayed(const Duration(seconds:20));
   return http.Response(jsonEncode({'success':true,'text':'Xin chao'}),200);
  }))..session=Session('owner','session:test','Owner');
  String? text;Object? error;
  final pending=transcribePcm(api,Uint8List(12800)).then((value){text=value;},onError:(Object e){error=e;});
  await tester.pump();await tester.pump(const Duration(seconds:16));
  expect(error,isNull);expect(text,isNull);
  await tester.pump(const Duration(seconds:4));await pending;
  expect(text,'Xin chao');expect(error,isNull);expect(calls,1);api.close();
 });
}

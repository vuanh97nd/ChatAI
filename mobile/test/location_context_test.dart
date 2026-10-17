import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import '../lib/api.dart';
import '../lib/location_context.dart';

void main() {
 test('weather without a city requests coordinates and sends them only to weather search', () async {
  var locations=0;
  final api=ChatApi(locate:() async {locations++;return const NearbyPosition(21.02,105.84);},client:MockClient((r) async {
   final body=jsonDecode(r.body);
   if(r.url.path=='/api/chat/search'){
    expect(body['weather_coordinates'],{'latitude':21.02,'longitude':105.84});
    return http.Response(jsonEncode({'success':true,'answer':'25 C','sources':[{'title':'Weather','url':'https://open-meteo.com/en/docs'}]}),200);
   }
   expect(body.containsKey('weather_coordinates'),isFalse);
   return http.Response(jsonEncode({'success':true,'answer':'25 C'}),200);
  }))..session=Session('alice','session:test','Alice');
  addTearDown(api.close);
  expect(await api.answer('gemini',[{'role':'user','content':'Thời tiết hôm nay?'}],[]),contains('25 C'));expect(locations,1);
 });
 test('named city and ordinary questions never request GPS', () async {
  var locations=0;
  final api=ChatApi(locate:() async {locations++;return null;},client:MockClient((r) async=>http.Response(jsonEncode({'success':true,'answer':'Hello','sources':[{'title':'Weather','url':'https://example.org/weather'}]}),200)))..session=Session('alice','session:test','Alice');
  addTearDown(api.close);
  await api.answer('gemini',[{'role':'user','content':'Xin chào'}],[]);
  await api.answer('gemini',[{'role':'user','content':'Thời tiết Hà Nội hôm nay?'}],[]);
  expect(locations,0);
 });
 test('denied GPS asks for a city without sending requests', () async {
  final api=ChatApi(locate:() async=>null,client:MockClient((_) async=>throw Exception('No network expected')))..session=Session('alice','session:test','Alice');
  addTearDown(api.close);
  expect(await api.answer('gemini',[{'role':'user','content':'Thời tiết hôm nay?'}],[]),contains('tỉnh/thành phố'));
 });
 test('nearby map returns a usable map link without fabricating places', () async {
  final api=ChatApi(locate:() async=>const NearbyPosition(21.02,105.84),client:MockClient((_) async=>throw Exception('No model expected')))..session=Session('alice','session:test','Alice');
  addTearDown(api.close);
  final result=await api.answer('gemini',[{'role':'user','content':'Tìm bản đồ quán cà phê gần tôi'}],[]);
  expect(result,contains('https://www.google.com/maps/search/'));expect(result,contains('chưa xác minh'));
 });
}

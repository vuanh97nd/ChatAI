import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:chatai_mobile/api.dart';
import 'package:chatai_mobile/live_search.dart';

void main(){
 test('weather asks location rather than inventing a city',(){
  expect(liveSearchPlan([{'role':'user','content':'Thời tiết hôm nay thế nào?'}])!.askLocation,true);
  expect(liveSearchPlan([{'role':'user','content':'Thời tiết ở Hồ Chí Minh hôm nay?'}])!.location,'Hồ Chí Minh');
  expect(liveSearchPlan([{'role':'user','content':'Thời tiết Chiang Mai hôm nay?'}])!.location,'Chiang Mai');
 });
 test('short location reply resolves the weather follow-up',(){
  final plan=liveSearchPlan([{'role':'user','content':'Thời tiết hôm nay?'},{'role':'assistant','content':'Bạn muốn xem thời tiết ở tỉnh/thành phố nào?'},{'role':'user','content':'Hà Nội'}]);
  expect(plan!.location,'Hà Nội');
 });
 test('news automatically searches; ordinary chats and thanks do not',(){
  expect(liveSearchPlan([{'role':'user','content':'Tin tức hôm nay'}])!.query,contains('Tin tức hôm nay'));
  expect(liveSearchPlan([{'role':'user','content':'Xin chào'}]),isNull);
  expect(liveSearchPlan([{'role':'user','content':'Thời tiết Hà Nội?'},{'role':'user','content':'Cảm ơn'}]),isNull);
 });
 test('current weather fetches sources before model and cites them',() async {
  final paths=<String>[];
  final api=ChatApi(endpoint:'https://primary.example',client:MockClient((r) async {
   paths.add(r.url.path);final body=jsonDecode(r.body) as Map<String,dynamic>;
   if(r.url.path=='/api/chat/search'){
    expect(body['weather_location'],'Hà Nội');
    return http.Response(jsonEncode({'success':true,'answer':'28 °C; 2026-10-16T18:00','sources':[{'title':'Weather source','url':'https://example.org/weather'}]}),200);
   }
   expect(jsonEncode(body['messages']),contains('28 °C'));
   return http.Response(jsonEncode({'success':true,'answer':'Nhiệt độ tại Hà Nội là 28 °C theo dữ liệu lúc 18:00 [1].'}),200);
  }));
  addTearDown(api.close);api.session=Session('alice','session:test','Alice');
  final result=await api.answer('gemini',[{'role':'user','content':'Thời tiết Hà Nội hôm nay?'}],[]);
  expect(paths,['/api/chat/search','/api/provider/model']);expect(result,contains('https://example.org/weather'));
 });
 test('missing city does not spend a model or search call',() async {
  var calls=0;final api=ChatApi(client:MockClient((r) async {calls++;throw Exception('unexpected');}));
  addTearDown(api.close);api.session=Session('alice','session:test','Alice');
  expect(await api.answer('gemini',[{'role':'user','content':'Thời tiết hôm nay?'}],[]),contains('tỉnh/thành phố'));
  expect(calls,0);
 });
}

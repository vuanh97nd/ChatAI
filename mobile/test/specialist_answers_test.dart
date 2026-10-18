import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import '../lib/api.dart';

void main(){
 test('news renders RSS items without an unnecessary model request or refusal',() async {
  var calls=0;
  final api=ChatApi(client:MockClient((r) async {
   calls++;expect(r.url.path,'/api/chat/search');
   return http.Response.bytes(utf8.encode(jsonEncode({'success':true,'source':'news','answer':'RSS data','items':[{'title':'Tin mới có nguồn','date':'Sun, 18 Oct 2026 07:00:00 +0700','text':'Trích đoạn đã xuất bản.','url':'https://vnexpress.net/example.html'}],'sources':[{'title':'News','url':'https://vnexpress.net/example.html'}]})),200);
  }))..session=Session('alice','session:test','Alice');
  addTearDown(api.close);
  final text=await api.answer('nvidia',[{'role':'user','content':'Tin tức hôm nay'}],[]);
  expect(text,contains('Tin mới có nguồn'));expect(text,contains('18 Oct 2026'));expect(text,contains('https://vnexpress.net/example.html'));expect(calls,1);
 });
 test('gold quote preserves units and missing publication timestamp without calling a model',() async {
  var calls=0;
  final api=ChatApi(client:MockClient((r) async {
   calls++;expect(r.url.path,'/api/chat/search');
   return http.Response.bytes(utf8.encode(jsonEncode({'success':true,'source':'gold_pnj','answer':'PNJ','updated_at':null,'searched_at':'2026-10-18T00:00:00Z','unit':'1.000 đồng/chỉ','items':[{'name':'Vàng SJC','buy':'14,060','sell':'14,360'}],'sources':[{'title':'PNJ','url':'https://www.pnj.com.vn/blog/gia-vang/'}]})),200);
  }))..session=Session('alice','session:test','Alice');
  addTearDown(api.close);
  final text=await api.answer('nvidia',[{'role':'user','content':'giá vàng hôm nay'}],[]);
  expect(text,contains('chưa thể xác nhận'));expect(text,contains('1.000 đồng/chỉ'));expect(text,contains('14,060'));expect(calls,1);
 });
}

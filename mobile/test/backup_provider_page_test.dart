import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:chatai_mobile/api.dart';
import 'package:chatai_mobile/backup_provider_page.dart';

void main() {
  testWidgets('saves backup key only to backup, clears input, then verifies real answer', (tester) async {
    final calls = <http.Request>[];
    final api = ChatApi(endpoint:'https://backup.example', client:MockClient((request) async {
      calls.add(request);
      expect(request.url.host,'backup.example');
      expect(jsonDecode(request.body)['key'],'backup-token');
      return http.Response('{"success":true,"answer":"OK"}',200);
    }))..session=Session('admin','backup-token','',admin:true);
    await tester.pumpWidget(MaterialApp(home:BackupProviderPage(api:api)));
    final inputs=find.byType(TextField);
    await tester.enterText(inputs.at(0),'private-api-secret');
    await tester.tap(find.text('Lưu API dự phòng')); await tester.pumpAndSettle();
    expect(calls.single.url.path,'/api/admin/providers/save');
    expect(jsonDecode(calls.single.body)['providers']['nvidia'],'private-api-secret');
    expect((tester.widget<TextField>(inputs.at(0))).controller!.text,isEmpty);
    await tester.ensureVisible(find.text('Kiểm tra AI'));
    await tester.tap(find.text('Kiểm tra AI')); await tester.pumpAndSettle();
    expect(calls.last.url.path,'/api/admin/providers/test');
    expect(jsonDecode(calls.last.body)['api_key'],'');
    expect(find.textContaining('AI dự phòng đã trả lời thành công'),findsOneWidget);
    api.close();
  });
  testWidgets('HTTP success without answer is not reported as verified AI', (tester) async {
    final api=ChatApi(endpoint:'https://backup.example',client:MockClient((request) async =>
      http.Response.bytes(utf8.encode('{"success":true,"message":"Chưa xác nhận AI hoạt động đầy đủ."}'),200,headers:{'content-type':'application/json; charset=utf-8'})))
      ..session=Session('admin','backup-token','',admin:true);
    await tester.pumpWidget(MaterialApp(home:BackupProviderPage(api:api)));
    await tester.ensureVisible(find.text('Kiểm tra AI'));
    await tester.tap(find.text('Kiểm tra AI')); await tester.pumpAndSettle();
    expect(find.text('Chưa xác nhận AI hoạt động đầy đủ.'),findsOneWidget);
    expect(find.textContaining('AI dự phòng đã trả lời thành công'),findsNothing);
    api.close();
  });
  testWidgets('admin denial is shown and configuration writes are not retried', (tester) async {
    var calls=0;
    final api=ChatApi(endpoint:'https://backup.example',client:MockClient((request) async {
      calls++;return http.Response('{"success":false,"message":"Admin required"}',403);
    }))..session=Session('user','backup-token','');
    await tester.pumpWidget(MaterialApp(home:BackupProviderPage(api:api)));
    await tester.tap(find.text('Lưu API dự phòng'));await tester.pumpAndSettle();
    expect(calls,1);expect(find.textContaining('Admin required'),findsOneWidget);
    api.close();
  });
}

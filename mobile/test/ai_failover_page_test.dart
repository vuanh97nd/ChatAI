import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:chatai_mobile/api.dart';
import 'package:chatai_mobile/main.dart';
import 'app_test.dart' show testApp;
import 'voice_test.dart' show FakeVoice;

void main() {
  testWidgets('saved AI backup is not restored and backup settings are absent', (tester) async {
    const primary = 'https://primary.example';
    FlutterSecureStorage.setMockInitialValues({
      'session:$primary': jsonEncode(Session('alice', 'primary-token', 'Alice').toJson()),
      'backup:$primary:alice': jsonEncode({'endpoint':'https://backup.example','session':Session('alice','backup-token','Alice').toJson()}),
    });
    final api = ChatApi(endpoint:primary,client:MockClient((request) async {
      expect(request.url.host,'primary.example');
      return http.Response('{"success":true,"items":[],"conversations":[],"notifications":[]}',200);
    }));
    await tester.pumpWidget(testApp(home:Home(api:api,voiceEngine:FakeVoice(),updateCheck:() async => throw Exception('Offline'))));
    await tester.pumpAndSettle();
    expect(api.backup,isNull); expect(api.usingBackup,isFalse);
    final scaffold = tester.state<ScaffoldState>(find.byType(Scaffold).last);
    scaffold.openDrawer(); await tester.pumpAndSettle();
    expect(find.text('AI dự phòng'),findsNothing);
    expect(find.text('Cấu hình API dự phòng'),findsNothing);
    await tester.pumpWidget(testApp(home:const SizedBox()));
  });
}

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
  testWidgets('history outage does not block AI; cached answer restores during outage', (tester) async {
    const primary = 'https://primary.example';
    const backup = 'https://backup.example';
    const scope = 'backup:$primary:alice';
    FlutterSecureStorage.setMockInitialValues({
      'session': jsonEncode(Session('alice', 'primary-token', 'Alice').toJson()),
      scope: jsonEncode({'endpoint': backup, 'session': Session('alice', 'backup-token', 'Alice').toJson()}),
    });
    var offline = false, creates = 0, aiCalls = 0;
    final client = MockClient((request) async {
      if (request.url.host == 'backup.example') {
        expect(request.url.path, '/api/provider/model');
        expect(jsonDecode(request.body)['key'], 'backup-token');
        aiCalls++;
        return http.Response('{"success":true,"answer":"Backup answer"}', 200);
      }
      if (request.url.path == '/api/conversations/create') { creates++; offline = true; }
      if (offline) return http.Response('{"success":false,"message":"D1 limit"}', 503);
      return http.Response('{"success":true,"items":[],"conversations":[]}', 200);
    });
    await tester.pumpWidget(testApp(home: Home(api: ChatApi(client: client, endpoint: primary), voiceEngine: FakeVoice(), updateCheck: () async => throw Exception('Offline'))));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Question');
    await tester.pump();
    await tester.tap(find.byTooltip('Gửi tin nhắn'));
    await tester.pumpAndSettle();
    expect(find.text('Backup answer'), findsOneWidget);
    expect(creates, 1); expect(aiCalls, 1);
    final cached = await const FlutterSecureStorage().read(key: 'offline:$scope');
    expect(cached, contains('Backup answer'));
    await tester.pumpWidget(testApp(home: const SizedBox()));
    final restoredClient = MockClient((request) async => http.Response('{"success":false,"message":"D1 limit"}', 503));
    await tester.pumpWidget(testApp(home: Home(api: ChatApi(client: restoredClient, endpoint: primary), voiceEngine: FakeVoice(), updateCheck: () async => throw Exception('Offline'))));
    await tester.pumpAndSettle();
    expect(find.text('Backup answer'), findsOneWidget);
    expect(aiCalls, 1);
    await tester.pumpWidget(testApp(home: const SizedBox()));
  });
}

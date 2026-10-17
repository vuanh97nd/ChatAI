import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:chatai_mobile/api.dart';

void main() {
  test('saved fallback is ignored and AI stays on primary during outage', () async {
    final requests = <http.Request>[];
    final client = MockClient((request) async {
      requests.add(request);
      return http.Response('{"success":false,"message":"D1 limit"}', 503);
    });
    final api = ChatApi(client: client, endpoint: 'https://primary.example')..session = Session('owner', 'primary-token', '');
    api.backup = ChatApi(client: client, endpoint: 'https://backup.example')..session = Session('backup-owner', 'backup-token', '');
    api.usingBackup = true;
    await expectLater(api.modelAnswer({'provider': 'gemini'}), throwsA(isA<ApiException>()));
    expect(requests.length, 1); expect(requests.single.url.host, 'primary.example');
    expect(api.usingBackup, isFalse);
    client.close();
  });
  test('auth and billing errors do not switch', () async {
    for (final status in [401, 403, 429]) {
      var calls = 0;
      final client = MockClient((request) async {
        calls++;
        return http.Response('{"success":false,"code":"QUOTA_EXHAUSTED","message":"Denied"}', status);
      });
      final api = ChatApi(client: client, endpoint: 'https://primary.example')..session = Session('owner', 'primary-token', '');
      api.backup = ChatApi(client: client, endpoint: 'https://backup.example')..session = Session('owner', 'backup-token', '');
      await expectLater(api.modelAnswer({'provider':'gemini'}), throwsA(isA<ApiException>()));
      expect(calls, 1); expect(api.usingBackup, isFalse);
      client.close();
    }
  });
  test('partial streamed answer is not replayed', () async {
    var calls = 0;
    final client = MockClient.streaming((request, body) async {
      calls++;
      return http.StreamedResponse(Stream.value(utf8.encode('data: {"choices":[{"delta":{"content":"part"}}]}\n\n')), 200,
        headers: {'content-type':'text/event-stream'});
    });
    final api = ChatApi(client: client, endpoint:'https://primary.example')..session = Session('owner','primary-token','');
    api.backup = ChatApi(client:client, endpoint:'https://backup.example')..session = Session('owner','backup-token','');
    await expectLater(api.modelAnswer({'provider':'nvidia'}, onText: (_) {}), throwsA(isA<ApiException>()));
    expect(calls, 1); expect(api.usingBackup, isFalse);
    client.close();
  });
}

import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:chatai_mobile/api.dart';

void main() {
  test('outage switches AI with separate credentials; history writes stay primary', () async {
    final requests = <http.Request>[];
    final client = MockClient((request) async {
      requests.add(request);
      if (request.url.host == 'primary.example') return http.Response('{"success":false,"message":"D1 limit"}', 503);
      expect(jsonDecode(request.body)['key'], 'backup-token');
      return http.Response('{"success":true,"answer":"OK"}', 200);
    });
    final api = ChatApi(client: client, endpoint: 'https://primary.example')..session = Session('owner', 'primary-token', '');
    api.backup = ChatApi(client: client, endpoint: 'https://backup.example')..session = Session('backup-owner', 'backup-token', '');
    expect((await api.modelAnswer({'provider': 'gemini'}))['answer'], 'OK');
    expect(api.usingBackup, isTrue);
    await api.modelAnswer({'provider': 'gemini'});
    expect(requests.last.url.host, 'backup.example');
    await expectLater(api.post('/api/conversations/append', {}), throwsA(isA<ApiException>()));
    expect(requests.last.url.host, 'primary.example');
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

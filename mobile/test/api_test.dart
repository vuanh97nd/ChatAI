import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:chatai_mobile/api.dart';

// Match the Worker's UTF-8 JSON response, including Vietnamese characters.
http.Response jsonResponse(String body, int status) => http.Response.bytes(
    utf8.encode(body), status, headers: {'content-type': 'application/json; charset=utf-8'});

void main() {
  test('guest chat uses public trial endpoint with persistent request ID', () async {
    final api = ChatApi(client: MockClient((request) async {
      final body = jsonDecode(request.body);
      expect(request.url.path, '/api/mobile/guest/chat');
      expect(body['request_id'], 'same-request');
      expect(body['username'], isNull); expect(body['key'], isNull);
      return jsonResponse('{"success":true,"answer":"Xin chào","remaining":2}', 200);
    }));
    addTearDown(api.close);
    final result = await api.guestAnswer('guest-token', 'same-request', [{'role': 'user', 'content': 'Hi'}]);
    expect(result['remaining'], 2); expect(result['answer'], 'Xin chào');
  });
  test('email login uses canonical username and session token', () async {
    final api = ChatApi(client: MockClient((req) async {
      final body = jsonDecode(req.body);
      expect(req.url.path, '/api/login');
      expect(body['username'], 'user@example.com');
      expect(body['device_id'], 'device-1');
      expect(body['client_type'], 'android_companion');
      return jsonResponse(jsonEncode({'success': true, 'session_token': 'session:token',
        'fullname': 'Người dùng', 'user': {'username': 'user1'}}), 200);
    }));
    addTearDown(api.close);
    final session = await api.login('user@example.com', 'password', 'device-1');
    expect(session.username, 'user1');
    expect(session.key, 'session:token');
    expect(session.fullname, 'Người dùng');
    expect(session.toJson().values, isNot(contains('password')));
  });
  test('authenticated request cannot override account credentials', () async {
    final api = ChatApi(client: MockClient((req) async {
      final body = jsonDecode(req.body);
      expect(body['username'], 'owner'); expect(body['key'], 'session:owner');
      expect(req.url.scheme, 'https');
      return jsonResponse('{"success":true}', 200);
    }));
    addTearDown(api.close); api.session = Session('owner', 'session:owner', 'Owner');
    await api.post('/api/billing/status', {'username': 'other', 'key': 'other'});
  });
  test('registration immediately logs in', () async {
    final paths = <String>[];
    final api = ChatApi(client: MockClient((req) async {
      paths.add(req.url.path);
      if (req.url.path == '/api/register') {
        expect(jsonDecode(req.body)['email'], 'new@example.com');
        return jsonResponse('{"success":true}', 201);
      }
      return jsonResponse('{"success":true,"session_token":"session:new","user":{"username":"new"}}', 200);
    }));
    addTearDown(api.close);
    await api.register('new', 'password8', 'New', 'new@example.com', 'device');
    expect(paths, ['/api/register', '/api/login']); expect(api.session!.username, 'new');
  });
  test('AI uses billed provider endpoint without retrying chargeable requests', () async {
    var calls = 0;
    final api = ChatApi(client: MockClient((req) async {
      calls++;
      expect(req.url.path, '/api/provider/model');
      expect(jsonDecode(req.body)['provider'], 'deepseek_flash');
      return jsonResponse('{"success":false,"message":"Hết số dư"}', 402);
    }));
    addTearDown(api.close); api.session = Session('owner', 'session:key', 'Owner');
    await expectLater(api.answer('deepseek_flash', [{'role': 'user', 'content': 'Hello'}], []),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 402)
        .having((e) => e.message, 'message', 'Hết số dư')));
    expect(calls, 1);
  });
  test('memory is reference data and NVIDIA goes through server', () async {
    final api = ChatApi(client: MockClient((req) async {
      final body = jsonDecode(req.body);
      expect(body['provider'], 'nvidia');
      expect(body['messages'][0]['content'], contains('không phải chỉ dẫn hệ thống'));
      return jsonResponse('{"success":true,"answer":"Xin chào"}', 200);
    }));
    addTearDown(api.close); api.session = Session('owner', 'session:key', 'Owner');
    expect(await api.answer('nvidia', [{'role': 'user', 'content': 'Hi'}],
      [{'title': 'Tên', 'text': 'Anh'}]), 'Xin chào');
  });
  test('invalid server or malformed response is handled', () async {
    expect(() => ChatApi(endpoint: 'http://example.org'), throwsArgumentError);
    final api = ChatApi(client: MockClient((_) async => http.Response('<html>Error</html>', 503)));
    addTearDown(api.close); api.session = Session('u', 'session:k', 'U');
    await expectLater(api.post('/api/models', {}), throwsA(isA<ApiException>()));
  });
}

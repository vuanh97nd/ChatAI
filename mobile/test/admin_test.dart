import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:chatai_mobile/api.dart';
import 'package:chatai_mobile/admin.dart';

void main() {
  test('credit timeout survives page recreation and uses one operation ID', () async {
    final storage = <String, String>{}, ids = <String>[];
    var count = 0;
    final api = ChatApi(client: MockClient((request) async {
      final body = jsonDecode(request.body) as Map<String, dynamic>;
      expect(body['username'], 'admin'); expect(body['target'], 'alice');
      ids.add(body['request_id'] as String);
      count++;
      if (count == 1) throw http.ClientException('response lost');
      return http.Response('{"success":true}', 200);
    }));
    addTearDown(api.close); api.session = Session('admin', 'secret', 'Admin', admin: true);
    AdminActions create() => AdminActions(api,
      read: (key) async => storage[key],
      write: (key, value) async { if (value == null) { storage.remove(key); } else { storage[key] = value; } });
    final payload = {'target': 'alice', 'amount': 20000, 'note': 'Test credit'};
    const path = '/api/admin/billing/credit';
    await expectLater(create().send(path, payload, 'request_id'), throwsA(isA<ApiException>()));
    final restored = create();
    expect((await restored.pending(path))!['payload'], payload);
    await expectLater(restored.send(path, {...payload, 'amount': 50000}, 'request_id'), throwsA(isA<ApiException>()));
    expect(count, 1);
    await restored.send(path, payload, 'request_id');
    expect(ids[0], ids[1]); expect(storage, isEmpty);
  });
  test('regular user or switched account cannot send admin operations', () async {
    var count = 0;
    final api = ChatApi(client: MockClient((_) async { count++; return http.Response('{"success":true}', 200); }));
    addTearDown(api.close); api.session = Session('admin', 'secret', 'Admin', admin: true);
    final actions = AdminActions(api, read: (_) async => null, write: (_, value) async {});
    api.session = Session('alice', 'session:alice', 'Alice');
    await expectLater(actions.send('/api/admin/notifications/send', {'title': 'Hi'}, 'id'), throwsA(isA<ApiException>()));
    expect(count, 0);
  });
}

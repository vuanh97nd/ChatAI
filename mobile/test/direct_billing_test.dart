import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:chatai_mobile/api.dart';

void main() {
  test('wallet and QR polls go direct with one cached identity request', () async {
    final requests = <http.Request>[];
    final api = ChatApi(client: MockClient((r) async {
      requests.add(r);
      final body = jsonDecode(r.body) as Map<String, dynamic>;
      if (r.url.path == '/api/account/billing-session') {
        expect(r.url.origin, defaultServer);
        expect(body['key'], 'private-main-session');
        return http.Response(jsonEncode({'success': true, 'billing_endpoint': defaultBackupServer,
          'billing_session': 'signed-ticket', 'expires_at': DateTime.now().millisecondsSinceEpoch + 300000}), 200);
      }
      expect(r.url.origin, defaultBackupServer);
      expect(body.containsKey('key'), false); expect(body.containsKey('username'), false);
      expect(body['billing_session'], 'signed-ticket');
      return http.Response('{"success":true}', 200);
    }));
    addTearDown(api.close); api.session = Session('alice', 'private-main-session', 'Alice');
    await api.post('/api/billing/status', {});
    await api.post('/api/billing/order/status', {'order_id': 'same-order'});
    expect(requests.where((r) => r.url.origin == defaultServer).length, 1);
    expect(requests.where((r) => r.url.origin == defaultBackupServer).length, 2);
  });

  test('ambiguous direct payment never retries on primary', () async {
    final requests = <http.Request>[];
    final api = ChatApi(client: MockClient((r) async {
      requests.add(r);
      if (r.url.path == '/api/account/billing-session') {
        return http.Response(jsonEncode({'success': true, 'billing_endpoint': defaultBackupServer,
          'billing_session': 'signed-ticket', 'expires_at': DateTime.now().millisecondsSinceEpoch + 300000}), 200);
      }
      throw http.ClientException('lost reply');
    }));
    addTearDown(api.close); api.session = Session('alice', 'private-main-session', 'Alice');
    await expectLater(api.post('/api/billing/order', {'request_id': 'same-request'}),
      throwsA(isA<ApiException>().having((e) => e.code, 'code', 'BILLING_AUTHORITY_UNAVAILABLE')));
    expect(requests.length, 2); expect(requests.last.url.origin, defaultBackupServer);
  });
}

import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:chatai_mobile/api.dart';
import 'package:chatai_mobile/plaxis_agent_api.dart';

void main() {
  test(
    'agent uses distinct Bearer and native job API without account credentials',
    () async {
      final paths = <String>[];
      final api = PlaxisAgentApi(
        'https://pc.example',
        'agent-token',
        client: MockClient((request) async {
          paths.add(request.url.path);
          expect(request.headers['Authorization'], 'Bearer agent-token');
          expect(request.followRedirects, isFalse);
          if (request.url.path == '/plaxis/jobs') {
            final data = jsonDecode(request.body) as Map<String, dynamic>;
            expect(data['project_id'], 'foundation');
            expect(data['version'], '3d');
            expect(data.containsKey('username'), isFalse);
            expect(data.containsKey('key'), isFalse);
            expect(data['criteria'][0]['unit'], 'm');
            return http.Response('{"id":"job1","status":"queued"}', 202);
          }
          return http.Response(
            '{"ok":true,"status":"running","events":[]}',
            200,
          );
        }),
      );
      addTearDown(api.close);
      await api.connect();
      final job = await api.submit(
        'calculate',
        '3d',
        'foundation',
        criteria: [
          {'metric': 'S_m', 'operator': 'le', 'target': .2, 'unit': 'm'},
        ],
      );
      await api.inspect(job['id'] as String);
      await api.stop('job1');
      expect(paths, [
        '/health',
        '/plaxis/jobs',
        '/plaxis/jobs/job1',
        '/plaxis/jobs/job1/stop',
      ]);
    },
  );
  test('reject insecure addresses and empty token', () {
    for (final url in [
      'http://pc.example',
      'https://user:pass@pc.example',
      'https://pc.example/path',
      'https://pc.example?token=secret',
    ]) {
      expect(() => PlaxisAgentApi(url, 'token'), throwsArgumentError);
    }
    expect(() => PlaxisAgentApi('https://pc.example', ''), throwsArgumentError);
  });
  test('does not follow redirects or retry failed job submissions', () async {
    var requests = 0;
    final api = PlaxisAgentApi(
      'https://pc.example',
      'secret',
      client: MockClient((request) async {
        requests++;
        return http.Response(
          'secret upstream failure',
          302,
          headers: {'location': 'https://other.example'},
        );
      }),
    );
    addTearDown(api.close);
    await expectLater(
      api.submit('write', '2d', 'p'),
      throwsA(
        isA<ApiException>().having(
          (e) => e.message,
          'message',
          isNot(contains('secret')),
        ),
      ),
    );
    expect(requests, 1);
  });
  test('server restart is reported without replaying work', () async {
    final api = PlaxisAgentApi(
      'https://pc.example',
      'token',
      client: MockClient(
        (request) async => http.Response('{"detail":"gone"}', 404),
      ),
    );
    addTearDown(api.close);
    await expectLater(
      api.inspect('old'),
      throwsA(isA<ApiException>().having((e) => e.status, 'status', 404)),
    );
  });
}

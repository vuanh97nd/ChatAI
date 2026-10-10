import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:chatai_mobile/updates.dart';

void main() {
  test('update manifest builds a fixed GitHub APK URL and compares build codes', () async {
    final client = MockClient((request) async {
      expect(request.url.toString(), updateManifest);
      return http.Response(jsonEncode({'version': '0.9.5', 'build': '25',
        'file': 'ChatAI-0.9.5-build25-abcdef0.apk'}), 200);
    });
    addTearDown(client.close);
    final result = await checkAppUpdate(client: client);
    expect(result.build, greaterThan(currentBuild));
    expect(result.url, 'https://github.com/vuanh97nd/ChatAI/releases/download/android-latest/ChatAI-0.9.5-build25-abcdef0.apk');
  });
  test('manifest cannot redirect installation outside the release path', () {
    for (final file in ['https://evil.example/app.apk', '../app.apk', 'app.exe']) {
      expect(() => AppUpdate.parse({'version': '1', 'build': 30, 'file': file}), throwsFormatException);
    }
  });
  test('missing release reports no published APK', () async {
    final client = MockClient((_) async => http.Response('', 404));
    addTearDown(client.close);
    await expectLater(checkAppUpdate(client: client), throwsA(isA<Exception>()));
  });
}

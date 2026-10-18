import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:chatai_mobile/api.dart';
import 'package:chatai_mobile/media_page.dart';

void main() {
  testWidgets('explicit image action starts once without a confirmation dialog', (tester) async {
    var calls = 0; var consumed = 0;
    final api = ChatApi(client: MockClient((request) async {
      if (request.url.path == '/api/media/capabilities') return http.Response(jsonEncode({'success':true,'image_available':true}),200);
      expect(request.url.path, '/api/media/image'); calls++;
      return http.Response(jsonEncode({'success':false,'message':'Service unavailable'}),503);
    }))..session = Session('alice','token','Alice');
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SingleChildScrollView(child: MediaPage(api:api,inline:true,initialPrompt:'Con mèo',autoStart:true,onAutoStartConsumed:()=>consumed++)))));
    await tester.pumpAndSettle();
    expect(calls,1); expect(consumed,1); expect(find.byType(AlertDialog),findsNothing);
    await tester.pump(); expect(calls,1);
    await tester.pumpWidget(const SizedBox());
  });
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(
      const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'), (_) async => null);
  });
  testWidgets('media capabilities require a real configured provider', (tester) async {
    final api = ChatApi(client: MockClient((request) async {
      expect(request.url.path, '/api/media/capabilities');
      expect(jsonDecode(request.body)['username'], 'alice');
      return http.Response(jsonEncode({'success': true, 'image_available': false, 'video_available': false}), 200);
    }))..session = Session('alice', 'token', 'Alice');
    await tester.pumpWidget(MaterialApp(home: MediaPage(api: api)));
    await tester.pumpAndSettle();
    expect(find.text('Dịch vụ chưa được cấu hình. Liên hệ quản trị viên.'), findsOneWidget);
    final create = tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Tạo ảnh'));
    expect(create.onPressed, isNull);
    await tester.tap(find.text('Video'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Cần OpenAI key'), findsOneWidget);
  });
}

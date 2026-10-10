import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:chatai_mobile/api.dart';
import 'package:chatai_mobile/main.dart';
import 'voice_test.dart' show FakeVoice;

void main() {
  testWidgets('fresh install opens chat, accepts three turns, then opens login on fourth send', (tester) async {
    FlutterSecureStorage.setMockInitialValues({});
    var turns = 0;
    final api = ChatApi(client: MockClient((request) async {
      final Map<String, dynamic> result;
      if (request.url.path == '/api/mobile/guest/status') {
        result = {'success': true, 'remaining': 3};
      } else {
        expect(request.url.path, '/api/mobile/guest/chat');
        turns++;
        result = {'success': true, 'answer': 'Answer $turns', 'remaining': 3 - turns};
      }
      return http.Response(jsonEncode(result), 200, headers: {'content-type': 'application/json; charset=utf-8'});
    }));
    await tester.pumpWidget(MaterialApp(home: Home(api: api, voiceEngine: FakeVoice())));
    await tester.pumpAndSettle();
    expect(find.byType(LoginPage), findsNothing);
    expect(find.byType(ChatWelcome), findsOneWidget);
    expect(find.textContaining('Dùng thử NVIDIA · còn'), findsNothing);
    for (var i = 1; i <= 3; i++) {
      await tester.enterText(find.byType(TextField), 'Question $i');
      await tester.tap(find.byIcon(Icons.send)); await tester.pumpAndSettle();
      expect(turns, i);
      expect(find.byType(LoginPage), findsNothing);
    }
    await tester.enterText(find.byType(TextField), 'Question 4');
    await tester.tap(find.byIcon(Icons.send)); await tester.pumpAndSettle();
    expect(turns, 3);
    expect(find.byType(LoginPage), findsOneWidget);
    await tester.pumpWidget(const MaterialApp(home: SizedBox()));
  });
  testWidgets('empty chat welcomes users with the shared logo without a login form', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: ChatWelcome())));
    expect(find.text('Xin chào bạn!'), findsOneWidget);
    expect(find.text('Tôi có thể giúp gì cho bạn?'), findsOneWidget);
    expect(find.byType(TextField), findsNothing);
    expect((tester.widget<Image>(find.byType(Image)).image as AssetImage).assetName, 'assets/chat_ai.png');
  });
  testWidgets('welcome scrolls in the small space left by the keyboard without overflow', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(
      body: SizedBox(height: 70, child: ChatWelcome()))));
    expect(tester.takeException(), isNull);
    expect(find.byType(SingleChildScrollView), findsOneWidget);
  });
  testWidgets('startup shows the shared ChatAI logo, name and loading state', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: StartupScreen()));
    expect(find.text('Chat AI'), findsOneWidget);
    expect(find.text('Đang khởi động…'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    final logo = tester.widget<Image>(find.byType(Image));
    expect((logo.image as AssetImage).assetName, 'assets/chat_ai.png');
    expect(logo.semanticLabel, 'Logo ChatAI');
    await tester.pumpWidget(const MaterialApp(home: SizedBox()));
  });
  testWidgets('first screen offers NVIDIA, login and required email registration', (tester) async {
    final api = ChatApi(); addTearDown(api.close);
    await tester.pumpWidget(MaterialApp(home: LoginPage(api: api, device: 'test', onLogin: (_) async {})));
    expect(find.text('AI trực tuyến · NVIDIA mặc định'), findsOneWidget);
    expect((tester.widget<Image>(find.byType(Image)).image as AssetImage).assetName, 'assets/chat_ai.png');
    expect(find.text('Đăng nhập'), findsOneWidget);
    await tester.tap(find.text('Tạo tài khoản')); await tester.pumpAndSettle();
    expect(find.text('Email bắt buộc'), findsOneWidget);
    expect((tester.widget<Image>(find.byType(Image)).image as AssetImage).assetName, 'assets/chat_ai.png');
    expect(find.text('Đăng ký và đăng nhập'), findsOneWidget);
    expect(find.text('Họ và tên'), findsOneWidget);
  });
}

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:chatai_mobile/api.dart';
import 'package:chatai_mobile/main.dart';
import 'voice_test.dart' show FakeVoice;

// Repeating logo motion is disabled in interaction tests so settling is finite.
Widget testApp({required Widget home}) => MaterialApp(home: home,
  builder: (context, child) => MediaQuery(
    data: MediaQuery.of(context).copyWith(disableAnimations: true), child: child!));

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
    await tester.pumpWidget(testApp(home: Home(api: api, voiceEngine: FakeVoice())));
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
    await tester.pumpWidget(testApp(home: SizedBox()));
  });
  testWidgets('signed-in drawer opens memory and notifications and can return to chat', (tester) async {
    FlutterSecureStorage.setMockInitialValues({'session': jsonEncode(Session('alice', 'session:test', 'Alice').toJson())});
    final api = ChatApi(client: MockClient((request) async {
      final result = <String, dynamic>{'success': true};
      switch (request.url.path) {
        case '/api/memory/personal/list': result['items'] = [{'title': 'Test memory', 'text': 'Remember me'}];
        case '/api/notifications/list': result['notifications'] = [{'title': 'Test notice', 'text': 'Hello'}];
        case '/api/conversations/list': result['conversations'] = [{'id': 'saved', 'title': 'Recent chat'}];
      }
      return http.Response(jsonEncode(result), 200, headers: {'content-type': 'application/json; charset=utf-8'});
    }));
    await tester.pumpWidget(testApp(home: Home(api: api, voiceEngine: FakeVoice())));
    await tester.pumpAndSettle();
    expect(find.byType(NavigationBar), findsNothing);
    expect(find.byType(LoginPage), findsNothing);
    await tester.tap(find.byTooltip('Open navigation menu')); await tester.pumpAndSettle();
    final drawerScroll = find.descendant(of: find.byKey(const ValueKey('drawer-history')),
      matching: find.byWidgetPredicate((w) => w is Scrollable && w.axisDirection == AxisDirection.down));
    expect(drawerScroll, findsOneWidget);
    await tester.scrollUntilVisible(find.text('Recent chat'), 160, scrollable: drawerScroll);
    expect(find.text('Recent chat'), findsOneWidget);
    expect(find.text('Quản trị'), findsNothing);
    await tester.scrollUntilVisible(find.text('Bộ nhớ'), -160, scrollable: drawerScroll);
    await tester.tap(find.text('Bộ nhớ')); await tester.pumpAndSettle();
    expect(find.text('Test memory'), findsOneWidget);
    await tester.tap(find.byType(BackButton)); await tester.pumpAndSettle();
    expect(find.byType(ChatWelcome), findsOneWidget);
    await tester.tap(find.byTooltip('Open navigation menu')); await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Thông báo'), -160, scrollable: drawerScroll);
    await tester.tap(find.text('Thông báo')); await tester.pumpAndSettle();
    expect(find.text('Test notice'), findsOneWidget);
    await tester.tap(find.byType(BackButton)); await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Open navigation menu')); await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Chat'), -160, scrollable: drawerScroll);
    await tester.tap(find.text('Chat')); await tester.pumpAndSettle();
    expect(find.byType(ChatWelcome), findsOneWidget);
    await tester.pumpWidget(testApp(home: const SizedBox()));
  });
  testWidgets('login back arrow returns to chat and keeps its draft', (tester) async {
    FlutterSecureStorage.setMockInitialValues({});
    final api = ChatApi(client: MockClient((request) async => http.Response(
      '{"success":true,"remaining":3}', 200, headers: {'content-type': 'application/json'})));
    await tester.pumpWidget(testApp(home: Home(api: api, voiceEngine: FakeVoice())));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Keep this draft');
    await tester.tap(find.text('Đăng nhập')); await tester.pumpAndSettle();
    expect(find.byType(LoginPage), findsOneWidget);
    await tester.tap(find.byTooltip('Quay lại')); await tester.pumpAndSettle();
    expect(find.byType(LoginPage), findsNothing);
    expect(find.text('Keep this draft'), findsOneWidget);
    expect(find.byTooltip('Đính kèm file'), findsOneWidget);
    await tester.pumpWidget(testApp(home: const SizedBox()));
  });
  testWidgets('empty chat welcomes users with the shared logo without a login form', (tester) async {
    await tester.pumpWidget(testApp(home: Scaffold(body: ChatWelcome())));
    expect(find.text('Xin chào bạn!'), findsOneWidget);
    expect(find.text('Tôi có thể giúp gì cho bạn?'), findsOneWidget);
    expect(find.byType(TextField), findsNothing);
    expect((tester.widget<Image>(find.byType(Image)).image as AssetImage).assetName, 'assets/chat_ai.png');
  });
  testWidgets('welcome hides when keyboard leaves too little space, without overflow', (tester) async {
    await tester.pumpWidget(testApp(home: Scaffold(
      body: SizedBox(height: 70, child: ChatWelcome()))));
    expect(tester.takeException(), isNull);
    expect(find.byType(Image), findsNothing);
  });
  testWidgets('Flutter startup does not repeat the native launch logo', (tester) async {
    await tester.pumpWidget(testApp(home: const StartupScreen()));
    expect(find.byType(Image), findsNothing);
    expect(find.text('Đang khởi động…'), findsNothing);
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    await tester.pumpWidget(testApp(home: const SizedBox()));
  });
  testWidgets('first screen offers NVIDIA, login and required email registration', (tester) async {
    final api = ChatApi(); addTearDown(api.close);
    await tester.pumpWidget(testApp(home: LoginPage(api: api, device: 'test', onLogin: (_) async {})));
    expect(find.text('AI trực tuyến · NVIDIA mặc định'), findsNothing);
    expect((tester.widget<Image>(find.byType(Image)).image as AssetImage).assetName, 'assets/chat_ai.png');
    expect(find.text('Đăng nhập'), findsNWidgets(2));
    await tester.tap(find.text('Tạo tài khoản')); await tester.pumpAndSettle();
    expect(find.text('Email bắt buộc'), findsOneWidget);
    expect((tester.widget<Image>(find.byType(Image)).image as AssetImage).assetName, 'assets/chat_ai.png');
    expect(find.text('Đăng ký và đăng nhập'), findsOneWidget);
    expect(find.text('Họ và tên'), findsOneWidget);
  });
}

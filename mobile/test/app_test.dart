import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:chatai_mobile/api.dart';
import 'package:chatai_mobile/main.dart';

void main() {
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

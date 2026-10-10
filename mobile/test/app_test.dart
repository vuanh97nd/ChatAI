import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:chatai_mobile/api.dart';
import 'package:chatai_mobile/main.dart';

void main() {
  testWidgets('first screen offers NVIDIA, login and required email registration', (tester) async {
    final api = ChatApi(); addTearDown(api.close);
    await tester.pumpWidget(MaterialApp(home: LoginPage(api: api, device: 'test', onLogin: (_) async {})));
    expect(find.text('AI trực tuyến · NVIDIA mặc định'), findsOneWidget);
    expect(find.text('Đăng nhập'), findsOneWidget);
    await tester.tap(find.text('Tạo tài khoản')); await tester.pumpAndSettle();
    expect(find.text('Email bắt buộc'), findsOneWidget);
    expect(find.text('Đăng ký và đăng nhập'), findsOneWidget);
    expect(find.text('Họ và tên'), findsOneWidget);
  });
}

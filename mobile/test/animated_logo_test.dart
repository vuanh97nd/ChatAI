import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:chatai_mobile/animated_logo.dart';

void main() {
  testWidgets('logo floats, pauses in background and stops after disposal', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: AnimatedChatLogo())));
    await tester.pump();
    final logo = find.descendant(of: find.byType(AnimatedChatLogo), matching: find.byType(Transform));
    final initial = tester.widget<Transform>(logo).transform.getTranslation().y;
    await tester.pump(const Duration(milliseconds: 500));
    final moved = tester.widget<Transform>(logo).transform.getTranslation().y;
    expect(moved, isNot(initial));
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pump(const Duration(milliseconds: 500));
    expect(tester.widget<Transform>(logo).transform.getTranslation().y, moved);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpWidget(const MaterialApp(home: SizedBox()));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}

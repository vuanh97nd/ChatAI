import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../lib/ios_settings.dart';
import '../lib/visual_style.dart';

void main() {
  testWidgets('deadline wheel requires confirmation and cancel returns no date', (tester) async {
    tester.view.physicalSize = const Size(320, 740); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    final initial = DateTime.now().add(const Duration(days: 1));
    DateTime? result;
    await tester.pumpWidget(MaterialApp(theme: futuristicTheme(Brightness.light), home: Scaffold(body: Builder(builder: (context) =>
      TextButton(onPressed: () async { result = await showIosDateTime(context, initial: initial); }, child: const Text('Mở lịch'))))));
    await tester.tap(find.text('Mở lịch')); await tester.pumpAndSettle();
    expect(find.byType(CupertinoDatePicker), findsOneWidget);
    expect(result, isNull);
    await tester.tap(find.text('Hủy')); await tester.pumpAndSettle();
    expect(result, isNull);
    await tester.tap(find.text('Mở lịch')); await tester.pumpAndSettle();
    await tester.tap(find.text('Xong')); await tester.pumpAndSettle();
    expect(result?.day, initial.day); expect(result?.hour, initial.hour);
    expect(tester.takeException(), isNull);
  });
  testWidgets('picker opens an iOS sheet and returns the selected value', (tester) async {
    String? selected;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: IosPicker<String>(
      title: 'Trạng thái', value: 'all', options: const {'all': 'Tất cả', 'locked': 'Đã khóa'}, onChanged: (value) => selected = value))));
    await tester.tap(find.text('Tất cả')); await tester.pumpAndSettle();
    expect(find.byType(CupertinoActionSheet), findsOneWidget);
    await tester.tap(find.text('Đã khóa')); await tester.pumpAndSettle();
    expect(selected, 'locked'); expect(find.byType(CupertinoActionSheet), findsNothing);
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: IosPicker<String>(
      title: 'Trạng thái', value: 'all', options: {'all': 'Tất cả'}, onChanged: null))));
    await tester.tap(find.text('Tất cả')); await tester.pumpAndSettle();
    expect(find.byType(CupertinoActionSheet), findsNothing);
  });
  testWidgets('inset settings fit narrow screens with larger text in both themes', (tester) async {
    tester.view.physicalSize = const Size(320, 740); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    FlutterSecureStorage.setMockInitialValues({});
    for (final brightness in Brightness.values) {
      await tester.pumpWidget(MaterialApp(theme: futuristicTheme(brightness), builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(1.4)), child: child!), home: const EffectsPage()));
      await tester.pumpAndSettle();
      expect(find.text('QUYỀN RIÊNG TƯ VÀ ÂM THANH'), findsOneWidget);
      await tester.scrollUntilVisible(find.text('Tắt hiệu ứng'), 250, scrollable: find.byType(Scrollable).first);
      await Scrollable.ensureVisible(tester.element(find.text('Tắt hiệu ứng')), alignment: .5);
      await tester.pumpAndSettle();
      expect(find.text('Tắt hiệu ứng').hitTestable(), findsOneWidget);
      await tester.tap(find.text('Tắt hiệu ứng')); await tester.pumpAndSettle();
      expect(visualEffects.value, VisualEffects.off);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
    }
    visualEffects.value = VisualEffects.full;
  });
  testWidgets('segmented admin navigation stays synchronized with swipes', (tester) async {
    await tester.pumpWidget(MaterialApp(theme: futuristicTheme(Brightness.light), home: DefaultTabController(length: 3, child: Scaffold(
      appBar: AppBar(bottom: const IosTabHeader(labels: ['Người dùng', 'Thông báo', 'Thanh toán'])),
      body: const TabBarView(children: [Center(child: Text('Users page')), Center(child: Text('Notices page')), Center(child: Text('Billing page'))]),
    ))));
    await tester.tap(find.text('Thanh toán')); await tester.pumpAndSettle();
    expect(find.text('Billing page'), findsOneWidget);
    await tester.drag(find.byType(TabBarView), const Offset(600, 0)); await tester.pumpAndSettle();
    expect(tester.widget<CupertinoSlidingSegmentedControl<int>>(find.byType(CupertinoSlidingSegmentedControl<int>)).groupValue, 1);
    expect(tester.takeException(), isNull);
  });
}

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/testing.dart';
import 'package:chatai_mobile/api.dart';
import 'package:chatai_mobile/task_page.dart';
void main() {
  testWidgets('manual work and completed progress persist without any AI call', (tester) async {
    FlutterSecureStorage.setMockInitialValues({});
    final api=ChatApi(client:MockClient((_) async => throw StateError('Offline task editing must not call AI')))
      ..session=Session('alice','token','Alice');
    Widget page()=>MaterialApp(home:TaskPage(api:api,provider:'openrouter'));
    await tester.pumpWidget(page()); await tester.pumpAndSettle();
    await tester.tap(find.text('Thêm thủ công')); await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).last,'Chuẩn bị báo cáo');
    await tester.tap(find.text('Lưu')); await tester.pumpAndSettle();
    await tester.ensureVisible(find.byType(CheckboxListTile));
    await tester.tap(find.byType(CheckboxListTile)); await tester.pumpAndSettle();
    expect(tester.widget<CheckboxListTile>(find.byType(CheckboxListTile)).value,true);
    await tester.pumpWidget(const SizedBox()); await tester.pumpAndSettle();
    await tester.pumpWidget(page()); await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.byType(CheckboxListTile),200, scrollable:find.byType(Scrollable).first);
    expect(tester.widget<CheckboxListTile>(find.byType(CheckboxListTile)).value,true);
    expect(find.text('1/1 việc đã hoàn thành'),findsOneWidget);
    await tester.pumpWidget(const SizedBox()); await tester.pumpAndSettle();
  });
}

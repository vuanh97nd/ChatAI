import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import '../lib/connected_apps.dart';

void main(){
 testWidgets('Drive hands the search URL to the explicit Android app only after a tap',(tester) async {
  const channel=MethodChannel('vn.chatai/linked_apps');
  final calls=<MethodCall>[];
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(channel,(call) async { calls.add(call); return true; });
  addTearDown(()=>TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(channel,null));
  await tester.pumpWidget(const MaterialApp(home:ConnectedAppsPage(initialApp:LinkedApp.drive,initialRequest:'Tìm file báo cáo trên Google Drive')));
  await tester.pumpAndSettle(); expect(calls,isEmpty);
  await Scrollable.ensureVisible(tester.element(find.text('Mở Drive / tìm tệp')),alignment:.5); await tester.pumpAndSettle();
  await tester.tap(find.text('Mở Drive / tìm tệp')); await tester.pumpAndSettle();
  expect(calls.length,1); expect(calls.single.method,'open');
  final args=calls.single.arguments as Map;
  expect(args['package'],'com.google.android.apps.docs');
  final uri=Uri.parse(args['uri'] as String);
  expect(uri.host,'drive.google.com'); expect(uri.queryParameters['q'],'báo cáo');
  expect(tester.takeException(),isNull);
 });
 test('explicit app requests route correctly without mistaking ordinary words for apps',(){
  expect(requestedApp('Mở Grab'),LinkedApp.grab);
  expect(requestedApp('Đặt xe be đến sân bay'),LinkedApp.be);
  expect(requestedApp('Gọi xe Xanh SM'),LinkedApp.green);
  expect(requestedApp('Tìm file trên Google Drive'),LinkedApp.drive);
  expect(requestedApp('Soạn email'),LinkedApp.gmail);
  expect(requestedApp('Tìm trường học cho bé'),isNull);
  expect(requestedApp('Grab là gì?'),isNull);
 });
 test('search directions and drafts encode user data without query injection',(){
  expect(mapSearch('cà phê & trà').queryParameters['query'],'cà phê & trà');
  expect(mapDirections('Sân bay Nội Bài').queryParameters['destination'],'Sân bay Nội Bài');
  expect(driveSearch('báo cáo & q=secret').queryParameters['q'],'báo cáo & q=secret');
  final draft=emailDraft('a@example.org','Họp & kiểm tra','Nội dung\n&bcc=other@example.org');
  expect(draft.scheme,'mailto');expect(draft.path,'a@example.org');
  expect(draft.queryParameters['subject'],'Họp & kiểm tra');expect(draft.queryParameters.containsKey('bcc'),isFalse);
 });
 testWidgets('opening the integration page never launches an app or sends email automatically',(tester) async {
  await tester.pumpWidget(const MaterialApp(home:ConnectedAppsPage(initialApp:LinkedApp.gmail)));
  expect(find.textContaining('Chat AI không tự đặt xe hoặc gửi thư'),findsOneWidget);
  final scroll=find.descendant(of:find.byType(ListView),matching:find.byWidgetPredicate((w)=>w is Scrollable && w.axisDirection==AxisDirection.down)).first;
  await tester.scrollUntilVisible(find.text('Mở ứng dụng email để xem và gửi'),150,scrollable:scroll);
  expect(find.text('Mở ứng dụng email để xem và gửi'),findsOneWidget);
 });
 testWidgets('Drive search is prefilled from the explicit user request',(tester) async {
  await tester.pumpWidget(const MaterialApp(home:ConnectedAppsPage(initialApp:LinkedApp.drive,initialRequest:'Tìm file báo cáo trên Google Drive')));
  final field=tester.widget<TextField>(find.byType(TextField));
  expect(field.controller!.text,'báo cáo');
 });
}

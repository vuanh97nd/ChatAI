import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import '../lib/assistant_reply.dart';

const weatherTable='''Dự báo hôm nay:

| Ngày | Nhiệt độ min (°C) | Nhiệt độ max (°C) | Xác suất mưa max (%) | Mã thời tiết | Mô tả thời tiết (WMO) |
| --- | --- | --- | --- | --- | --- |
| 2026-10-18 | 24,7 | 31,9 | 27 | 51 | Mưa phùn nhẹ |

Đoạn văn sau bảng vẫn đọc theo chiều ngang màn hình.
''';

void main(){
 for(final scale in [1.0,1.6]){
  testWidgets('wide weather table scrolls on a narrow phone at text scale $scale',(tester) async {
   await tester.pumpWidget(MaterialApp(home:Scaffold(body:MediaQuery(
    data:MediaQueryData(size:const Size(320,900),textScaler:TextScaler.linear(scale)),
    child:Align(alignment:Alignment.topLeft,child:SizedBox(width:300,child:SingleChildScrollView(
     child:AssistantReply(text:weatherTable,provider:'nvidia',reading:false,onRead:(){}))))))));
   await tester.pump();
   final table=find.byType(Table);
   expect(table,findsOneWidget);
   expect(tester.getSize(table).width,greaterThan(900));
   final horizontal=find.byWidgetPredicate((w)=>w is Scrollable && w.axisDirection==AxisDirection.right);
   expect(horizontal,findsOneWidget);
   final state=tester.state<ScrollableState>(horizontal);
   expect(state.position.maxScrollExtent,greaterThan(600));
   expect(state.position.pixels,0);
   await tester.drag(find.byType(Table),const Offset(-800,0));await tester.pumpAndSettle();
   expect(state.position.pixels,greaterThan(0));
   expect(find.text('Mưa phùn nhẹ'),findsOneWidget);
   expect(find.textContaining('Đoạn văn sau bảng'),findsOneWidget);
   expect(tester.takeException(),isNull);
  });
 }
 testWidgets('plain replies do not gain a horizontal scroller',(tester) async {
  await tester.pumpWidget(MaterialApp(home:Scaffold(body:SizedBox(width:300,
   child:AssistantReply(text:'Xin chào. Đây là câu trả lời thông thường.',reading:false,onRead:(){})))));
  expect(find.byType(Table),findsNothing);
  expect(find.byWidgetPredicate((w)=>w is Scrollable && w.axisDirection==AxisDirection.right),findsNothing);
  expect(tester.takeException(),isNull);
 });
}

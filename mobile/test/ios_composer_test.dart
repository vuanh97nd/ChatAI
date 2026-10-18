import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import '../lib/ios_composer.dart';
import '../lib/visual_style.dart';

void main(){
 testWidgets('image and video icons replace the old wand and call their own actions',(tester) async {
  final input=TextEditingController(text:'Con mèo');addTearDown(input.dispose);
  var images=0,videos=0;
  await tester.pumpWidget(MaterialApp(home:Scaffold(body:IosChatComposer(controller:input,provider:'nvidia',busy:false,hasAttachments:false,listening:false,onChanged:(){},onProvider:(_){},onImage:()=>images++,onVideo:()=>videos++))));
  expect(find.byIcon(CupertinoIcons.wand_stars),findsNothing);
  await tester.tap(find.byTooltip('Tạo ảnh'));await tester.tap(find.byTooltip('Tạo video'));
  expect(images,1);expect(videos,1);expect(tester.takeException(),isNull);
 });
 testWidgets('iOS composer fits narrow phone and chooses provider from a sheet',(tester) async {
  tester.view.physicalSize=const Size(320,740);tester.view.devicePixelRatio=1;
  addTearDown(tester.view.resetPhysicalSize);addTearDown(tester.view.resetDevicePixelRatio);
  final input=TextEditingController();addTearDown(input.dispose);
  String? selected;
  await tester.pumpWidget(MaterialApp(theme:futuristicTheme(Brightness.light),home:Scaffold(body:Align(alignment:Alignment.bottomCenter,
   child:IosChatComposer(controller:input,provider:'nvidia',busy:false,hasAttachments:false,listening:false,onChanged:(){},onProvider:(value)=>selected=value,onAttach:(){},onMedia:(){},onMicrophone:(){},onAction:(){})))));
  expect(tester.takeException(),isNull);
  await tester.tap(find.text('NVIDIA'));await tester.pumpAndSettle();
  expect(find.byType(CupertinoActionSheet),findsOneWidget);
  await tester.tap(find.text('Gemini'));await tester.pumpAndSettle();
  expect(selected,'gemini');expect(tester.takeException(),isNull);
 });
 testWidgets('guest cannot change provider and send callback remains available',(tester) async {
  final input=TextEditingController(text:'Xin chào');addTearDown(input.dispose);var sent=0;
  await tester.pumpWidget(MaterialApp(home:Scaffold(body:IosChatComposer(controller:input,provider:'nvidia',busy:false,canChooseProvider:false,hasAttachments:false,listening:false,onChanged:(){},onProvider:(_)=>fail('guest must not change provider'),onAction:()=>sent++))));
  await tester.tap(find.byTooltip('Gửi tin nhắn'));expect(sent,1);
  expect(find.byType(CupertinoActionSheet),findsNothing);
 });
}

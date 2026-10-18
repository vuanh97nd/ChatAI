import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:chatai_mobile/api.dart';
import 'package:chatai_mobile/main.dart';
import 'package:chatai_mobile/visual_style.dart';
import 'voice_test.dart' show FakeVoice;

void main() {
  testWidgets('dark home fits a small screen and prompt chips populate the composer', (tester) async {
    if (Platform.environment['CHAT_AI_UI_PREVIEW'] == 'true') {
      await tester.runAsync(() async {
        final font = File('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf');
        if (font.existsSync()) {
          await (FontLoader('Roboto')..addFont(Future.value(ByteData.sublistView(font.readAsBytesSync())))).load();
        }
        await (FontLoader('packages/cupertino_icons/CupertinoIcons')..addFont(rootBundle.load('packages/cupertino_icons/assets/CupertinoIcons.ttf'))).load();
        await (FontLoader('MaterialIcons')..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
      });
    }
    tester.view.physicalSize = const Size(390,844); tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    FlutterSecureStorage.setMockInitialValues({'session:${Uri.parse(defaultServer).origin}': jsonEncode(Session('alice','token','Alice').toJson())});
    final api = ChatApi(client: MockClient((_) async => http.Response(jsonEncode({'success':true,'items':[],'notifications':[],'conversations':[]}),200)));
    final capture = GlobalKey();
    await tester.pumpWidget(MaterialApp(theme: futuristicTheme(Brightness.dark), builder: (context, child) =>
      MediaQuery(data: MediaQuery.of(context).copyWith(disableAnimations:true), child: RepaintBoundary(key:capture,
        child: AmbientScene(effects:VisualEffects.full,child:child!))),
      home:Home(api:api,voiceEngine:FakeVoice(),updateCheck:() async => throw Exception('Offline'))));
    await tester.pumpAndSettle();
    if (Platform.environment['CHAT_AI_UI_PREVIEW'] == 'true') {
      await tester.runAsync(() => precacheImage(const AssetImage('assets/chat_ai.png'), tester.element(find.byType(Home))));
      await tester.pumpAndSettle();
    }
    expect(find.byType(NavigationBar), findsOneWidget);
    expect(tester.takeException(),isNull);
    await tester.tap(find.text('Viết nội dung')); await tester.pumpAndSettle();
    expect(tester.widget<TextField>(find.byType(TextField)).controller!.text,'Giúp tôi viết nội dung ');
    if (Platform.environment['CHAT_AI_UI_PREVIEW'] == 'true') {
      await tester.runAsync(() async {
        final image = await (capture.currentContext!.findRenderObject()! as RenderRepaintBoundary).toImage(pixelRatio:2);
        final bytes = await image.toByteData(format:ui.ImageByteFormat.png);
        final output = File('build/ui-preview/android-dark-home.png'); await output.parent.create(recursive:true); await output.writeAsBytes(bytes!.buffer.asUint8List()); image.dispose();
      });
    }
    await tester.pumpWidget(const SizedBox()); await tester.pumpAndSettle();
  });
  testWidgets('turning off effects produces a settled scene without recurring frames', (tester) async {
    await tester.pumpWidget(MaterialApp(home:AmbientScene(effects:VisualEffects.off,child:const Scaffold(body:Text('Ready')))));
    await tester.pumpAndSettle(); expect(tester.binding.hasScheduledFrame,isFalse);
    await tester.pumpWidget(const SizedBox()); await tester.pumpAndSettle();
  });
}

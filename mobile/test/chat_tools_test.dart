import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:chatai_mobile/main.dart';
import 'package:chatai_mobile/api.dart';
import 'package:chatai_mobile/media_page.dart';
import 'package:chatai_mobile/connected_apps.dart';
import 'package:chatai_mobile/visual_style.dart';
import 'voice_test.dart' show FakeVoice;

void main() {
  testWidgets('media and app requests stay in chat without generating or launching automatically', (tester) async {
    FlutterSecureStorage.setMockInitialValues({'session:${Uri.parse(defaultServer).origin}': jsonEncode(Session('alice', 'token', 'Alice').toJson())});
    final paths = <String>[];
    final api = ChatApi(client: MockClient((request) async {
      paths.add(request.url.path);
      return http.Response(jsonEncode({'success': true, 'items': [], 'notifications': [], 'conversations': [],
        'conversation': {'id': 'tools-test'}, 'image_available': true, 'video_available': false}), 200);
    }));
    await tester.pumpWidget(MaterialApp(theme: futuristicTheme(Brightness.light), home: Home(api: api, voiceEngine: FakeVoice(), updateCheck: () async => throw Exception('Offline'))));
    await tester.pumpAndSettle();
    expect(tester.widget<NavigationBar>(find.byType(NavigationBar)).destinations.length, 3);
    await tester.enterText(find.byType(TextField).last, 'Tạo ảnh con mèo');
    await tester.pump(); await tester.tap(find.byTooltip('Gửi tin nhắn')); await tester.pumpAndSettle();
    expect(tester.widget<MediaPage>(find.byType(MediaPage)).inline, isTrue);
    expect(find.byType(Scaffold), findsOneWidget);
    expect(paths.where((p) => p == '/api/media/image'), isEmpty);
    expect(paths.where((p) => p == '/api/provider/model'), isEmpty);
    // Locate the main composer by its send/voice controls rather than the media prompt.
    final fields = tester.widgetList<TextField>(find.byType(TextField)).toList();
    final chatField = fields.last;
    chatField.controller!.text = 'Mở Grab';
    await tester.enterText(find.byType(TextField).last, 'Mở Grab'); await tester.pump();
    await tester.tap(find.byTooltip('Gửi tin nhắn')); await tester.pumpAndSettle();
    expect(tester.widget<ConnectedAppsPage>(find.byType(ConnectedAppsPage)).inline, isTrue);
    expect(find.byType(Scaffold), findsOneWidget);
    expect(paths.where((p) => p == '/api/media/capabilities').length, 1);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox()); await tester.pumpAndSettle();
  });
}

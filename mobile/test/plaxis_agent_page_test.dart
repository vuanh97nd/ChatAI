import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:chatai_mobile/plaxis_agent_api.dart';
import 'package:chatai_mobile/plaxis_agent_page.dart';

void main() {
  testWidgets(
    'connect, submit, read numeric evidence and stop without claiming completion',
    (tester) async {
      FlutterSecureStorage.setMockInitialValues({});
      final paths = <String>[];
      await tester.pumpWidget(
        MaterialApp(
          home: PlaxisAgentPage(
            storageKey: 'owner',
            clientFactory: (address, token) => PlaxisAgentApi(
              address,
              token,
              client: MockClient((request) async {
                paths.add(request.url.path);
                if (request.url.path == '/health')
                  return http.Response('{"ok":true}', 200);
                if (request.url.path == '/plaxis/jobs')
                  return http.Response('{"id":"j1","status":"queued"}', 202);
                if (request.url.path.endsWith('/stop'))
                  return http.Response('{"status":"stopping"}', 200);
                return http.Response(
                  jsonEncode({
                    'id': 'j1',
                    'status': 'running',
                    'events': [],
                    'result': null,
                  }),
                  200,
                );
              }),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextField, 'Địa chỉ HTTPS của agent PC'),
        'https://pc.example',
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'Mã kết nối agent'),
        'token',
      );
      await tester.tap(find.text('Kết nối agent'));
      await tester.pumpAndSettle();
      expect(
        find.text('Đã kết nối dịch vụ. Chưa xác minh kết nối PLAXIS.'),
        findsOneWidget,
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'Giao việc cho agent'),
        'inspect',
      );
      tester.testTextInput.hide();
      await tester.scrollUntilVisible(
        find.text('Gửi việc'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.text('Gửi việc'));
      await tester.pumpAndSettle();
      expect(paths.where((p) => p == '/plaxis/jobs').length, 1);
      await tester.scrollUntilVisible(
        find.text('Dừng công việc'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.text('Dừng công việc'));
      await tester.pumpAndSettle();
      expect(paths, contains('/plaxis/jobs/j1/stop'));
      expect(find.text('Mô hình đã được kiểm chứng.'), findsNothing);
      await tester.pumpWidget(const SizedBox());
    },
  );
  testWidgets(
    'uncertain submission is persisted and never replayed on reopen',
    (tester) async {
      FlutterSecureStorage.setMockInitialValues({});
      var submissions = 0;
      Widget page() => MaterialApp(
        home: PlaxisAgentPage(
          storageKey: 'timeout-owner',
          clientFactory: (address, token) => PlaxisAgentApi(
            address,
            token,
            client: MockClient((request) async {
              if (request.url.path == '/health')
                return http.Response('{"ok":true}', 200);
              submissions++;
              return http.Response('upstream unavailable', 502);
            }),
          ),
        ),
      );
      await tester.pumpWidget(page());
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextField, 'Địa chỉ HTTPS của agent PC'),
        'https://pc.example',
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'Mã kết nối agent'),
        'token',
      );
      await tester.tap(find.text('Kết nối agent'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextField, 'Giao việc cho agent'),
        'write material',
      );
      tester.testTextInput.hide();
      await tester.scrollUntilVisible(
        find.text('Gửi việc'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.text('Gửi việc'));
      await tester.pumpAndSettle();
      final saved = jsonDecode(
        (await const FlutterSecureStorage().read(
          key: 'plaxis-agent:timeout-owner',
        ))!,
      );
      expect(saved['uncertain'], isTrue);
      expect(submissions, 1);
      await tester.pumpWidget(const SizedBox());
      await tester.pumpAndSettle();
      await tester.pumpWidget(page());
      await tester.pumpAndSettle();
      expect(
        find.text(
          'Yêu cầu trước chưa rõ đã được nhận hay chưa. Không tự gửi lại.',
        ),
        findsOneWidget,
      );
      expect(submissions, 1);
      await tester.pumpWidget(const SizedBox());
    },
  );
}

import 'dart:convert';
import 'package:flutter/widgets.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:workmanager/workmanager.dart';
import 'api.dart';

const notificationJob = 'chatai-notification-check';
const notificationVault = FlutterSecureStorage();
String notificationScope(ChatApi api) => '${api.server.origin}:${api.session!.username}';
final localNotifications = FlutterLocalNotificationsPlugin();
Future<void> initializeLocalNotifications() async {
  await localNotifications.initialize(const InitializationSettings(
    android: AndroidInitializationSettings('chatai_notification')));
}

@pragma('vm:entry-point')
void notificationDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    WidgetsFlutterBinding.ensureInitialized();
    final raw = await notificationVault.read(key: 'session');
    if (raw == null) return true;
    final api = ChatApi();
    try {
      api.session = Session.fromJson(jsonDecode(raw) as Map<String, dynamic>);
      if (await notificationVault.read(key: 'notify-enabled:${notificationScope(api)}') != 'true') return true;
      final result = await api.post('/api/notifications/list', {});
      if (await notificationVault.read(key: 'session') != raw) return true;
      await showAccountNotifications(api, result['notifications'] as List<dynamic>);
      return true;
    } catch (_) { return false; }
    finally { api.close(); }
  });
}

List<Map<String, dynamic>> unseenNotifications(List<dynamic> items, Set<String> seen) => items
    .cast<Map<String, dynamic>>()
    .where((item) => item['read_at'] == null && !seen.contains(item['id']))
    .take(5).toList();

Future<void> showAccountNotifications(ChatApi api, List<dynamic> items) async {
  if (api.session == null) return;
  final scope = notificationScope(api);
  if (await notificationVault.read(key: 'notify-enabled:$scope') != 'true') return;
  final key = 'notify-seen:$scope';
  final raw = await notificationVault.read(key: key);
  final seen = raw == null ? <String>{} : (jsonDecode(raw) as List<dynamic>).cast<String>().toSet();
  await initializeLocalNotifications();
  for (final item in unseenNotifications(items, seen)) {
    final session = await notificationVault.read(key: 'session');
    if (session == null || Session.fromJson(jsonDecode(session) as Map<String, dynamic>).username != api.session!.username) return;
    await localNotifications.show((item['id'] as String).hashCode & 0x7fffffff,
      item['title'] as String, item['text'] as String,
      const NotificationDetails(android: AndroidNotificationDetails(
        'chatai_updates', 'Thông báo ChatAI', channelDescription: 'Thông báo từ quản trị viên',
        importance: Importance.defaultImportance, priority: Priority.defaultPriority,
        visibility: NotificationVisibility.private)));
  }
  // API returns the latest 200; older items remain available inside the application.
  await notificationVault.write(key: key, value: jsonEncode(items.map((item) => item['id']).toList()));
}

Future<bool> enableAccountNotifications(ChatApi api) async {
  if (api.session == null) throw ApiException('Đăng nhập trước khi bật thông báo.');
  await initializeLocalNotifications();
  final android = localNotifications.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();
  final allowed = await android?.requestNotificationsPermission() ?? false;
  if (!allowed) return false;
  final items = await api.post('/api/notifications/list', {});
  final scope = notificationScope(api);
  await notificationVault.write(key: 'notify-seen:$scope', value: jsonEncode((items['notifications'] as List<dynamic>).map((n) => n['id']).toList()));
  await notificationVault.write(key: 'notify-enabled:$scope', value: 'true');
  await Workmanager().initialize(notificationDispatcher);
  await Workmanager().registerPeriodicTask(notificationJob, notificationJob,
    frequency: const Duration(minutes: 15), constraints: Constraints(networkType: NetworkType.connected));
  return true;
}
Future<void> disableAccountNotifications(ChatApi api) async {
  if (api.session != null) await notificationVault.write(key: 'notify-enabled:${notificationScope(api)}', value: 'false');
  await Workmanager().cancelByUniqueName(notificationJob);
  await localNotifications.cancelAll();
}

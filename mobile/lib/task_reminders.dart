import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:workmanager/workmanager.dart';
import 'api.dart';
import 'task_plans.dart';
import 'notifications.dart';

const taskReminderJob = 'chatai-task-reminders';
const taskVault = FlutterSecureStorage();
String reminderScope(ChatApi api) => '${api.server.origin}:${api.session!.username}';
Future<void> enableTaskReminders(ChatApi api) async {
  if (api.session == null) throw ApiException('Đăng nhập trước khi bật nhắc việc.');
  final saved = await taskVault.read(key: api.sessionStorageKey);
  if (saved == null || Session.fromJson(jsonDecode(saved) as Map<String,dynamic>).username != api.session!.username) {
    throw ApiException('Bật Nhớ đăng nhập để nhắc việc chạy khi ứng dụng đóng.');
  }
  await initializeLocalNotifications();
  final android = localNotifications.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();
  if (await android?.requestNotificationsPermission() != true) throw ApiException('Cần cho phép thông báo để nhận nhắc việc.');
  await Workmanager().initialize(notificationDispatcher);
  await Workmanager().registerPeriodicTask(taskReminderJob, taskReminderJob, frequency: const Duration(minutes: 15));
  await taskVault.write(key: 'task-reminders:${reminderScope(api)}', value: 'true');
}
Future<void> disableTaskReminders(ChatApi api) async {
  if (api.session != null) await taskVault.write(key: 'task-reminders:${reminderScope(api)}', value: 'false');
  await Workmanager().cancelByUniqueName(taskReminderJob);
}
Future<void> showTaskReminders(ChatApi api) async {
  if (api.session == null) return;
  final scope = reminderScope(api);
  if (await taskVault.read(key: 'task-reminders:$scope') != 'true') return;
  final plans = await TaskPlanStore(api.server.origin, api.session!.username).load();
  final raw = await taskVault.read(key: 'task-reminded:$scope');
  final seen = raw == null ? <String>{} : (jsonDecode(raw) as List).cast<String>().toSet();
  await initializeLocalNotifications();
  for (final item in dueWorkItems(plans, DateTime.now()).where((t) => !seen.contains(taskReminderToken(t))).take(5)) {
    final saved = await taskVault.read(key: api.sessionStorageKey);
    if (saved == null || Session.fromJson(jsonDecode(saved) as Map<String,dynamic>).username != api.session!.username) return;
    if (await taskVault.read(key: 'task-reminders:$scope') != 'true') return;
    await localNotifications.show(('task:$scope:${item.id}').hashCode & 0x7fffffff,
      'Nhắc việc: ${item.title}', item.detail.isEmpty ? 'Mở Trợ lý công việc để xem tiến độ.' : item.detail,
      const NotificationDetails(android: AndroidNotificationDetails('chatai_tasks', 'Nhắc việc',
        importance: Importance.defaultImportance, priority: Priority.defaultPriority, visibility: NotificationVisibility.private)));
    seen.add(taskReminderToken(item));
  }
  final active = plans.expand((p) => p.items).where((t) => t.due != null && !t.done).map(taskReminderToken).toSet();
  await taskVault.write(key: 'task-reminded:$scope', value: jsonEncode(seen.intersection(active).toList()));
}

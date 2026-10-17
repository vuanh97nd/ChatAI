import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

class WorkItem {
  final String id, title, detail;
  final bool done;
  final DateTime? due;
  WorkItem({required this.id, required this.title, this.detail = '', this.done = false, this.due});
  WorkItem change({bool? done, DateTime? due, bool clearDue = false}) => WorkItem(
    id: id, title: title, detail: detail, done: done ?? this.done, due: clearDue ? null : due ?? this.due);
  Map<String, dynamic> toJson() => {'id': id, 'title': title, 'detail': detail, 'done': done, 'due': due?.toUtc().toIso8601String()};
  factory WorkItem.fromJson(Map<String, dynamic> data) => WorkItem(id: data['id'] as String,
    title: data['title'] as String, detail: data['detail'] as String? ?? '', done: data['done'] == true,
    due: data['due'] == null ? null : DateTime.parse(data['due'] as String).toLocal());
}
class TaskPlan {
  final String id, title;
  final List<WorkItem> items;
  TaskPlan({required this.id, required this.title, required this.items});
  double get progress => items.isEmpty ? 0 : items.where((t) => t.done).length / items.length;
  TaskPlan withItems(List<WorkItem> value) => TaskPlan(id: id, title: title, items: value);
  Map<String, dynamic> toJson() => {'id': id, 'title': title, 'items': items.map((i) => i.toJson()).toList()};
  factory TaskPlan.fromJson(Map<String, dynamic> data) => TaskPlan(id: data['id'] as String,
    title: data['title'] as String, items: (data['items'] as List).map((i) => WorkItem.fromJson(Map<String,dynamic>.from(i as Map))).toList());
}
String taskStorageKey(String origin, String username) => 'task-plans:v1:$origin:$username';
class TaskPlanStore {
  final String key;
  final FlutterSecureStorage vault;
  TaskPlanStore(String origin, String username, {this.vault = const FlutterSecureStorage()}) : key = taskStorageKey(origin, username);
  Future<List<TaskPlan>> load() async {
    final raw = await vault.read(key: key);
    if (raw == null) return [];
    return (jsonDecode(raw) as List).map((i) => TaskPlan.fromJson(Map<String,dynamic>.from(i as Map))).toList();
  }
  Future<void> save(List<TaskPlan> plans) async {
    if (plans.length > 20) throw const FormatException('Tối đa 20 kế hoạch. Xóa kế hoạch cũ trước khi thêm.');
    await vault.write(key: key, value: jsonEncode(plans.map((p) => p.toJson()).toList()));
  }
}
TaskPlan parseSuggestedPlan(String answer) {
  final raw = answer.trim().replaceFirst(RegExp(r'^```(?:json)?\s*', caseSensitive: false), '').replaceFirst(RegExp(r'\s*```$'), '');
  if (raw.length > 40000) throw const FormatException('Kế hoạch AI quá dài.');
  final data = jsonDecode(raw);
  if (data is! Map || data['title'] is! String || (data['title'] as String).trim().isEmpty || (data['title'] as String).length > 160 || data['tasks'] is! List) {
    throw const FormatException('AI chưa trả kế hoạch hợp lệ. Bạn có thể thêm thủ công.');
  }
  final tasks = data['tasks'] as List;
  if (tasks.isEmpty || tasks.length > 20) throw const FormatException('Kế hoạch cần 1–20 việc.');
  final items = tasks.map((t) {
    if (t is! Map || t['title'] is! String || (t['title'] as String).trim().isEmpty || (t['title'] as String).length > 160 || (t['detail'] != null && (t['detail'] is! String || (t['detail'] as String).length > 1200))) {
      throw const FormatException('AI trả một công việc không hợp lệ.');
    }
    // Dates and actions from generated text are never executed or scheduled.
    return WorkItem(id: const Uuid().v4(), title: (t['title'] as String).trim(), detail: (t['detail'] as String? ?? '').trim());
  }).toList();
  return TaskPlan(id: const Uuid().v4(), title: (data['title'] as String).trim(), items: items);
}
List<WorkItem> dueWorkItems(List<TaskPlan> plans, DateTime now) => plans.expand((p) => p.items)
  .where((t) => !t.done && t.due != null && !t.due!.isAfter(now)).toList();
String taskReminderToken(WorkItem item) => '${item.id}:${item.due!.millisecondsSinceEpoch}';

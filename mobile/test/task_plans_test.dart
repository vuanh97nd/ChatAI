import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:chatai_mobile/task_plans.dart';
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('saved work survives a new store instance and is isolated by account', () async {
    FlutterSecureStorage.setMockInitialValues({});
    final plan=TaskPlan(id:'p',title:'Work',items:[WorkItem(id:'t',title:'Prepare',done:true)]);
    await TaskPlanStore('https://one.example','alice').save([plan]);
    final saved=await TaskPlanStore('https://one.example','alice').load();
    expect(saved.single.progress,1);
    expect(await TaskPlanStore('https://one.example','bob').load(),isEmpty);
  });
  test('AI plan is preview data and cannot schedule or execute hidden actions', () {
    final plan = parseSuggestedPlan(jsonEncode({'title': 'Cuộc họp', 'tasks': [
      {'title': 'Chuẩn bị báo cáo', 'detail': 'Đối chiếu số liệu', 'done': true, 'due': '2026-10-18', 'action': 'send_email'},
    ]}));
    expect(plan.items.single.done, false); expect(plan.items.single.due, isNull); expect(plan.progress, 0);
  });
  test('malformed or oversized AI plans cannot be saved as valid suggestions', () {
    for (final answer in ['Not JSON', '{"title":"","tasks":[]}', jsonEncode({'title': 'Plan', 'tasks': List.generate(21, (_) => {'title':'A'})})]) {
      expect(() => parseSuggestedPlan(answer), throwsFormatException);
    }
  });
  test('progress and due dates survive a storage round trip', () {
    final plan = TaskPlan(id: 'p', title: 'Work', items: [WorkItem(id: 't', title: 'Prepare', done: true, due: DateTime(2026,10,18,14,30))]);
    final restored = TaskPlan.fromJson(jsonDecode(jsonEncode(plan.toJson())) as Map<String,dynamic>);
    expect(restored.progress, 1); expect(restored.items.single.due, plan.items.single.due);
  });
  test('completed and future tasks do not produce overdue reminders', () {
    final now=DateTime(2026,10,18,14);
    final plan=TaskPlan(id:'p',title:'Work',items:[
      WorkItem(id:'due',title:'Due',due:now.subtract(const Duration(minutes:1))),
      WorkItem(id:'done',title:'Done',due:now,done:true),
      WorkItem(id:'future',title:'Future',due:now.add(const Duration(hours:1))),
      WorkItem(id:'none',title:'No reminder'),
    ]);
    expect(dueWorkItems([plan],now).map((t)=>t.id),['due']);
    final item=plan.items.first;
    expect(taskReminderToken(item.change(due:now)),isNot(taskReminderToken(item)));
  });
  test('task storage separates account and server identities', () {
    expect(taskStorageKey('https://one.example','alice'),isNot(taskStorageKey('https://one.example','bob')));
    expect(taskStorageKey('https://one.example','alice'),isNot(taskStorageKey('https://two.example','alice')));
  });
}

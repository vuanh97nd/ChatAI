import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import 'api.dart';
import 'ios_settings.dart';
import 'package:flutter/cupertino.dart';
import 'task_plans.dart';
import 'task_reminders.dart';

class TaskPage extends StatefulWidget {
  final ChatApi api;
  final bool embedded;
  final String provider;
  final String initialGoal;
  const TaskPage({super.key, required this.api, this.embedded = false, required this.provider, this.initialGoal = ''});
  @override
  State<TaskPage> createState() => _TaskPageState();
}
class _TaskPageState extends State<TaskPage> {
  late final TextEditingController goal;
  late final TaskPlanStore store;
  List<TaskPlan> plans = [];
  TaskPlan? suggestion;
  bool busy = false, loaded = false, reminderEnabled = false;
  String message = '';
  Timer? reminders;
  @override
  void initState() {
    super.initState();
    goal = TextEditingController(text: widget.initialGoal);
    store = TaskPlanStore(widget.api.server.origin, widget.api.session!.username);
    unawaited(load());
    reminders = Timer.periodic(const Duration(seconds: 30), (_) { if (mounted && TickerMode.of(context)) { unawaited(showTaskReminders(widget.api).catchError((Object _) {})); } });
  }
  @override
  void dispose() { reminders?.cancel(); goal.dispose(); super.dispose(); }
  Future<void> run(Future<void> Function() action) async {
    if (busy) return;
    setState(() { busy = true; message = ''; });
    try { await action(); } catch (e) { if (mounted) setState(() => message = '$e'); }
    finally { if (mounted) setState(() => busy = false); }
  }
  Future<void> load() => run(() async {
    final saved = await store.load();
    final enabled = await taskVault.read(key: 'task-reminders:${reminderScope(widget.api)}') == 'true';
    if (mounted) setState(() { plans = saved; loaded = true; reminderEnabled = enabled; });
  });
  Future<void> persist(List<TaskPlan> next) async {
    await store.save(next);
    if (mounted) setState(() => plans = next);
  }
  Future<void> generate() => run(() async {
    final text = goal.text.trim();
    if (text.isEmpty) throw ApiException('Nhập mục tiêu cần lập kế hoạch.');
    final answer = await widget.api.answer(widget.provider, [
      {'role': 'user', 'content': 'Lập kế hoạch thực tế cho mục tiêu sau bằng tiếng Việt. '
        'Chỉ trả JSON {"title":"Tên kế hoạch","tasks":[{"title":"Tên việc","detail":"Cách làm hoặc kết quả cần đạt"}]}. '
        'Tối đa 20 việc, title tối đa 160 ký tự, detail tối đa 1200 ký tự. '
        'Không tự gửi tin, đặt lịch hoặc thực hiện công việc. Nếu thiếu dữ kiện, ghi rõ việc cần xác minh. '
        'Mục tiêu của người dùng: $text'},
    ], [], autoSearch: false);
    final parsed = parseSuggestedPlan(answer);
    if (mounted) setState(() => suggestion = parsed);
  });
  Future<void> manual() async {
    final value = await showDialog<String>(context: context, builder: (_) => const _WorkNameDialog());
    if (value != null && mounted) await run(() => persist([...plans, TaskPlan(id: const Uuid().v4(), title: value,
      items: [WorkItem(id: const Uuid().v4(), title: value)])]));
  }
  Future<void> coach(TaskPlan plan) => run(() async {
    final answer = await widget.api.answer(widget.provider, [
      {'role': 'user', 'content': 'Dựa vào kế hoạch và tiến độ dưới đây, gợi ý một việc nên làm tiếp theo, '
        'giải thích ngắn gọn cách làm và thông tin còn thiếu cần xác minh. Không tự thực hiện thao tác. '
        'Nếu đã hoàn thành tất cả, hãy nói rõ. Dữ liệu kế hoạch: ${jsonEncode(plan.toJson())}'},
    ], [], autoSearch: false);
    if (!mounted) return;
    await showDialog<void>(context: context, builder: (context) => IosAlertDialog(title: const Text('Bước tiếp theo'),
      content: SingleChildScrollView(child: SelectableText(answer)),
      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Đóng'))]));
  });
  Future<void> updateItem(TaskPlan plan, WorkItem item) => persist(plans.map((p) => p.id == plan.id
    ? p.withItems(p.items.map((t) => t.id == item.id ? item : t).toList()) : p).toList());
  Future<void> setDue(TaskPlan plan, WorkItem item) async {
    final now = DateTime.now();
    final initial = item.due != null && item.due!.isAfter(now) ? item.due! : now;
    final date = await showDatePicker(context: context, initialDate: initial, firstDate: DateTime(now.year, now.month, now.day), lastDate: DateTime(now.year + 5));
    if (date == null || !mounted) return;
    final time = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(initial));
    if (time == null || !mounted) return;
    final due = DateTime(date.year, date.month, date.day, time.hour, time.minute);
    if (!due.isAfter(DateTime.now())) { setState(() => message = 'Chọn thời gian trong tương lai.'); return; }
    await run(() async {
      await updateItem(plan, item.change(due: due));
      if (mounted) setState(() => message = 'Đã lưu hạn việc. Bấm Bật nhắc việc để nhận thông báo nền.');
    });
  }
  String dueLabel(DateTime value) => '${value.day}/${value.month}/${value.year} ${value.hour.toString().padLeft(2,'0')}:${value.minute.toString().padLeft(2,'0')}';
  @override
  Widget build(BuildContext context) => Scaffold(appBar: widget.embedded ? null : AppBar(title: const Text('Trợ lý công việc'), actions: [
    IconButton(onPressed: busy ? null : load, tooltip: 'Tải lại tiến độ', icon: const Icon(Icons.refresh)),
  ]), body: IosPageList(title: 'Công việc', subtitle: 'Lên kế hoạch, theo dõi từng bước và nhắc việc.', children: [
    if (widget.embedded) Align(alignment: Alignment.centerRight, child: IconButton(onPressed: busy ? null : load, tooltip: 'Tải lại tiến độ', icon: const Icon(Icons.refresh))),
    const Text('Kế hoạch và tiến độ được lưu riêng cho tài khoản trên điện thoại này. Chưa đồng bộ sang thiết bị khác.'),
    const SizedBox(height: 12),
    TextField(controller: goal, enabled: !busy, minLines: 2, maxLines: 5, maxLength: 2000,
      decoration: const InputDecoration(labelText: 'Bạn muốn hoàn thành việc gì?', hintText: 'Ví dụ: Chuẩn bị cuộc họp tuần sau')),
    Wrap(spacing: 8, children: [
      FilledButton.icon(onPressed: busy || !loaded ? null : generate, icon: const Icon(CupertinoIcons.sparkles), label: const Text('AI lập kế hoạch')),
      OutlinedButton(onPressed: busy || !loaded ? null : manual, child: const Text('Thêm thủ công')),
      OutlinedButton.icon(onPressed: busy ? null : () => run(() async {
        await enableTaskReminders(widget.api);
        await showTaskReminders(widget.api);
        if (mounted) setState(() { reminderEnabled = true; message = 'Đã bật nhắc việc. Android kiểm tra khoảng 15 phút/lần; có thể chậm khi tiết kiệm pin.'; });
      }), icon: const Icon(CupertinoIcons.bell), label: const Text('Bật nhắc việc')),
      TextButton(onPressed: busy ? null : () => run(() async {
        await disableTaskReminders(widget.api);
        if (mounted) setState(() { reminderEnabled = false; message = 'Đã tắt nhắc việc nền.'; });
      }), child: const Text('Tắt nhắc việc')),
    ]),
    Text(reminderEnabled ? 'Nhắc việc nền: đang bật · kiểm tra khoảng 15 phút/lần' : 'Nhắc việc nền: đang tắt'),
    if (busy) const Padding(padding: EdgeInsets.all(16), child: Center(child: CupertinoActivityIndicator())),
    if (message.isNotEmpty) Padding(padding: const EdgeInsets.symmetric(vertical: 12), child: SelectableText(message)),
    if (suggestion != null) Card(child: Padding(padding: const EdgeInsets.all(12), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Đề xuất: ${suggestion!.title}', style: Theme.of(context).textTheme.titleMedium),
      const Text('Xem lại trước khi lưu. Chưa có thao tác hay nhắc việc nào được thực hiện.'),
      for (final item in suggestion!.items) ListTile(title: Text(item.title), subtitle: Text(item.detail)),
      Wrap(spacing: 8, children: [FilledButton(onPressed: busy ? null : () => run(() async {
        await persist([...plans, suggestion!]);
        if (mounted) setState(() { suggestion = null; goal.clear(); });
      }), child: const Text('Lưu kế hoạch')),
        TextButton(onPressed: busy ? null : () => setState(() => suggestion = null), child: const Text('Bỏ đề xuất'))]),
    ]))),
    if (loaded && plans.isEmpty) const Padding(padding: EdgeInsets.all(16), child: Text('Chưa có kế hoạch. Nhập mục tiêu để AI chia thành các bước hoặc thêm việc thủ công.')),
    for (final plan in plans) Card(child: Padding(padding: const EdgeInsets.all(8), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      ListTile(title: Text(plan.title), subtitle: Text('${plan.items.where((t) => t.done).length}/${plan.items.length} việc đã hoàn thành'),
        trailing: IconButton(tooltip: 'Xóa kế hoạch', icon: const Icon(CupertinoIcons.trash), onPressed: busy ? null : () async {
          final yes = await showDialog<bool>(context: context, builder: (context) => IosAlertDialog(title: const Text('Xóa kế hoạch?'), content: Text(plan.title),
            actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Giữ lại')),
              FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Xóa'))]));
          if (yes == true && mounted) await run(() => persist(plans.where((p) => p.id != plan.id).toList()));
        })),
      LinearProgressIndicator(value: plan.progress),
      TextButton.icon(onPressed: busy ? null : () => coach(plan), icon: const Icon(Icons.playlist_play), label: const Text('AI gợi ý bước tiếp theo')),
      for (final item in plan.items) Column(children: [
        CheckboxListTile(value: item.done, onChanged: busy ? null : (value) => run(() => updateItem(plan, item.change(done: value))),
          title: Text(item.title), subtitle: item.detail.isEmpty ? null : Text(item.detail), controlAffinity: ListTileControlAffinity.leading),
        Row(children: [Expanded(child: Padding(padding: const EdgeInsets.only(left: 16), child: Text(item.due == null ? 'Chưa đặt hạn' : dueLabel(item.due!)))),
          IconButton(tooltip: 'Đặt hạn việc', onPressed: busy || item.done ? null : () => setDue(plan, item), icon: const Icon(CupertinoIcons.calendar)),
          if (item.due != null) IconButton(tooltip: 'Bỏ hạn việc', onPressed: busy ? null : () => run(() => updateItem(plan, item.change(clearDue: true))), icon: const Icon(Icons.event_busy)),
        ]),
      ]),
    ]))),
  ]));
}

class _WorkNameDialog extends StatefulWidget {
  const _WorkNameDialog();
  @override
  State<_WorkNameDialog> createState() => _WorkNameDialogState();
}
class _WorkNameDialogState extends State<_WorkNameDialog> {
  final name = TextEditingController();
  @override
  void dispose() { name.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => IosAlertDialog(title: const Text('Thêm việc thủ công'),
    content: TextField(controller: name, maxLength: 160, autofocus: true, decoration: const InputDecoration(labelText: 'Việc cần làm')),
    actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Hủy')),
      FilledButton(onPressed: () { if (name.text.trim().isNotEmpty) Navigator.pop(context, name.text.trim()); }, child: const Text('Lưu'))]);
}

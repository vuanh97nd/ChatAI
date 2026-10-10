import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:intl/intl.dart';
import 'package:uuid/uuid.dart';
import 'api.dart';

/// Durable operation IDs: a timeout never becomes a second credit or notification.
class AdminActions {
  final ChatApi api;
  final Future<String?> Function(String) read;
  final Future<void> Function(String, String?) write;
  final String owner;
  AdminActions(this.api, {required this.read, required this.write}) : owner = api.session!.username;
  void check() {
    if (api.session?.admin != true || api.session?.username != owner) {
      throw ApiException('Chỉ dành cho Admin đang đăng nhập.', 403);
    }
  }
  String key(String path) => 'admin-pending:${api.server.origin}:$owner:$path';
  Future<Map<String, dynamic>?> pending(String path) async {
    check(); final raw = await read(key(path));
    return raw == null ? null : jsonDecode(raw) as Map<String, dynamic>;
  }
  Future<Map<String, dynamic>> send(String path, Map<String, dynamic> payload, String idField) async {
    check(); final old = await pending(path);
    if (old != null && jsonEncode(old['payload']) != jsonEncode(payload)) {
      throw ApiException('Giao dịch trước chưa rõ kết quả. Thử lại đúng nội dung đã lưu trước khi tạo yêu cầu khác.');
    }
    final attempt = old ?? {'payload': payload, 'id': const Uuid().v4()};
    await write(key(path), jsonEncode(attempt));
    check();
    final result = await api.post(path, {...payload, idField: attempt['id']});
    await write(key(path), null);
    return result;
  }
}

class AdminPage extends StatefulWidget {
  final ChatApi api;
  const AdminPage({super.key, required this.api});
  @override
  State<AdminPage> createState() => _AdminPageState();
}
class _AdminPageState extends State<AdminPage> {
  static const vault = FlutterSecureStorage();
  final search = TextEditingController(), target = TextEditingController();
  final amount = TextEditingController(), note = TextEditingController();
  final title = TextEditingController(), text = TextEditingController();
  final recipient = TextEditingController(text: '*');
  final fee = TextEditingController(), price = TextEditingController();
  late final AdminActions actions;
  List<dynamic> users = [];
  Map<String, dynamic>? detail;
  String? message;
  bool busy = false, pricesLoaded = false;
  int offset = 0, total = 0;
  String filter = 'all';
  String money(num value) => '${NumberFormat.decimalPattern('vi').format(value)} đ';
  @override
  void initState() {
    super.initState();
    actions = AdminActions(widget.api, read: (key) => vault.read(key: key),
      write: (key, value) => value == null ? vault.delete(key: key) : vault.write(key: key, value: value));
    run(() async {
      for (final path in ['/api/admin/billing/credit', '/api/admin/notifications/send']) {
        final saved = await actions.pending(path);
        if (!mounted || saved == null) continue;
        final p = saved['payload'] as Map<String, dynamic>;
        if (path.endsWith('credit')) {
          target.text = p['target'] as String; amount.text = '${p['amount']}'; note.text = p['note'] as String;
        } else {
          title.text = p['title'] as String; text.text = p['text'] as String; recipient.text = p['target'] as String;
        }
        message = 'Có yêu cầu chưa xác minh. Nội dung đã được khôi phục để thử lại cùng mã.';
      }
      await loadUsers(); await loadPrices();
    });
  }
  @override
  void dispose() {
    for (final c in [search, target, amount, note, title, text, recipient, fee, price]) { c.dispose(); }
    super.dispose();
  }
  Future<void> run(Future<void> Function() fn) async {
    if (busy) return;
    setState(() => busy = true);
    try { actions.check(); await fn(); }
    catch (e) { if (mounted) setState(() => message = '$e'); }
    finally { if (mounted) setState(() => busy = false); }
  }
  Future<void> loadUsers() async {
    final result = await widget.api.post('/api/admin/accounts/list', {'offset': offset, 'search': search.text.trim(), 'filter': filter});
    if (mounted) setState(() { users = result['users'] as List<dynamic>; total = (result['total'] as num).toInt(); });
  }
  Future<void> loadPrices() async {
    final result = await widget.api.post('/api/admin/billing/config/get', {});
    if (!mounted) return;
    final config = result['config'] as Map<String, dynamic>;
    setState(() { fee.text = '${config['service_fee']}'; price.text = '${config['token_price']}'; pricesLoaded = true; });
  }
  Future<bool> confirm(String content) async => await showDialog<bool>(context: context,
    builder: (c) => AlertDialog(title: const Text('Xác nhận thao tác Admin'), content: Text(content), actions: [
      TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Hủy')),
      FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Thực hiện'))])) ?? false;
  Future<void> changeUser(Map<String, dynamic> user, String action) async {
    const labels = {'lock': 'Khóa tài khoản', 'unlock': 'Mở khóa tài khoản', 'revoke': 'Thu hồi phiên', 'delete': 'Xóa mềm tài khoản', 'restore': 'Khôi phục tài khoản'};
    if (busy || !await confirm('${labels[action]}: ${user['username']}? Thao tác có thể thu hồi phiên đăng nhập.')) return;
    await run(() async {
      final result = await widget.api.post('/api/admin/accounts/$action', {'target': user['username'], 'confirm': true});
      message = result['message'] as String?; detail = null; await loadUsers();
    });
  }
  Future<void> inspect(String username) async => run(() async {
    final values = await Future.wait([
      widget.api.post('/api/admin/accounts/detail', {'target': username}),
      widget.api.post('/api/admin/billing/status', {'target': username}),
    ]);
    if (mounted) setState(() { target.text = username; detail = {'profile': values[0], 'billing': values[1]}; });
  });
  Future<void> credit() async {
    final value = int.tryParse(amount.text.trim());
    if (target.text.trim().isEmpty || value == null || value < 1000 || value > 5000000 || note.text.trim().isEmpty) {
      setState(() => message = 'Nhập tài khoản, 1.000–5.000.000 đ và lý do nạp.'); return;
    }
    final payload = {'target': target.text.trim(), 'amount': value, 'note': note.text.trim()};
    if (!await confirm('Nạp ${money(value)} cho ${payload['target']}?')) return;
    await run(() async {
      await actions.send('/api/admin/billing/credit', payload, 'request_id');
      message = 'Đã nạp thủ công.'; await loadUsers();
    });
  }
  Future<void> notify() async {
    final payload = {'title': title.text.trim(), 'text': text.text.trim(), 'target': recipient.text.trim()};
    if (payload.values.any((v) => v.isEmpty) || payload['title']!.length > 160 || payload['text']!.length > 10000) {
      setState(() => message = 'Nhập tiêu đề (tối đa 160), nội dung (10.000) và người nhận.'); return;
    }
    if (!await confirm('Gửi thông báo đến ${payload['target'] == '*' ? 'tất cả người dùng' : payload['target']}?')) return;
    await run(() async { await actions.send('/api/admin/notifications/send', payload, 'id'); message = 'Đã gửi thông báo.'; });
  }
  Future<void> savePrices() async {
    final f = int.tryParse(fee.text.trim()), p = int.tryParse(price.text.trim());
    if (f == null || f < 0 || f > 5000000 || p == null || p < 1 || p > 10000000) {
      setState(() => message = 'Phí duy trì 0–5.000.000 đ; giá token 1–10.000.000 đ/triệu.'); return;
    }
    if (!await confirm('Phí duy trì ${money(f)}/30 ngày; DeepSeek ${money(p)}/triệu token?')) return;
    await run(() async { await widget.api.post('/api/admin/billing/fee/save', {'service_fee': f, 'token_price': p}); message = 'Đã cập nhật bảng giá.'; await loadPrices(); });
  }
  Widget field(TextEditingController c, String label, {bool number = false, int lines = 1}) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6), child: TextField(controller: c, enabled: !busy,
      keyboardType: number ? TextInputType.number : null, minLines: lines, maxLines: lines,
      decoration: InputDecoration(labelText: label, border: const OutlineInputBorder())));
  @override
  Widget build(BuildContext context) {
    if (widget.api.session?.admin != true) return const Scaffold(body: Center(child: Text('Chỉ dành cho Admin.')));
    return DefaultTabController(length: 3, child: Scaffold(
      appBar: AppBar(title: const Text('Quản trị'), bottom: const TabBar(isScrollable: true, tabs: [
        Tab(text: 'Người dùng'), Tab(text: 'Thông báo'), Tab(text: 'Thanh toán')])),
      body: Column(children: [
        if (busy) const LinearProgressIndicator(),
        if (message != null) MaterialBanner(content: Text(message!), actions: [TextButton(onPressed: () => setState(() => message = null), child: const Text('Đóng'))]),
        Expanded(child: TabBarView(children: [
          ListView(padding: const EdgeInsets.all(16), children: [
            field(search, 'Tìm tên / email'),
            DropdownButton<String>(value: filter, items: const [
              DropdownMenuItem(value: 'all', child: Text('Tất cả')),
              DropdownMenuItem(value: 'active', child: Text('Hoạt động')),
              DropdownMenuItem(value: 'locked', child: Text('Đã khóa')),
              DropdownMenuItem(value: 'deleted', child: Text('Đã xóa')),
            ], onChanged: busy ? null : (v) { setState(() { filter = v!; offset = 0; }); run(loadUsers); }),
            FilledButton(onPressed: busy ? null : () { offset = 0; run(loadUsers); }, child: const Text('Tìm / Làm mới')),
            Text('$total người dùng · trang ${offset ~/ 100 + 1} · token theo tháng, giờ Việt Nam'),
            for (final item in users) Builder(builder: (_) {
              final u = item as Map<String, dynamic>, b = u['billing'] as Map<String, dynamic>? ?? {};
              return Card(child: Column(children: [ListTile(title: Text('${u['fullname']} · ${u['username']}'),
                subtitle: Text('${u['email']} · ${u['account_status']}\n${b['month_tokens'] ?? 0} token tháng này · ${money((b['balance_vnd'] as num?) ?? 0)}'),
                onTap: busy ? null : () => inspect(u['username'] as String)),
                Wrap(children: [
                  if (u['account_status'] != 'deleted') ...[
                    TextButton(onPressed: busy ? null : () => changeUser(u, u['account_status'] == 'locked' ? 'unlock' : 'lock'), child: Text(u['account_status'] == 'locked' ? 'Mở khóa' : 'Khóa')),
                    TextButton(onPressed: busy ? null : () => changeUser(u, 'revoke'), child: const Text('Thu hồi phiên')),
                    TextButton(onPressed: busy ? null : () => changeUser(u, 'delete'), child: const Text('Xóa mềm')),
                  ] else if (u['can_restore'] == true)
                    TextButton(onPressed: busy ? null : () => changeUser(u, 'restore'), child: const Text('Khôi phục')),
                ]),
              ]));
            }),
            Row(children: [TextButton(onPressed: busy || offset == 0 ? null : () { offset -= 100; run(loadUsers); }, child: const Text('Trước')),
              TextButton(onPressed: busy || offset + 100 >= total ? null : () { offset += 100; run(loadUsers); }, child: const Text('Sau'))]),
            if (detail != null) ...[
              Text('Chi tiết: ${target.text}', style: Theme.of(context).textTheme.titleLarge),
              for (final m in detail!['billing']['monthly_usage'] as List<dynamic>)
                ListTile(title: Text('Tháng ${m['month']}: ${m['tokens']} token'), subtitle: Text('Phí ${money(m['fee_vnd'] as num)}')),
              const Text('Lịch sử thao tác Admin'),
              for (final event in detail!['profile']['audit'] as List<dynamic>)
                ListTile(title: Text('${event['action']} · ${event['created_at']}'), subtitle: Text('${event['details']}')),
            ],
          ]),
          ListView(padding: const EdgeInsets.all(16), children: [
            field(recipient, 'Người nhận: * = tất cả, hoặc tên tài khoản'),
            field(title, 'Tiêu đề'), field(text, 'Nội dung', lines: 5),
            FilledButton(onPressed: busy ? null : notify, child: const Text('Gửi thông báo')),
          ]),
          ListView(padding: const EdgeInsets.all(16), children: [
            const Text('Nạp thủ công có lưu Admin thực hiện và lý do.'),
            field(target, 'Tên tài khoản nhận'), field(amount, 'Số tiền (đ)', number: true), field(note, 'Lý do'),
            FilledButton(onPressed: busy ? null : credit, child: const Text('Nạp thủ công')),
            const Divider(), const Text('Bảng giá dùng chung trên server'),
            field(fee, 'Phí duy trì / 30 ngày (0 = miễn phí)', number: true),
            field(price, 'Giá DeepSeek / triệu token', number: true),
            FilledButton(onPressed: busy || !pricesLoaded ? null : savePrices, child: const Text('Lưu bảng giá')),
            TextButton(onPressed: busy ? null : () => run(loadPrices), child: const Text('Tải lại bảng giá')),
          ]),
        ])),
      ])));
  }
}

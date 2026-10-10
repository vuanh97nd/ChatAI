import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:intl/intl.dart';
import 'package:uuid/uuid.dart';
import 'api.dart';
import 'voice.dart';
import 'computer.dart';
import 'admin.dart';
import 'notifications.dart';

const storage = FlutterSecureStorage();
const uuid = Uuid();
String money(num value) => '${NumberFormat.decimalPattern('vi').format(value)} đ';

void main() => runApp(const ChatApp());
class ChatApp extends StatelessWidget {
  const ChatApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Chat AI', debugShowCheckedModeBanner: false,
    theme: ThemeData(brightness: Brightness.dark, useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff6d65ff),
        brightness: Brightness.dark), scaffoldBackgroundColor: const Color(0xff202020)),
    home: const Home(),
  );
}

class StartupScreen extends StatelessWidget {
  const StartupScreen({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(body: SafeArea(child: Center(child: Column(
    mainAxisSize: MainAxisSize.min, children: [
    Image.asset('assets/chat_ai.png', width: 112, height: 112, semanticLabel: 'Logo ChatAI'),
    const SizedBox(height: 24),
    Text('Chat AI', style: Theme.of(context).textTheme.headlineMedium),
    const SizedBox(height: 24),
    const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2)),
    const SizedBox(height: 12), const Text('Đang khởi động…'),
  ]))));
}

class Home extends StatefulWidget {
  const Home({super.key});
  @override
  State<Home> createState() => _HomeState();
}
class _HomeState extends State<Home> with WidgetsBindingObserver {
  final api = ChatApi();
  final voice = VoiceController();
  int? readingMessage;
  final input = TextEditingController();
  final amount = TextEditingController(text: '50000');
  String device = '', provider = 'nvidia';
  bool loading = true, sending = false, working = false;
  String? error;
  int tab = 0, guestRemaining = 3;
  String guestToken = '';
  Map<String, dynamic>? guestPending;
  List<Map<String, String>> messages = [];
  List<dynamic> memories = [], notifications = [], conversations = [];
  String? conversation;
  Map<String, dynamic>? billing, order;
  Timer? poll;
  int pollSeconds = 10;
  bool pollBusy = false;
  bool foreground = true;
  int? requestedAmount;
  String? paymentRequest;

  @override
  void initState() {
    super.initState(); WidgetsBinding.instance.addObserver(this);
    voice.addListener(voiceChanged); restore();
  }
  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this); poll?.cancel();
    voice.removeListener(voiceChanged); voice.dispose();
    api.close(); input.dispose(); amount.dispose(); super.dispose();
  }
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // A permission dialog is inactive, but it must not cancel first-time setup.
    if (state == AppLifecycleState.inactive) return;
    foreground = state == AppLifecycleState.resumed;
    if (!foreground) { poll?.cancel(); unawaited(voice.stop()); }
    else if (order != null) { schedulePoll(); }
  }
  void changed(VoidCallback fn) { if (mounted) setState(fn); }
  void voiceChanged() {
    changed(() {
      if (voice.error != null) error = voice.error;
      if (!voice.speaking) readingMessage = null;
    });
  }
  Future<void> dictate() async {
    if (voice.listening || voice.starting) { await voice.stop(); return; }
    changed(() => error = null);
    final prefix = input.text.trimRight();
    await voice.start((words) {
      if (!mounted) return;
      final text = prefix.isEmpty ? words : '$prefix $words';
      input.value = TextEditingValue(text: text, selection: TextSelection.collapsed(offset: text.length));
    });
  }
  Future<void> readMessage(int index) async {
    if (readingMessage == index && voice.speaking) { await voice.stop(); return; }
    changed(() => readingMessage = index);
    await voice.read(messages[index]['content']!);
  }
  Future<void> restore() async {
    try {
      device = await storage.read(key: 'device') ?? uuid.v4();
      await storage.write(key: 'device', value: device);
      guestToken = await storage.read(key: 'guest_token') ?? '${uuid.v4()}${uuid.v4()}'.replaceAll('-', '');
      await storage.write(key: 'guest_token', value: guestToken);
      final pendingRaw = await storage.read(key: 'guest_pending');
      if (pendingRaw != null) {
        guestPending = jsonDecode(pendingRaw) as Map<String, dynamic>;
        input.text = guestPending!['text'] as String;
      }
      final raw = await storage.read(key: 'session');
      if (raw != null) {
        api.session = Session.fromJson(jsonDecode(raw) as Map<String, dynamic>);
        await refresh();
      } else {
        final status = await api.post('/api/mobile/guest/status', {'guest_token': guestToken}, authenticated: false);
        guestRemaining = (status['remaining'] as num).toInt();
      }
    } catch (e) { changed(() => error = '$e'); }
    finally { changed(() => loading = false); }
  }
  Future<void> guard(Future<void> Function() fn) async {
    if (working) return;
    changed(() { working = true; error = null; });
    try { await fn(); }
    catch (e) { changed(() => error = '$e'); }
    finally { changed(() => working = false); }
  }
  Future<void> refresh() async {
    // Explicit refresh only: no background wallet/history scan.
    final values = await Future.wait([
      api.post('/api/billing/status', {}),
      api.post('/api/memory/personal/list', {}).catchError((Object e) {
        return <String, dynamic>{'items': <dynamic>[], 'warning': '$e'};
      }),
      api.post('/api/notifications/list', {}),
      api.post('/api/conversations/list', {}),
    ]);
    try { await showAccountNotifications(api, values[2]['notifications'] as List<dynamic>); } catch (_) {}
    changed(() {
      billing = values[0]; memories = values[1]['items'] as List<dynamic>;
      notifications = values[2]['notifications'] as List<dynamic>;
      conversations = values[3]['conversations'] as List<dynamic>;
      if (values[1]['warning'] != null) error = values[1]['warning'] as String;
    });
  }
  Future<void> authenticated(Session session) async {
    changed(() { messages = []; conversation = null; provider = 'nvidia'; });
    await storage.write(key: 'session', value: jsonEncode(session.toJson()));
    changed(() { loading = false; error = null; });
    await guard(refresh);
  }
  Future<void> signOut() async {
    poll?.cancel(); await voice.stop();
    try { await disableAccountNotifications(api); } catch (_) {}
    // Local logout always completes, including when the server is unavailable.
    try { await api.post('/api/logout', {'client_type': 'android_companion'}); } catch (_) {}
    await storage.delete(key: 'session');
    api.session = null;
    changed(() { messages = []; memories = []; notifications = []; conversations = [];
      conversation = null; billing = null; order = null; paymentRequest = null; requestedAmount = null; error = null; tab = 0; provider = 'nvidia'; });
  }
  Future<void> send() async {
    final text = input.text.trim();
    if (text.isEmpty || sending || working) return;
    if (api.session == null) { await sendGuest(); return; }
    changed(() { sending = true; error = null; });
    await voice.stop();
    final pending = <String, String>{'role': 'user', 'content': text};
    bool userSaved = false;
    try {
      if (conversation == null) {
        final result = await api.post('/api/conversations/create', {'title': text});
        conversation = (result['conversation'] as Map<String, dynamic>)['id'] as String;
      }
      await api.post('/api/conversations/append', {'conversation_id': conversation,
        'role': 'user', 'content': text, 'client_id': uuid.v4()});
      userSaved = true;
      changed(() { messages.add(pending); input.clear(); });
      final history = messages.length > 24 ? messages.sublist(messages.length - 24) : messages;
      final answer = await api.answer(provider, history, memories);
      changed(() => messages.add({'role': 'assistant', 'content': answer}));
      try {
        await api.post('/api/conversations/append', {'conversation_id': conversation,
          'role': 'assistant', 'content': answer, 'client_id': uuid.v4()});
      } catch (_) {
        changed(() => error = 'Đã có câu trả lời nhưng chưa lưu lên server. Hãy sao chép để giữ lại.');
      }
    } catch (e) {
      changed(() => error = '$e${userSaved ? '\nCâu hỏi đã lưu; chưa có câu trả lời. Có thể gửi yêu cầu tiếp theo.' : ''}');
    } finally { changed(() => sending = false); }
  }
  Future<void> openLogin() async {
    await voice.stop();
    if (!mounted) return;
    await Navigator.push<void>(context, MaterialPageRoute(builder: (c) => LoginPage(
      api: api, device: device, onLogin: (session) async {
        await authenticated(session);
        if (c.mounted) Navigator.pop(c);
      })));
  }
  Future<void> sendGuest() async {
    if (guestRemaining <= 0 && guestPending == null) { await openLogin(); return; }
    await voice.stop();
    changed(() { sending = true; error = null; });
    try {
      final text = input.text.trim();
      if (guestPending != null && guestPending!['text'] != text) {
        throw ApiException('Lượt trước chưa rõ kết quả. Thử lại đúng nội dung hoặc đăng nhập.');
      }
      final history = messages.length > 10 ? messages.sublist(messages.length - 10) : messages;
      guestPending ??= {'id': uuid.v4(), 'text': text, 'messages': [...history, {'role': 'user', 'content': text}]};
      await storage.write(key: 'guest_pending', value: jsonEncode(guestPending));
      final result = await api.guestAnswer(guestToken, guestPending!['id'] as String,
        (guestPending!['messages'] as List<dynamic>).map((m) => {'role': m['role'] as String, 'content': m['content'] as String}).toList());
      await storage.delete(key: 'guest_pending'); guestPending = null;
      changed(() { messages.add({'role': 'user', 'content': text}); messages.add({'role': 'assistant', 'content': result['answer'] as String});
        input.clear(); guestRemaining = (result['remaining'] as num).toInt(); });
    } catch (e) {
      changed(() { error = '$e'; if (e is ApiException && e.status == 401) guestRemaining = 0; });
    } finally { changed(() => sending = false); }
  }
  Widget guestChat() => Scaffold(appBar: AppBar(title: const Text('Chat AI'), actions: [
    TextButton(onPressed: sending ? null : openLogin, child: const Text('Đăng nhập'))]),
    body: SafeArea(child: Column(children: [
      Padding(padding: const EdgeInsets.all(12), child: Text('Dùng thử NVIDIA · còn $guestRemaining/3 lượt trên thiết bị này')),
      if (error != null) Padding(padding: const EdgeInsets.all(12), child: Text(error!)),
      if (guestRemaining == 0) TextButton(onPressed: sending ? null : openLogin, child: const Text('Đăng nhập / Đăng ký để tiếp tục')),
      Expanded(child: chat()),
    ])));
  Future<void> openConversation(Map<String, dynamic> item) async {
    await voice.stop();
    await guard(() async {
      final result = <Map<String, String>>[];
      dynamic cursor;
      do {
        final page = await api.post('/api/conversations/get', {
          'conversation_id': item['id'], 'after_id': cursor ?? 0});
        for (final m in page['messages'] as List<dynamic>) {
          result.add({'role': m['role'] as String, 'content': m['content'] as String});
        }
        cursor = page['next_after_id'];
      } while (cursor != null);
      changed(() { conversation = item['id'] as String; messages = result; tab = 0; });
    });
  }
  Future<void> topUp(int amount) async {
    // Keep the same ID after a timeout; never silently create a second order.
    if (paymentRequest != null && requestedAmount != amount) {
      throw ApiException('Đơn trước chưa rõ kết quả. Thử lại đúng số tiền $requestedAmount đ để kiểm tra đơn đó.');
    }
    paymentRequest ??= uuid.v4();
    requestedAmount = amount;
    final result = await api.post('/api/billing/order', {
      'kind': 'topup', 'amount': amount, 'request_id': paymentRequest});
    changed(() => order = result);
    pollSeconds = 10; schedulePoll();
  }
  void schedulePoll() {
    poll?.cancel();
    if (order != null && mounted && foreground) {
      poll = Timer(Duration(seconds: pollSeconds), checkPayment);
    }
  }
  Future<void> checkPayment() async {
    if (pollBusy || order == null) return;
    final current = order!['order'] as Map<String, dynamic>;
    if (DateTime.now().millisecondsSinceEpoch >= (current['expires'] as num)) {
      changed(() { order = null; paymentRequest = null; requestedAmount = null; error = 'QR đã hết hạn. Hãy tạo mã mới.'; });
      return;
    }
    pollBusy = true;
    try {
      final result = await api.post('/api/billing/order/status', {'order_id': current['id']});
      if (!mounted || (order?['order'] as Map<String, dynamic>?)?['id'] != current['id']) return;
      if ((result['order_status'] as Map<String, dynamic>)['status'] == 'paid') {
        changed(() { order = null; paymentRequest = null; requestedAmount = null; error = 'Thanh toán thành công.'; });
        await refresh();
      } else if ((result['order_status'] as Map<String, dynamic>)['status'] != 'pending') {
        changed(() { order = null; paymentRequest = null; requestedAmount = null; error = 'Đơn nạp đã hết hiệu lực.'; });
      } else { pollSeconds = 10; }
    } catch (e) {
      pollSeconds = (pollSeconds * 2).clamp(10, 60).toInt();
      changed(() => error = 'Chưa kiểm tra được thanh toán: $e');
    } finally { pollBusy = false; schedulePoll(); }
  }
  Future<void> editMemory() async {
    final title = TextEditingController(), text = TextEditingController();
    final save = await showDialog<bool>(context: context, builder: (c) => AlertDialog(
      title: const Text('Thêm ghi nhớ'), content: SingleChildScrollView(child: Column(
        mainAxisSize: MainAxisSize.min, children: [
        TextField(controller: title, maxLength: 120, decoration: const InputDecoration(labelText: 'Tiêu đề')),
        TextField(controller: text, maxLength: 4000, maxLines: 5, decoration: const InputDecoration(labelText: 'Nội dung')),
      ])), actions: [TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Hủy')),
        FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Lưu'))]));
    if (save == true) {
      await guard(() async {
        await api.post('/api/memory/personal/put', {'id': uuid.v4(), 'title': title.text,
          'text': text.text, 'confirm': true}); await refresh();
      });
    }
    // Dialog controllers are retained until the closing animation finishes.
  }
  Widget chat() => Column(children: [
    Padding(padding: const EdgeInsets.symmetric(horizontal: 16), child: Row(children: [
      const Text('AI trực tuyến'), const SizedBox(width: 16),
      DropdownButton<String>(value: provider, items: const [
        DropdownMenuItem(value: 'nvidia', child: Text('NVIDIA · Miễn phí')),
        DropdownMenuItem(value: 'deepseek_flash', child: Text('DeepSeek · Tính phí token')),
      ], onChanged: sending || api.session == null ? null : (v) => changed(() => provider = v!)),
    ])),
    Expanded(child: messages.isEmpty ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
      Image.asset('assets/chat_ai.png', width: 80, height: 80, semanticLabel: 'Logo ChatAI'),
      const SizedBox(height: 16), const Text('Xin chào! Tôi có thể giúp gì cho bạn?'),
    ])) :
      ListView.builder(itemCount: messages.length, itemBuilder: (c, i) {
        final m = messages[i];
        return Align(alignment: m['role'] == 'user' ? Alignment.centerRight : Alignment.centerLeft,
          child: Container(margin: const EdgeInsets.all(12), padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: m['role'] == 'user' ? const Color(0xff39354b) : const Color(0xff292929),
              borderRadius: BorderRadius.circular(16)), child: Column(
              mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              SelectableText(m['content']!),
              if (m['role'] == 'assistant') TextButton.icon(
                onPressed: () => readMessage(i),
                icon: Icon(readingMessage == i && voice.speaking ? Icons.stop : Icons.volume_up_outlined),
                label: Text(readingMessage == i && voice.speaking ? 'Dừng đọc' : 'Đọc câu trả lời')),
            ])));
      })),
    if (sending) const LinearProgressIndicator(),
    if (voice.listening || voice.starting) Padding(padding: const EdgeInsets.all(8),
      child: Text(voice.starting ? 'Đang mở micro…' : 'Đang nghe tiếng Việt… Bấm micro để dừng.')),
    Padding(padding: const EdgeInsets.all(12), child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
      Expanded(child: TextField(controller: input, minLines: 1, maxLines: 5,
        maxLength: 12000, decoration: const InputDecoration(hintText: 'Hỏi Chat AI…', border: OutlineInputBorder()))),
      IconButton(tooltip: voice.listening || voice.starting ? 'Dừng nghe' : 'Nhập bằng giọng nói',
        onPressed: sending || working ? null : dictate,
        icon: Icon(voice.listening || voice.starting ? Icons.mic_off : Icons.mic_none),
        color: voice.listening ? Colors.redAccent : null),
      IconButton.filled(onPressed: sending || working || voice.starting ? null : send, icon: const Icon(Icons.send)),
    ])),
  ]);
  Widget account() {
    final wallet = billing?['wallet'] as Map<String, dynamic>?;
    return ListView(padding: const EdgeInsets.all(16), children: [
      Text(api.session!.fullname, style: Theme.of(context).textTheme.headlineSmall),
      Text(api.session!.username), const SizedBox(height: 20),
      ListTile(leading: const Icon(Icons.notifications_active_outlined), title: const Text('Bật thông báo điện thoại'),
        subtitle: const Text('Kiểm tra nền khoảng 15 phút/lần; có thể chậm khi tiết kiệm pin'),
        onTap: working ? null : () => guard(() async {
          final allowed = await enableAccountNotifications(api);
          changed(() => error = allowed ? 'Đã bật thông báo. Bạn có thể quản lý quyền trong Cài đặt Android.' : 'Chưa được cấp quyền. Bật Thông báo trong Cài đặt Android nếu muốn nhận.');
        })),
      TextButton(onPressed: working ? null : () => guard(() async { await disableAccountNotifications(api); changed(() => error = 'Đã tắt thông báo điện thoại.'); }), child: const Text('Tắt thông báo điện thoại')),
      if (api.session!.admin) ListTile(leading: const Icon(Icons.admin_panel_settings),
        title: const Text('Quản trị'), subtitle: const Text('Người dùng · token · thông báo · thanh toán'),
        onTap: () async {
          await voice.stop();
          if (!mounted) return;
          await Navigator.push<void>(context, MaterialPageRoute(builder: (_) => AdminPage(api: api)));
        }),
      Text('Số dư: ${wallet == null ? 'Chưa tải được' : money(wallet['balance_vnd'] as num)}',
        style: Theme.of(context).textTheme.titleLarge),
      Text('Khả dụng: ${money((wallet?['available_vnd'] as num?) ?? 0)}'),
      Text('Phí duy trì: ${money((billing?['service_fee'] as num?) ?? 0)}/30 ngày'),
      Text('DeepSeek: ${money((billing?['price_per_million'] as num?) ?? 4000)}/triệu token'),
      for (final m in billing?['monthly_usage'] as List<dynamic>? ?? [])
        ListTile(title: Text('Tháng ${m['month']}'), subtitle: Text('${m['tokens']} token · ${money(m['fee_vnd'] as num)}')),
      if (!api.session!.admin && order == null) ...[
        const SizedBox(height: 12), const Text('Nạp token · tối thiểu 20.000 đ'),
        TextField(controller: amount, keyboardType: TextInputType.number,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          decoration: const InputDecoration(labelText: 'Số tiền', helperText: '20.000–10.000.000 đ, bội số 1.000 đ')),
        FilledButton(onPressed: working ? null : () => guard(() async {
          final value = int.tryParse(amount.text) ?? 0;
          if (value < 20000 || value > 10000000 || value % 1000 != 0) throw ApiException('Số tiền không hợp lệ.');
          await topUp(value);
        }), child: const Text('Tạo QR nạp token')),
      ],
      if (order != null) ...[
        Image.network(order!['qr_url'] as String, height: 280,
          errorBuilder: (_, _, _) => const Text('Không tải được ảnh QR. Dùng thông tin chuyển khoản bên dưới.')),
        SelectableText('${order!['bank']} · ${order!['account']} · ${order!['name']}\n'
          'Số tiền: ${money(order!['order']['amount'] as num)}\nNội dung: ${order!['order']['memo']}'),
        const Text('Đang chờ xác nhận tự động. Chuyển đúng số tiền và nội dung.'),
      ],
      OutlinedButton(onPressed: working ? null : () => guard(refresh), child: const Text('Làm mới')),
      OutlinedButton(onPressed: working || sending ? null : () => guard(signOut), child: const Text('Đăng xuất')),
    ]);
  }
  @override
  Widget build(BuildContext context) {
    if (loading) return const StartupScreen();
    if (api.session == null) return guestChat();
    return Scaffold(appBar: AppBar(title: const Text('Chat AI'), actions: [
      IconButton(tooltip: 'Cuộc trò chuyện mới', onPressed: sending ? null : () async {
        await voice.stop(); changed(() { messages = []; conversation = null; tab = 0; }); }, icon: const Icon(Icons.add_comment_outlined)),
    ]), body: SafeArea(child: Column(children: [
      if (error != null) MaterialBanner(content: Text(error!), actions: [
        TextButton(onPressed: () => changed(() => error = null), child: const Text('Đóng'))]),
      if (working) const LinearProgressIndicator(),
      Expanded(child: tab == 4 ? ComputerPage(key: ValueKey(api.session!.username), api: api, mobileId: device) : [chat(), ListView(children: [
        ListTile(title: const Text('Hội thoại trên server'), trailing: IconButton(
          onPressed: working || sending ? null : () => guard(refresh), icon: const Icon(Icons.refresh))),
        for (final item in conversations) ListTile(title: Text(item['title'] as String),
          onTap: sending ? null : () => openConversation(item as Map<String, dynamic>)),
        const Padding(padding: EdgeInsets.all(16), child: Text('Bản đầu tiên hiển thị hội thoại Android. '
          'Hội thoại desktop dùng kho đồng bộ riêng; chưa hiển thị ở đây.')),
      ]), ListView(children: [
        ListTile(title: const Text('Bộ nhớ cá nhân'), trailing: IconButton(
          onPressed: working ? null : editMemory, icon: const Icon(Icons.add))),
        for (final m in memories) ListTile(title: Text(m['title'] as String), subtitle: Text(m['text'] as String)),
        const Divider(), const ListTile(title: Text('Thông báo')),
        for (final n in notifications) ListTile(title: Text(n['title'] as String), subtitle: Text(n['text'] as String)),
      ]), account()][tab]),
    ])), bottomNavigationBar: NavigationBar(selectedIndex: tab,
      onDestinationSelected: (i) {
        if (i != tab) unawaited(voice.stop());
        changed(() => tab = i);
      }, destinations: const [
        NavigationDestination(icon: Icon(Icons.chat_bubble_outline), label: 'Chat'),
        NavigationDestination(icon: Icon(Icons.history), label: 'Hội thoại'),
        NavigationDestination(icon: Icon(Icons.memory), label: 'Bộ nhớ'),
        NavigationDestination(icon: Icon(Icons.person_outline), label: 'Tài khoản'),
        NavigationDestination(icon: Icon(Icons.computer), label: 'Máy tính'),
      ]));
  }
}

class LoginPage extends StatefulWidget {
  final ChatApi api;
  final String device;
  final Future<void> Function(Session) onLogin;
  const LoginPage({super.key, required this.api, required this.device, required this.onLogin});
  @override
  State<LoginPage> createState() => _LoginPageState();
}
class _LoginPageState extends State<LoginPage> {
  final name = TextEditingController(), password = TextEditingController();
  final fullname = TextEditingController(), email = TextEditingController();
  bool register = false, busy = false;
  String? error;
  @override
  void dispose() { for (final c in [name, password, fullname, email]) { c.dispose(); } super.dispose(); }
  Future<void> submit() async {
    if (busy) return;
    setState(() { busy = true; error = null; });
    try {
      if (name.text.trim().isEmpty || password.text.isEmpty) throw ApiException('Nhập tài khoản và mật khẩu.');
      if (register) {
        await widget.api.register(name.text, password.text, fullname.text, email.text, widget.device);
      } else { await widget.api.login(name.text, password.text, widget.device); }
      await widget.onLogin(widget.api.session!);
    } catch (e) { if (mounted) setState(() => error = '$e'); }
    finally { if (mounted) setState(() => busy = false); }
  }
  @override
  Widget build(BuildContext context) => Scaffold(body: SafeArea(child: Center(
    child: SingleChildScrollView(padding: const EdgeInsets.all(24), child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 440), child: Column(children: [
        Image.asset('assets/chat_ai.png', width: 80, height: 80, semanticLabel: 'Logo ChatAI'),
        const SizedBox(height: 16),
        Text(register ? 'Đăng ký Chat AI' : 'Đăng nhập Chat AI', style: Theme.of(context).textTheme.headlineSmall),
        const Text('AI trực tuyến · NVIDIA mặc định'), const SizedBox(height: 24),
        TextField(controller: name, decoration: const InputDecoration(labelText: 'Email hoặc tên đăng nhập')),
        if (register) ...[
          TextField(controller: fullname, decoration: const InputDecoration(labelText: 'Họ và tên')),
          TextField(controller: email, keyboardType: TextInputType.emailAddress,
            decoration: const InputDecoration(labelText: 'Email bắt buộc')),
        ],
        TextField(controller: password, obscureText: true, autocorrect: false, enableSuggestions: false,
          onSubmitted: (_) => submit(), decoration: const InputDecoration(labelText: 'Mật khẩu')),
        if (error != null) Padding(padding: const EdgeInsets.all(12), child: Text(error!)),
        const SizedBox(height: 24),
        FilledButton(onPressed: busy ? null : submit,
          child: Text(busy ? 'Đang xử lý…' : register ? 'Đăng ký và đăng nhập' : 'Đăng nhập')),
        TextButton(onPressed: busy ? null : () => setState(() => register = !register),
          child: Text(register ? 'Đã có tài khoản? Đăng nhập' : 'Tạo tài khoản')),
      ]))))));
}

import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:uuid/uuid.dart';
import 'api.dart';
import 'voice.dart';

class ComputerPage extends StatefulWidget {
  final ChatApi api;
  final String mobileId;
  const ComputerPage({super.key, required this.api, required this.mobileId});
  @override
  State<ComputerPage> createState() => _ComputerPageState();
}
class _ComputerPageState extends State<ComputerPage> with WidgetsBindingObserver {
  static const vault = FlutterSecureStorage();
  static const uuid = Uuid();
  final prompt = TextEditingController();
  final voice = VoiceController();
  Map<String, dynamic>? link, desktop;
  List<dynamic> tasks = [];
  bool busy = false, active = true;
  String? error, requestId, pairId;
  String? requestText, captureId;
  Uint8List? screenImage;
  DateTime? screenExpires;
  Timer? timer;
  int delay = 10;
  late final String owner;
  late final String storageKey;
  @override
  void initState() {
    super.initState(); owner = widget.api.session!.username;
    storageKey = 'computer:${widget.api.server.origin}:$owner';
    WidgetsBinding.instance.addObserver(this);
    voice.addListener(voiceChanged); restore();
  }
  void changed(VoidCallback fn) { if (mounted) setState(fn); }
  void voiceChanged() => changed(() { if (voice.error != null) error = voice.error; });
  @override
  void dispose() {
    active = false; WidgetsBinding.instance.removeObserver(this); timer?.cancel();
    voice.removeListener(voiceChanged); voice.dispose(); prompt.dispose(); super.dispose();
  }
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive) return;
    active = state == AppLifecycleState.resumed;
    if (!active) { timer?.cancel(); unawaited(voice.stop()); }
    else {
      if (screenExpires != null && DateTime.now().isAfter(screenExpires!)) {
        changed(() { screenImage = null; screenExpires = null; });
      }
      schedule();
    }
  }
  Future<void> restore() async {
    try {
      final raw = await vault.read(key: storageKey);
      if (raw != null) changed(() {
        link = jsonDecode(raw) as Map<String, dynamic>;
        pairId = link!['pending_pair_id'] as String?;
        requestId = link!['pending_task_id'] as String?;
        requestText = link!['pending_task_text'] as String?;
        if (requestText != null) prompt.text = requestText!;
      });
      if (link != null) await refresh();
    } catch (e) { changed(() => error = '$e'); }
  }
  Map<String, dynamic> credentials() => {'mobile_id': widget.mobileId,
    'desktop_id': link!['desktop_id'], 'mobile_secret': link!['mobile_secret']};
  void schedule() {
    timer?.cancel();
    if (mounted && active && link != null) {
      timer = Timer(Duration(seconds: delay), refresh);
    }
  }
  Future<void> refresh() async {
    if (!mounted || !active || widget.api.session?.username != owner) return;
    if (busy || link == null) { schedule(); return; }
    busy = true;
    try {
      if (pairId != null) {
        final pair = await widget.api.post('/api/remote/pair/status', {...credentials(), 'pair_id': pairId});
        if (pair['state'] == 'approved') {
          pairId = null; link!.remove('pending_pair_id');
          await vault.write(key: storageKey, value: jsonEncode(link));
        } else if (pair['state'] != 'waiting') {
          await vault.delete(key: storageKey);
          changed(() { link = null; pairId = null; });
          throw ApiException('Ghép nối ${pair['state']}. Tạo QR mới trên máy tính.');
        } else { return; }
      }
      final result = await widget.api.post('/api/remote/mobile/status', credentials());
      changed(() { desktop = result['desktop'] as Map<String, dynamic>;
        tasks = result['tasks'] as List<dynamic>; });
      if (screenExpires != null && DateTime.now().isAfter(screenExpires!)) {
        changed(() { screenImage = null; screenExpires = null; });
      }
      if (captureId != null) {
        final capture = await widget.api.post('/api/remote/mobile/capture/get', {...credentials(), 'capture_id': captureId});
        if (capture['state'] == 'ready') {
          final bytes = base64Decode(capture['image'] as String);
          changed(() { screenImage = bytes; screenExpires = DateTime.fromMillisecondsSinceEpoch(capture['expires'] as int); });
          captureId = null;
        } else if (['denied', 'expired'].contains(capture['state'])) {
          changed(() => error = capture['message'] as String? ?? 'Yêu cầu ảnh hết hạn.'); captureId = null;
        }
      }
      delay = 10;
    } catch (e) {
      changed(() => error = '$e'); delay = (delay * 2).clamp(10, 60).toInt();
      if (e is ApiException && e.status == 403) { timer?.cancel(); active = false; }
    } finally { busy = false; schedule(); }
  }
  Future<void> action(Future<void> Function() fn) async {
    if (busy || !mounted || widget.api.session?.username != owner) return;
    changed(() { busy = true; error = null; });
    try { await fn(); }
    catch (e) { changed(() => error = '$e'); }
    finally { changed(() => busy = false); schedule(); }
  }
  Future<void> pair(String raw) async {
    final qr = jsonDecode(raw) as Map<String, dynamic>;
    if (qr['kind'] != 'chatai_pair' || qr['version'] != 1 || qr['server'] != widget.api.server.origin) {
      throw ApiException('QR không thuộc server ChatAI đang đăng nhập.');
    }
    final secret = '${uuid.v4()}${uuid.v4()}'.replaceAll('-', '');
    final proposed = {'desktop_id': qr['desktop_id'], 'mobile_secret': secret};
    final result = await widget.api.post('/api/remote/pair/request', {
      ...proposed, 'mobile_id': widget.mobileId, 'code': qr['code'], 'name': 'ChatAI Android'});
    proposed['pending_pair_id'] = result['pair_id'];
    await vault.write(key: storageKey, value: jsonEncode(proposed));
    changed(() { link = proposed; pairId = result['pair_id'] as String;
      desktop = null; tasks = []; screenImage = null; screenExpires = null; captureId = null; active = true; delay = 10; });
  }
  Future<void> scan() async {
    await voice.stop();
    if (!mounted) return;
    final raw = await Navigator.push<String>(context, MaterialPageRoute(builder: (_) => const PairScanner()));
    if (raw != null) await action(() => pair(raw));
  }
  Future<void> paste() async {
    final field = TextEditingController();
    final raw = await showDialog<String>(context: context, builder: (c) => AlertDialog(
      title: const Text('Dán mã ghép nối từ Windows'),
      content: TextField(controller: field, maxLines: 5), actions: [
        TextButton(onPressed: () => Navigator.pop(c), child: const Text('Hủy')),
        FilledButton(onPressed: () => Navigator.pop(c, field.text.trim()), child: const Text('Ghép nối'))]));
    if (raw != null && raw.isNotEmpty) await action(() => pair(raw));
  }
  Future<void> send() async {
    final text = prompt.text.trim();
    if (text.isEmpty || pairId != null || desktop == null || link == null) return;
    await voice.stop();
    await action(() async {
      if (requestId != null && requestText != text) throw ApiException('Yêu cầu trước chưa rõ kết quả. Thử lại cùng nội dung để tránh chạy trùng.');
      requestId ??= uuid.v4(); requestText = text;
      link!['pending_task_id'] = requestId; link!['pending_task_text'] = requestText;
      await vault.write(key: storageKey, value: jsonEncode(link));
      await widget.api.post('/api/remote/mobile/send', {...credentials(), 'task_id': requestId, 'prompt': text});
      link!.remove('pending_task_id'); link!.remove('pending_task_text');
      await vault.write(key: storageKey, value: jsonEncode(link));
      requestId = null; requestText = null; prompt.clear();
      error = 'Đã gửi. Máy tính sẽ nhận khi ChatAI đang mở và cho phép nhận việc.';
    });
    await refresh();
  }
  Future<void> control(Map<String, dynamic> task, String command) async {
    String text = '';
    if (command == 'reply') {
      final field = TextEditingController();
      final reply = await showDialog<String>(context: context, builder: (c) => AlertDialog(
        title: const Text('Bổ sung cho AI'), content: TextField(controller: field, maxLines: 4),
        actions: [TextButton(onPressed: () => Navigator.pop(c), child: const Text('Hủy')),
          FilledButton(onPressed: () => Navigator.pop(c, field.text.trim()), child: const Text('Gửi'))]));
      if (reply == null || reply.isEmpty) return;
      text = reply;
    }
    await action(() async {
      await widget.api.post('/api/remote/mobile/control', {...credentials(),
        'task_id': task['id'], 'action': command, 'text': text});
    });
    await refresh();
  }
  Future<void> requestScreen() async {
    await action(() async {
      captureId ??= uuid.v4();
      await widget.api.post('/api/remote/mobile/capture/request', {...credentials(), 'capture_id': captureId});
      changed(() => screenImage = null);
    });
    await refresh();
  }
  Future<void> dictate() async {
    if (voice.listening || voice.starting) { await voice.stop(); return; }
    final original = prompt.text.trimRight();
    await voice.start((words) {
      final text = original.isEmpty ? words : '$original $words';
      prompt.value = TextEditingValue(text: text, selection: TextSelection.collapsed(offset: text.length));
    });
  }
  String stateName(String state) => const {'queued': 'Chờ máy tính', 'claimed': 'Máy đã nhận',
    'running': 'Đang thực hiện', 'paused': 'Đã tạm dừng', 'needs_input': 'Cần trợ giúp',
    'completed': 'Đã kết thúc', 'failed': 'Có lỗi', 'cancelled': 'Đã hủy'}[state] ?? state;
  @override
  Widget build(BuildContext context) => ListView(padding: const EdgeInsets.all(16), children: [
    Row(children: [Expanded(child: Text(desktop?['name'] as String? ?? 'Kết nối máy tính',
      style: Theme.of(context).textTheme.titleLarge)),
      IconButton(onPressed: busy ? null : refresh, tooltip: 'Làm mới', icon: const Icon(Icons.refresh))]),
    Text(desktop == null ? pairId == null ? 'Mở ChatAI Windows → Tài khoản → Kết nối điện thoại.' :
      'Chờ Windows xác nhận tên điện thoại.' :
      '${desktop!['online'] == true ? 'Online' : 'Offline'} · ${desktop!['enabled'] == true ? 'Cho phép nhận việc' : 'Đã ngừng nhận việc'}'),
    Text('Mã điện thoại: ${widget.mobileId.substring(0, 8)} · đối chiếu trên Windows khi xác nhận'),
    Wrap(spacing: 8, children: [
      OutlinedButton.icon(onPressed: busy ? null : scan, icon: const Icon(Icons.qr_code_scanner), label: const Text('Quét QR')),
      TextButton(onPressed: busy ? null : paste, child: const Text('Dán mã')),
    ]),
    if (busy) const LinearProgressIndicator(),
    if (error != null) Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Text(error!)),
    if (desktop != null && pairId == null) ...[
      OutlinedButton.icon(onPressed: busy ? null : requestScreen, icon: const Icon(Icons.screenshot_monitor),
        label: Text(captureId == null ? 'Yêu cầu ảnh màn hình' : 'Chờ ảnh · thử lại')) ,
      if (screenImage != null) ...[
        const Text('Ảnh màn hình vừa yêu cầu · hết hạn sau 5 phút'),
        InteractiveViewer(maxScale: 5, child: Image.memory(screenImage!, gaplessPlayback: false)),
        TextButton(onPressed: () => changed(() { screenImage = null; screenExpires = null; }), child: const Text('Ẩn ảnh')),
      ],
      const SizedBox(height: 16),
      TextField(controller: prompt, minLines: 2, maxLines: 6, maxLength: 12000,
        decoration: const InputDecoration(labelText: 'Giao việc cho máy tính',
          hintText: 'Đọc Excel và DXF trong thư mục đã cấp, chạy GeoStudio…', border: OutlineInputBorder())),
      Row(children: [IconButton(onPressed: busy ? null : dictate,
        tooltip: voice.listening ? 'Dừng nghe' : 'Nói lệnh', icon: Icon(voice.listening ? Icons.mic_off : Icons.mic_none)),
        FilledButton.icon(onPressed: busy ? null : send, icon: const Icon(Icons.send), label: const Text('Gửi việc'))]),
      if (voice.listening) const Text('Đang nghe tiếng Việt…'),
    ],
    for (final row in tasks) Card(child: Padding(padding: const EdgeInsets.all(12), child: Column(
      crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(stateName(row['state'] as String), style: Theme.of(context).textTheme.titleMedium),
      Text(row['prompt'] as String),
      if (row['connection_lost'] == true) const Text('Máy mất kết nối; chưa xác minh kết quả. Không tự chạy lại.'),
      if ((row['progress'] as String).isNotEmpty) Text(row['progress'] as String),
      if (row['command'] != null) const Text('Đã gửi điều khiển, chờ máy tính xác nhận.'),
      if ((row['result'] as String).isNotEmpty) ...[
        SelectableText(row['result'] as String),
        TextButton.icon(onPressed: () => voice.speaking ? voice.stop() : voice.read(row['result'] as String),
          icon: Icon(voice.speaking ? Icons.stop : Icons.volume_up_outlined),
          label: Text(voice.speaking ? 'Dừng đọc' : 'Đọc kết quả')),
      ],
      if (!['completed', 'failed', 'cancelled'].contains(row['state'])) Wrap(spacing: 8, children: [
        if (['running', 'claimed'].contains(row['state'])) TextButton(onPressed: busy ? null : () => control(row as Map<String, dynamic>, 'pause'), child: const Text('Tạm dừng')),
        if (['paused', 'needs_input'].contains(row['state'])) TextButton(onPressed: busy ? null : () => control(row as Map<String, dynamic>, 'resume'), child: const Text('Tiếp tục')),
        if (row['state'] == 'needs_input') TextButton(onPressed: busy ? null : () => control(row as Map<String, dynamic>, 'reply'), child: const Text('Bổ sung')),
        TextButton(onPressed: busy ? null : () => control(row as Map<String, dynamic>, 'cancel'), child: const Text('Hủy tác vụ')),
      ]),
    ]))),
  ]);
}
class PairScanner extends StatefulWidget {
  const PairScanner({super.key});
  @override
  State<PairScanner> createState() => _PairScannerState();
}
class _PairScannerState extends State<PairScanner> {
  bool returned = false;
  @override
  Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Quét QR trên máy tính')),
    body: MobileScanner(onDetect: (capture) {
      if (returned) return;
      for (final code in capture.barcodes) {
        if (code.rawValue != null) { returned = true; Navigator.pop(context, code.rawValue); break; }
      }
    }));
}

import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'api.dart';

class MediaPage extends StatefulWidget {
  final ChatApi api;
  final String initialPrompt;
  final bool initialVideo;
  const MediaPage({super.key, required this.api, this.initialPrompt = '', this.initialVideo = false});
  @override
  State<MediaPage> createState() => _MediaPageState();
}

class _MediaPageState extends State<MediaPage> {
  final prompt = TextEditingController();
  bool busy = false, video = false;
  String message = '', status = '', job = '';
  Uint8List? image;
  Map<String, dynamic>? capabilities;
  @override
  void initState() { super.initState(); prompt.text = widget.initialPrompt; video = widget.initialVideo; load(); }
  String get jobKey => 'media-job:${widget.api.server.origin}:${widget.api.session?.username}';
  Future<void> load() async {
    try {
      final saved = await const FlutterSecureStorage().read(key: jobKey);
      if (mounted && saved != null) setState(() { job = saved; status = 'unknown'; if (widget.initialPrompt.isEmpty) video = true; });
      final value = await widget.api.post('/api/media/capabilities', {}); if (mounted) setState(() => capabilities = value); }
    catch (e) { if (mounted) setState(() => message = '$e'); }
  }
  @override
  void dispose() { prompt.dispose(); super.dispose(); }
  Future<void> run(Future<void> Function() action) async {
    setState(() { busy = true; message = ''; });
    try { await action(); } catch (e) { if (mounted) setState(() => message = '$e'); }
    finally { if (mounted) setState(() => busy = false); }
  }
  Future<void> generate() async {
    final text = prompt.text.trim();
    if (text.isEmpty) return;
    final confirmed = await showDialog<bool>(context: context, builder: (context) => AlertDialog(
      title: const Text('Xác nhận tạo nội dung'),
      content: Text(video ? 'Tạo video Sora 4 giây có thể tính phí OpenAI. Không tự gửi lại nếu yêu cầu chưa xác nhận.' : 'Tạo ảnh dùng hạn mức Workers AI của server.'),
      actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Hủy')),
        FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Tạo'))]));
    if (confirmed != true || !mounted) return;
    await run(() async {
      if (!video) {
        final value = await widget.api.post('/api/media/image', {'prompt': text});
        final bytes = base64Decode(value['image'] as String);
        if (mounted) setState(() { image = bytes; message = 'Ảnh đã tạo xong.'; });
      } else {
        // Retain the request identifier across uncertain submissions.
        final id = const Uuid().v4();
        await const FlutterSecureStorage().write(key: jobKey, value: id);
        if (!mounted) return;
        setState(() { job = id; status = 'submitting'; });
        final value = await widget.api.post('/api/media/video/create', {'prompt': text, 'request_id': id});
        if (mounted) setState(() { status = value['status'] as String; });
      }
    });
  }
  Future<void> check() => run(() async {
    final value = await widget.api.post('/api/media/video/status', {'id': job});
    if (mounted) setState(() { status = value['status'] as String; message = 'Tiến độ: ${value['progress']}%'; });
  });
  Future<void> saveVideo() => run(() async {
    final session = widget.api.session!;
    final response = await widget.api.client.post(widget.api.server.resolve('/api/media/video/content'),
      headers: {'Content-Type': 'application/json'}, body: jsonEncode({'username': session.username, 'key': session.key, 'id': job})).timeout(const Duration(minutes: 3));
    if (response.statusCode != 200 || !(response.headers['content-type'] ?? '').startsWith('video/mp4')) {
      throw ApiException('Chưa tải được video. Kiểm tra trạng thái rồi thử lại.', response.statusCode);
    }
    final path = await FilePicker.platform.saveFile(dialogTitle: 'Lưu video', fileName: 'ChatAI.mp4', bytes: response.bodyBytes);
    if (mounted && path != null) setState(() => message = 'Đã lưu video. Mở bằng ứng dụng xem video trên điện thoại.');
  });
  @override
  Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Tạo ảnh và video')),
    body: ListView(padding: const EdgeInsets.all(16), children: [
      SegmentedButton<bool>(segments: const [ButtonSegment(value: false, label: Text('Ảnh')), ButtonSegment(value: true, label: Text('Video'))],
        selected: {video}, onSelectionChanged: busy ? null : (value) => setState(() { video = value.first; message = ''; })),
      const SizedBox(height: 16),
      Text(video ? 'Sora 2 · 4 giây · 720 × 1280. Cần OpenAI key có quyền tạo video trên server chính.' : 'FLUX Schnell · Workers AI trên server chính.'),
      if (capabilities != null && capabilities![video ? 'video_available' : 'image_available'] != true)
        const Text('Dịch vụ chưa được cấu hình. Liên hệ quản trị viên.'),
      TextField(controller: prompt, maxLength: 2000, minLines: 3, maxLines: 6, decoration: const InputDecoration(labelText: 'Mô tả nội dung muốn tạo')),
      FilledButton(onPressed: busy || capabilities?[video ? 'video_available' : 'image_available'] != true || (video && job.isNotEmpty && status != 'completed' && status != 'failed') ? null : generate,
        child: Text(video ? 'Tạo video' : 'Tạo ảnh')),
      if (busy) const LinearProgressIndicator(),
      if (message.isNotEmpty) SelectableText(message),
      if (video && job.isNotEmpty) ...[
        SelectableText('Mã yêu cầu: $job\nTrạng thái: $status'),
        OutlinedButton(onPressed: busy ? null : check, child: const Text('Kiểm tra tiến độ')),
        if (status == 'completed') FilledButton(onPressed: busy ? null : saveVideo, child: const Text('Lưu video MP4')),
      ],
      if (!video && image != null) ...[
        InkWell(onTap: () => Navigator.push<void>(context, MaterialPageRoute(builder: (_) => Scaffold(
          backgroundColor: Colors.black, appBar: AppBar(title: const Text('Ảnh đã tạo'), backgroundColor: Colors.black, foregroundColor: Colors.white),
          body: Center(child: InteractiveViewer(minScale: .5, maxScale: 5, child: Hero(tag: 'generated-image', child: Image.memory(image!, fit: BoxFit.contain))))))),
          child: Hero(tag: 'generated-image', child: ClipRRect(borderRadius: BorderRadius.circular(24), child: Image.memory(image!)))),
        OutlinedButton(onPressed: busy ? null : () => run(() async {
          final path = await FilePicker.platform.saveFile(dialogTitle: 'Lưu ảnh', fileName: 'ChatAI.jpg', bytes: image!);
          if (mounted && path != null) setState(() => message = 'Đã lưu ảnh.');
        }), child: const Text('Lưu ảnh')),
      ],
    ]));
}

import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'voice.dart';
import 'cloud_voice.dart';
import 'api.dart';
import 'voice_robot.dart';

/// Text-only conversation: never dispatches computer or payment operations.
class VoiceChatPage extends StatefulWidget {
  final ChatApi api;
  final Future<String> Function(String) answer;
  const VoiceChatPage({super.key, required this.answer, required this.api});
  @override
  State<VoiceChatPage> createState() => _VoiceChatPageState();
}
class _VoiceChatPageState extends State<VoiceChatPage> with WidgetsBindingObserver {
  late final VoiceController voice;
  String draft = '', response = '', phase = 'Sẵn sàng', failure = '';
  bool showContent = true;
  bool processing = false, paused = false, closed = false;
  int generation = 0;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    voice = VoiceController(engine: CloudVoiceEngine(widget.api))..addListener(changed);
    WidgetsBinding.instance.addPostFrameCallback((_) => listen());
  }
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive) return;
    if (state != AppLifecycleState.resumed) { paused = true; generation++; unawaited(voice.stop()); }
  }
  void changed() {
    if (!mounted || closed) return;
    setState(() {
      if (voice.error != null) { failure = voice.error!; paused = true; phase = 'Chưa mở được giọng nói'; }
      else if (!processing) { phase = voice.transcribing ? 'Đang nhận dạng…' : voice.starting ? 'Đang mở micro…' : voice.listening ? 'Đang nghe…' : paused ? 'Đã tạm dừng' : 'Sẵn sàng'; }
    });
    if (!voice.starting && !voice.transcribing && !voice.listening && !voice.speaking && !processing && !paused && draft.trim().isNotEmpty) {
      unawaited(reply());
    }
  }
  Future<void> listen() async {
    if (!mounted || closed || processing) return;
    setState(() { paused = false; draft = ''; failure = ''; phase = 'Đang mở micro…'; });
    await voice.start((words) { if (mounted && !closed) setState(() => draft = words); });
  }
  Future<void> reply() async {
    if (processing || closed || draft.trim().isEmpty) return;
    final question = draft.trim();
    final run = ++generation;
    setState(() { processing = true; phase = 'Đang suy nghĩ…'; });
    await voice.stop();
    try {
      final text = await widget.answer(question);
      if (!mounted || closed || run != generation) return;
      setState(() { response = text; showContent = true; phase = 'Đang trả lời…'; });
      await voice.read(text);
      if (!mounted || closed || run != generation) return;
      if (voice.error != null) { paused = true; failure = voice.error!; }
    } catch (e) { if (mounted && run == generation) { paused = true; failure = '$e'; } }
    finally {
      if (mounted && !closed && run == generation) {
        setState(() { processing = false; draft = ''; phase = failure.isEmpty ? 'Sẵn sàng' : 'Giọng nói tạm dừng'; });
        if (!paused) unawaited(listen());
      } else if (mounted) { setState(() => processing = false); }
    }
  }
  Future<void> pause() async {
    paused = true; generation++; await voice.stop();
    if (mounted) setState(() => phase = 'Đã tạm dừng');
  }
  @override
  void dispose() {
    closed = true; generation++; WidgetsBinding.instance.removeObserver(this);
    voice.removeListener(changed); voice.dispose(); super.dispose();
  }
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Trò chuyện giọng nói')),
    body: SafeArea(child: Column(children: [
      Expanded(child: LayoutBuilder(builder: (context, constraints) =>
        SingleChildScrollView(padding: const EdgeInsets.all(24), child: ConstrainedBox(
          constraints: BoxConstraints(minHeight: math.max(0.0, constraints.maxHeight - 48)),
          child: SizedBox(width: double.infinity, child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
        VoiceRobot(speaking: voice.speaking, listening: voice.listening,
          thinking: processing && !voice.speaking, paused: paused || failure.isNotEmpty),
        const SizedBox(height: 24), Text(phase, textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 20),
        TextButton(onPressed: () => setState(() => showContent = !showContent), child: Text(showContent ? 'Ẩn nội dung' : 'Xem nội dung')),
        if (showContent && draft.isNotEmpty) Text('Bạn: $draft', textAlign: TextAlign.center),
        if (voice.listening && !processing)
          FilledButton.icon(onPressed: voice.finishListening, icon: const Icon(Icons.send), label: const Text('Gửi câu nói')),
        if (!processing && !voice.listening && draft.trim().isNotEmpty)
          FilledButton.icon(onPressed: reply, icon: const Icon(Icons.send), label: const Text('Gửi câu nói')),
        if (voice.listening && draft.isEmpty && !processing)
          const Text('Hãy nói câu hỏi. Chữ nhận dạng sẽ hiện ở đây.', textAlign: TextAlign.center),
        if (showContent && response.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 20), child: SelectableText(response)),
        if (failure.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 20), child: Text(failure, style: TextStyle(color: Theme.of(context).colorScheme.error))),
        if (failure.isNotEmpty) Wrap(alignment: WrapAlignment.center, children: [
          TextButton(onPressed: processing ? null : listen, child: const Text('Thử lại')),
          TextButton(onPressed: () async {
            try { await pause(); await openVoiceSettings(false); }
            catch (e) { if (mounted) setState(() => failure = '$e'); }
          }, child: const Text('Cài đặt mic')),
          TextButton(onPressed: () async {
            try { await pause(); await openVoiceSettings(true); }
            catch (e) { if (mounted) setState(() => failure = '$e'); }
          }, child: const Text('Cài đặt giọng đọc')),
        ]),
      ])))))),
      Wrap(alignment: WrapAlignment.center, spacing: 8, children: [
        TextButton.icon(onPressed: processing && !voice.speaking ? null : paused ? listen : pause,
          icon: Icon(paused ? Icons.mic : Icons.mic_off), label: Text(paused ? 'Nói tiếp' : 'Tắt mic')),
        TextButton(onPressed: voice.speaking ? pause : null, child: const Text('Ngắt lời')),
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Kết thúc')),
      ]), const SizedBox(height: 16),
    ])),
  );
}

import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'voice.dart';

/// Text-only conversation: never dispatches computer or payment operations.
class VoiceChatPage extends StatefulWidget {
  final Future<String> Function(String) answer;
  const VoiceChatPage({super.key, required this.answer});
  @override
  State<VoiceChatPage> createState() => _VoiceChatPageState();
}
class _VoiceChatPageState extends State<VoiceChatPage> with WidgetsBindingObserver, SingleTickerProviderStateMixin {
  late final VoiceController voice;
  late final AnimationController pulse;
  String draft = '', response = '', phase = 'Sẵn sàng', failure = '';
  bool processing = false, paused = false, closed = false;
  int generation = 0;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    voice = VoiceController()..addListener(changed);
    pulse = AnimationController(vsync: this, duration: const Duration(seconds: 2))..repeat();
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
      if (voice.error != null) { failure = voice.error!; paused = true; }
    });
    if (!voice.starting && !voice.listening && !voice.speaking && !processing && !paused && draft.trim().isNotEmpty) {
      unawaited(reply());
    }
  }
  Future<void> listen() async {
    if (!mounted || closed || processing) return;
    setState(() { paused = false; draft = ''; failure = ''; phase = 'Đang nghe…'; });
    await voice.start((words) { if (mounted && !closed) setState(() => draft = words); });
  }
  Future<void> reply() async {
    if (processing || closed) return;
    final run = ++generation;
    setState(() { processing = true; phase = 'Đang suy nghĩ…'; });
    await voice.stop();
    try {
      final text = await widget.answer(draft);
      if (!mounted || closed || run != generation) return;
      setState(() { response = text; phase = 'Đang trả lời…'; });
      await voice.read(text);
      if (!mounted || closed || run != generation) return;
      if (voice.error != null) { paused = true; failure = voice.error!; }
    } catch (e) { if (mounted && run == generation) { paused = true; failure = '$e'; } }
    finally {
      if (mounted && !closed && run == generation) {
        setState(() { processing = false; draft = ''; phase = 'Sẵn sàng'; });
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
    voice.removeListener(changed); voice.dispose(); pulse.dispose(); super.dispose();
  }
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Trò chuyện giọng nói')),
    body: SafeArea(child: Column(children: [
      Expanded(child: SingleChildScrollView(padding: const EdgeInsets.all(24), child: Column(children: [
        const SizedBox(height: 32),
        AnimatedBuilder(animation: pulse, builder: (_, child) {
          final active = voice.listening || voice.speaking || processing;
          final wave = MediaQuery.disableAnimationsOf(context) || !active ? 0.0 : (math.sin(pulse.value * math.pi * 2) + 1) / 2;
          return Container(padding: const EdgeInsets.all(24), decoration: BoxDecoration(shape: BoxShape.circle,
            boxShadow: [BoxShadow(color: Theme.of(context).colorScheme.primary.withValues(alpha: .12 + wave * .2), blurRadius: 12 + wave * 28)]), child: child);
        }, child: Image.asset('assets/chat_ai.png', width: 112, height: 112)),
        const SizedBox(height: 24), Text(phase, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 20),
        if (draft.isNotEmpty) Text('Bạn: $draft'),
        if (response.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 20), child: SelectableText(response)),
        if (failure.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 20), child: Text(failure, style: TextStyle(color: Theme.of(context).colorScheme.error))),
        const SizedBox(height: 20), const Text('Giọng Android · hiệu ứng mô phỏng. Lời nói được gửi cho AI khi kết thúc lượt nghe.'),
      ]))),
      Wrap(alignment: WrapAlignment.center, spacing: 8, children: [
        TextButton.icon(onPressed: processing && !voice.speaking ? null : paused ? listen : pause,
          icon: Icon(paused ? Icons.mic : Icons.mic_off), label: Text(paused ? 'Nói tiếp' : 'Tắt mic')),
        TextButton(onPressed: voice.speaking ? pause : null, child: const Text('Dừng đọc')),
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Kết thúc')),
      ]), const SizedBox(height: 16),
    ])),
  );
}

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
  bool showContent = false;
  bool processing = false, paused = false, closed = false;
  int generation = 0;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    voice = VoiceController()..addListener(changed);
    pulse = AnimationController(vsync: this, duration: const Duration(seconds: 2));
    WidgetsBinding.instance.addPostFrameCallback((_) => listen());
  }
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) { pulse.stop(); }
    else { pulse.repeat(); }
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
      else if (!processing) { phase = voice.starting ? 'Đang mở micro…' : voice.listening ? 'Đang nghe…' : paused ? 'Đã tạm dừng' : 'Sẵn sàng'; }
    });
    if (!voice.starting && !voice.listening && !voice.speaking && !processing && !paused && draft.trim().isNotEmpty) {
      unawaited(reply());
    }
  }
  Future<void> listen() async {
    if (!mounted || closed || processing) return;
    setState(() { paused = false; draft = ''; failure = ''; phase = 'Đang mở micro…'; });
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
          final level = MediaQuery.disableAnimationsOf(context) ? 0.0 : voice.listening ? voice.soundLevel : voice.speaking ? wave : processing ? .35 : 0.0;
          return Transform.scale(scale: 1 + level * .08, child: Transform.rotate(
            angle: processing && !MediaQuery.disableAnimationsOf(context) ? pulse.value * math.pi * 2 : 0,
            child: Container(width: 180, height: 180, decoration: BoxDecoration(shape: BoxShape.circle,
              gradient: const RadialGradient(center: Alignment(-.35, -.4), colors: [Color(0xffa7f3ff), Color(0xff1bbfff), Color(0xff6547ff), Color(0xff382481)]),
              boxShadow: [BoxShadow(color: const Color(0xff635bff).withValues(alpha: .18 + level * .25), blurRadius: 24 + level * 32, spreadRadius: level * 8)],
              border: Border.all(color: Colors.white.withValues(alpha: .25), width: 2)))));
        }),
        const SizedBox(height: 24), Text(phase, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 20),
        TextButton(onPressed: () => setState(() => showContent = !showContent), child: Text(showContent ? 'Ẩn nội dung' : 'Xem nội dung')),
        if (showContent && draft.isNotEmpty) Text('Bạn: $draft'),
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
      ]))),
      Wrap(alignment: WrapAlignment.center, spacing: 8, children: [
        TextButton.icon(onPressed: processing && !voice.speaking ? null : paused ? listen : pause,
          icon: Icon(paused ? Icons.mic : Icons.mic_off), label: Text(paused ? 'Nói tiếp' : 'Tắt mic')),
        TextButton(onPressed: voice.speaking ? pause : null, child: const Text('Ngắt lời')),
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Kết thúc')),
      ]), const SizedBox(height: 16),
    ])),
  );
}

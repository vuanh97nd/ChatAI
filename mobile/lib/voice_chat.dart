import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'voice.dart';
import 'streaming_speech.dart';
import 'cloud_voice.dart';
import 'api.dart';
import 'voice_robot.dart';
import 'voice_wave.dart';
import 'visual_style.dart';
import 'sound_effects.dart';
import 'package:flutter/cupertino.dart';

/// Text-only conversation: never dispatches computer or payment operations.
class VoiceChatPage extends StatefulWidget {
  final ChatApi api;
  final Future<String> Function(String)? answer;
  final Future<String> Function(String, void Function(String))? answerStream;
  const VoiceChatPage({super.key, this.answer, this.answerStream, required this.api}) : assert(answer != null || answerStream != null);
  @override
  State<VoiceChatPage> createState() => _VoiceChatPageState();
}
class _VoiceChatPageState extends State<VoiceChatPage> with WidgetsBindingObserver {
  late final VoiceController voice;
  String draft = '', response = '', phase = 'Sẵn sàng', failure = '';
  String speechMode = 'Giọng AI trực tuyến';
  bool showContent = true;
  String selectedVoice = 'auto';
  String recognitionMode = 'Đang chọn bộ nhận dạng…';
  bool processing = false, paused = false, closed = false;
  int generation = 0;
  bool startCuePlayed = false;
  StreamingSpeech? speechQueue;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    voice = VoiceController(engine: CloudVoiceEngine(widget.api, onRecognitionMode: (value) { if (mounted && !closed) setState(() => recognitionMode = value); }, onSpeechMode: (value) {
      if (mounted && !closed) setState(() => speechMode = value);
    }))..addListener(changed);
    WidgetsBinding.instance.addPostFrameCallback((_) => listen());
  }
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive) return;
    if (state != AppLifecycleState.resumed) { paused = true; generation++; speechQueue?.cancel(); unawaited(voice.stop()); }
  }
  void changed() {
    if (!mounted || closed) return;
    SoundEffects.microphoneActive = voice.starting || voice.listening || voice.transcribing;
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
    final cueNeeded=!startCuePlayed||paused;
    setState(() { paused = false; draft = ''; failure = ''; phase = 'Đang mở micro…'; });
    if(cueNeeded){startCuePlayed=true;await SoundEffects.play(AppSound.listening,voiceBoundary:true);await Future<void>.delayed(const Duration(milliseconds:220));}
    if(!mounted||closed||paused)return;
    await voice.start((words) { if (mounted && !closed) setState(() => draft = words); });
  }
  Future<void> reply() async {
    if (processing || closed || draft.trim().isEmpty) return;
    final question = draft.trim();
    final run = ++generation;
    setState(() { processing = true; phase = 'Đang suy nghĩ…'; });
    await voice.stop();
    try {
      final queue = StreamingSpeech((part) async {
        if (!mounted || closed || paused || run != generation) return;
        setState(() => phase = 'Đang trả lời…');
        await voice.read(part);
        if (voice.error != null) throw Exception(voice.error);
      });
      speechQueue = queue;
      void progress(String text) {
        if (!mounted || closed || run != generation) return;
        setState(() { response = text; showContent = true; });
        queue.add(text);
      }
      final text = widget.answerStream != null ? await widget.answerStream!(question, progress) : await widget.answer!(question);
      if (!mounted || closed || run != generation) { queue.cancel(); return; }
      setState(() { response = text; showContent = true; });
      await queue.finish(text);
      if (!mounted || closed || run != generation) return;
      if (voice.error != null) { paused = true; failure = voice.error!; }
    } catch (e) { speechQueue?.cancel(); await voice.stop(); if (mounted && run == generation) { paused = true; failure = '$e'; } }
    finally {
      if (mounted && !closed && run == generation) {
        setState(() { processing = false; draft = ''; phase = failure.isEmpty ? 'Sẵn sàng' : 'Giọng nói tạm dừng'; });
        if (!paused) unawaited(listen());
      } else if (mounted) { setState(() => processing = false); }
    }
  }
  Future<void> pause() async {
    paused = true; generation++; speechQueue?.cancel(); await voice.stop();
    if (mounted) setState(() => phase = 'Đã tạm dừng');
  }
  @override
  void dispose() {
    closed = true; speechQueue?.cancel(); SoundEffects.microphoneActive=false; generation++; WidgetsBinding.instance.removeObserver(this);
    voice.removeListener(changed); voice.dispose(); super.dispose();
  }
  Widget voiceControl(IconData icon,String label,VoidCallback? action,{bool destructive=false}) => Column(mainAxisSize:MainAxisSize.min,children:[
    IconButton(tooltip:label,onPressed:action,icon:Icon(icon,size:25),style:IconButton.styleFrom(
      minimumSize:const Size(62,62),backgroundColor:destructive?const Color(0xffff453a):Theme.of(context).colorScheme.surfaceContainerHigh,
      foregroundColor:destructive?Colors.white:Theme.of(context).colorScheme.onSurface,shape:const CircleBorder())),
    const SizedBox(height:7),Text(label,textAlign:TextAlign.center,style:Theme.of(context).textTheme.labelMedium),
  ]);
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Trò chuyện giọng nói'), actions: [
      IconButton(tooltip: 'Bộ nhận dạng', icon: const Icon(CupertinoIcons.mic), onPressed: () async {
        final value = await showCupertinoModalPopup<bool>(context: context, builder: (sheet) => CupertinoActionSheet(
          title: const Text('Bộ nhận dạng giọng nói'), actions: [
            CupertinoActionSheetAction(onPressed: () => Navigator.pop(sheet, true), child: const Text('Ưu tiên Android · có chữ khi đang nói')),
            CupertinoActionSheetAction(onPressed: () => Navigator.pop(sheet, false), child: const Text('Trực tuyến · gửi âm thanh sau khi nói')),
          ], cancelButton: CupertinoActionSheetAction(onPressed: () => Navigator.pop(sheet), child: const Text('Hủy'))));
        if (value == null || !mounted) return;
        await pause();
        (voice.engine as CloudVoiceEngine).preferDeviceRecognition = value;
        if (mounted) await listen();
      }),
      IconButton(tooltip: 'Chọn giọng đọc', icon: const Icon(CupertinoIcons.speaker_2),
        onPressed: () async {
          final value = await showCupertinoModalPopup<String>(context: context, builder: (sheet) => CupertinoActionSheet(
            title: const Text('Chọn giọng đọc'), actions: [
              for (final entry in const {'auto': 'Giọng AI tự chọn · có thể tính phí', 'openai': 'Giọng OpenAI', 'gemini': 'Giọng Gemini', 'phone': 'Giọng trên điện thoại'}.entries)
                CupertinoActionSheetAction(onPressed: () => Navigator.pop(sheet, entry.key), child: Text('${entry.value}${entry.key == selectedVoice ? ' ✓' : ''}')),
            ], cancelButton: CupertinoActionSheetAction(onPressed: () => Navigator.pop(sheet), child: const Text('Hủy')),
          ));
          if (value == null || !mounted) return;
          await pause();
          if (!mounted) return;
          final engine = voice.engine as CloudVoiceEngine;
          engine.useCloudSpeech = value != 'phone';
          engine.speechProvider = value == 'phone' ? 'auto' : value;
          engine.cloudSpeechAvailable = true;
          engine.retryCloudSpeechAfter = null;
          setState(() { selectedVoice = value; speechMode = value == 'phone' ? 'Giọng trên điện thoại' : 'Giọng AI trực tuyến'; });
        }),
    ]),
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
        const SizedBox(height: 16),
        VoiceWave(speaking: voice.speaking, listening: voice.listening, level: voice.soundLevel),
        const SizedBox(height: 12), Text(phase, textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        Text('$recognitionMode · $speechMode', textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
        const SizedBox(height: 12),
        TextButton(onPressed: () => setState(() => showContent = !showContent), child: Text(showContent ? 'Ẩn nội dung' : 'Xem nội dung')),
        if (voice.listening) TextButton.icon(onPressed: voice.finishListening, icon: const Icon(CupertinoIcons.check_mark), label: const Text('Nói xong · trả lời ngay')),
        if (showContent && draft.isNotEmpty) GlassPanel(child: Padding(padding: const EdgeInsets.all(16), child: Text('Bạn: $draft', textAlign: TextAlign.center))),
        if (!processing && !voice.listening && draft.trim().isNotEmpty)
          FilledButton.icon(onPressed: reply, icon: const Icon(Icons.send), label: const Text('Đã nói xong')),
        if (voice.listening && draft.isEmpty && !processing)
          const Text('Hãy nói câu hỏi. Tôi sẽ tự trả lời khi bạn ngừng nói.', textAlign: TextAlign.center),
        if (showContent && response.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 20), child: GlassPanel(child: Padding(padding: const EdgeInsets.all(16), child: SelectableText(response)))),
        if (failure.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 20), child: Text(failure, style: TextStyle(color: Theme.of(context).colorScheme.error))),
        if (failure.isNotEmpty) Wrap(alignment: WrapAlignment.center, children: [
          TextButton(onPressed: processing ? null : listen, child: const Text('Thử lại')),
          TextButton(onPressed: () async {
            try { await pause(); await openVoiceSettings(false, permissions: true); }
            catch (e) { if (mounted) setState(() => failure = '$e'); }
          }, child: const Text('Cài đặt mic')),
          TextButton(onPressed: () async {
            try { await pause(); await openVoiceSettings(true); }
            catch (e) { if (mounted) setState(() => failure = '$e'); }
          }, child: const Text('Cài đặt giọng đọc')),
        ]),
      ])))))),
      Padding(padding:const EdgeInsets.symmetric(horizontal:20,vertical:12),child:Row(children:[
        Expanded(child:voiceControl(paused?CupertinoIcons.mic:CupertinoIcons.mic_slash,paused?'Nói tiếp':'Tắt mic',processing&&!voice.speaking?null:paused?listen:pause)),
        Expanded(child:voiceControl(CupertinoIcons.hand_raised,'Ngắt lời',voice.speaking?pause:null)),
        Expanded(child:voiceControl(CupertinoIcons.phone_down_fill,'Kết thúc',() async {if(closed)return;closed=true;generation++;await voice.stop();SoundEffects.microphoneActive=false;await SoundEffects.play(AppSound.ended,voiceBoundary:true);if(context.mounted)Navigator.pop(context);},destructive:true)),
      ])), const SizedBox(height:8),
    ])),
  );
}

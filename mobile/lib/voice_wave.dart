import 'dart:math' as math;
import 'package:flutter/material.dart';

class VoiceWave extends StatefulWidget {
  final bool speaking, listening;
  final double level;
  const VoiceWave({super.key, required this.speaking, required this.listening, required this.level});
  @override
  State<VoiceWave> createState() => _VoiceWaveState();
}
class _VoiceWaveState extends State<VoiceWave> with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  late final AnimationController animation;
  bool foreground = true;
  @override
  void initState() { super.initState(); animation = AnimationController(vsync: this, duration: const Duration(milliseconds: 1100)); WidgetsBinding.instance.addObserver(this); }
  void updateMotion() {
    if (foreground && widget.speaking && !MediaQuery.disableAnimationsOf(context) && TickerMode.of(context)) { if (!animation.isAnimating) animation.repeat(); }
    else { animation.stop(); }
  }
  @override
  void didChangeDependencies() { super.didChangeDependencies(); updateMotion(); }
  @override
  void didUpdateWidget(covariant VoiceWave oldWidget) { super.didUpdateWidget(oldWidget); updateMotion(); }
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) { foreground = state == AppLifecycleState.resumed; updateMotion(); }
  @override
  void dispose() { WidgetsBinding.instance.removeObserver(this); animation.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => ExcludeSemantics(child: SizedBox(height: 36, child: AnimatedBuilder(animation: animation, builder: (context, _) {
    final reduced = MediaQuery.disableAnimationsOf(context);
    return Row(mainAxisAlignment: MainAxisAlignment.center, children: List.generate(17, (i) {
      final wave = (math.sin(animation.value * math.pi * 2 + i * .7) + 1) / 2;
      final level = reduced ? 0.0 : widget.listening ? widget.level.clamp(0.0, 1.0) : widget.speaking ? .25 + wave * .75 : 0.0;
      final height = 4 + 26 * level * (1 - (i - 8).abs() / 12);
      return Container(width: 4, height: height, margin: const EdgeInsets.symmetric(horizontal: 2),
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(4), gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xff42dcff), Color(0xff9468ff)])));
    }));
  })));
}

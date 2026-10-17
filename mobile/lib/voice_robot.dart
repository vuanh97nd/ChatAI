import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Voice status animation; mouth movement represents actual speech playback.
class VoiceRobot extends StatefulWidget {
  final bool speaking, listening, thinking, paused;
  const VoiceRobot({super.key, this.speaking = false, this.listening = false,
    this.thinking = false, this.paused = false});
  @override
  State<VoiceRobot> createState() => _VoiceRobotState();
}

class _VoiceRobotState extends State<VoiceRobot>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  late final AnimationController clock;
  bool foreground = true;
  @override
  void initState() {
    super.initState();
    clock = AnimationController(vsync: this, duration: const Duration(seconds: 4));
    WidgetsBinding.instance.addObserver(this);
  }
  void updateMotion() {
    final enabled = foreground && !widget.paused &&
      !MediaQuery.disableAnimationsOf(context) && TickerMode.of(context);
    if (enabled) { if (!clock.isAnimating) clock.repeat(); }
    else { clock.stop(); }
  }
  @override
  void didChangeDependencies() { super.didChangeDependencies(); updateMotion(); }
  @override
  void didUpdateWidget(covariant VoiceRobot oldWidget) { super.didUpdateWidget(oldWidget); updateMotion(); }
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
    updateMotion();
  }
  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    clock.dispose();
    super.dispose();
  }
  @override
  Widget build(BuildContext context) {
    final still = !foreground || widget.paused || MediaQuery.disableAnimationsOf(context) || !TickerMode.of(context);
    return Semantics(label: 'Robot Chat AI', image: true,
      child: SizedBox(width: 160, height: 160, child: AnimatedBuilder(
        animation: clock, builder: (context, child) {
          final t = still ? 0.0 : clock.value;
          // One brief blink per four seconds. No floating, rotation or halo.
          final blink = t > .91 && t < .97 ? math.sin((t - .91) / .06 * math.pi) : 0.0;
          final mouth = widget.speaking && !still ? .25 + .75 * (math.sin(t * math.pi * 2 * 13) + 1) / 2 : 0.0;
          return CustomPaint(painter: _RobotPainter(blink: blink, mouth: mouth,
            speaking: widget.speaking, listening: widget.listening,
            thinking: widget.thinking, paused: widget.paused));
        })));
  }
}

class _RobotPainter extends CustomPainter {
  final double blink, mouth;
  final bool speaking, listening, thinking, paused;
  _RobotPainter({required this.blink, required this.mouth, required this.speaking,
    required this.listening, required this.thinking, required this.paused});
  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 160, size.height / 160);
    final paint = Paint()..isAntiAlias = true;
    final tile = RRect.fromRectAndRadius(const Rect.fromLTWH(4, 4, 152, 152), const Radius.circular(40));
    paint.shader = const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight,
      colors: [Color(0xff04baf7), Color(0xff1748f5), Color(0xff6424e9)]).createShader(tile.outerRect);
    canvas.drawRRect(tile, paint);
    paint.shader = null;
    paint.color = const Color(0xffeaf9ff);
    canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(22, 67, 14, 36), const Radius.circular(7)), paint);
    canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(124, 67, 14, 36), const Radius.circular(7)), paint);
    canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(76, 29, 8, 25), const Radius.circular(4)), paint);
    paint.color = paused ? const Color(0xffb8c5d9) : listening ? const Color(0xffb5ffe2) : const Color(0xfff8fdff);
    canvas.drawCircle(const Offset(80, 28), 8, paint);
    paint.color = const Color(0xfff2fbff);
    canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(32, 48, 96, 78), const Radius.circular(28)), paint);
    paint.color = const Color(0xff102c61);
    for (final x in [59.0, 101.0]) {
      final eyeHeight = 13 * (1 - blink) + 1;
      canvas.drawOval(Rect.fromCenter(center: Offset(x, 80), width: 24, height: eyeHeight * 2), paint);
      if (blink < .5) {
        paint.color = Colors.white;
        canvas.drawCircle(Offset(x - 3, 76), 3, paint);
        paint.color = const Color(0xff102c61);
      }
    }
    if (speaking) {
      // A small open mouth remains visible with reduced motion enabled.
      canvas.drawOval(Rect.fromCenter(center: const Offset(80, 105), width: 17, height: 5 + mouth * 15), paint);
    } else if (thinking) {
      paint.strokeWidth = 4; paint.strokeCap = StrokeCap.round;
      canvas.drawLine(const Offset(75, 106), const Offset(85, 106), paint);
    } else {
      paint.style = PaintingStyle.stroke; paint.strokeWidth = 4; paint.strokeCap = StrokeCap.round;
      canvas.drawArc(const Rect.fromLTWH(69, 94, 22, 16), .15 * math.pi, .7 * math.pi, false, paint);
    }
    canvas.restore();
  }
  @override
  bool shouldRepaint(covariant _RobotPainter oldDelegate) => blink != oldDelegate.blink ||
    mouth != oldDelegate.mouth || speaking != oldDelegate.speaking ||
    listening != oldDelegate.listening || thinking != oldDelegate.thinking || paused != oldDelegate.paused;
}

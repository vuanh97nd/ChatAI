import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Same two-second float and blue/violet glow as Desktop's WelcomeRobot.
class AnimatedChatLogo extends StatefulWidget {
  final double size;
  const AnimatedChatLogo({super.key, this.size = 96});
  @override
  State<AnimatedChatLogo> createState() => _AnimatedChatLogoState();
}

class _AnimatedChatLogoState extends State<AnimatedChatLogo>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  late final AnimationController controller;
  bool foreground = true;
  bool animate = false;

  @override
  void initState() {
    super.initState();
    controller = AnimationController(vsync: this, duration: const Duration(seconds: 2));
    WidgetsBinding.instance.addObserver(this);
  }

  void updateMotion() {
    if (foreground && animate) {
      if (!controller.isAnimating) controller.repeat();
    } else {
      controller.stop();
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    animate = !MediaQuery.disableAnimationsOf(context) && TickerMode.of(context);
    updateMotion();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
    updateMotion();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(8),
    child: AnimatedBuilder(animation: controller, builder: (context, child) {
      final wave = animate ? math.sin(controller.value * 2 * math.pi) : 0.0;
      final pulse = (wave + 1) / 2;
      return Transform.translate(offset: Offset(0, -3 * wave), child: Container(
        decoration: BoxDecoration(shape: BoxShape.circle, gradient: RadialGradient(colors: [
          const Color(0xff6842ff).withValues(alpha: .14 + .18 * pulse),
          const Color(0xff2695ff).withValues(alpha: .08 + .10 * pulse),
          const Color(0xff2695ff).withValues(alpha: 0),
        ], stops: const [0, .65, 1])),
        child: child,
      ));
    }, child: Image.asset('assets/chat_ai.png', width: widget.size, height: widget.size,
      semanticLabel: 'Logo ChatAI')),
  );
}

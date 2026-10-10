import 'dart:math' as math;
import 'package:flutter/material.dart';

class ReplyIndicator extends StatefulWidget {
  final String status;
  const ReplyIndicator({super.key, required this.status});
  @override
  State<ReplyIndicator> createState() => _ReplyIndicatorState();
}
class _ReplyIndicatorState extends State<ReplyIndicator> with SingleTickerProviderStateMixin {
  late final AnimationController animation = AnimationController(vsync: this,
    duration: const Duration(milliseconds: 1200));
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) { animation.stop(); }
    else { animation.repeat(); }
  }
  @override
  void dispose() { animation.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.all(16),
    child: Row(children: [
      Image.asset('assets/chat_ai.png', width: 28, height: 28), const SizedBox(width: 12),
      Flexible(child: Text(widget.status)), const SizedBox(width: 8),
      AnimatedBuilder(animation: animation, builder: (context, _) => Row(mainAxisSize: MainAxisSize.min,
        children: List.generate(3, (i) {
          final opacity = MediaQuery.disableAnimationsOf(context) ? .6 : .25 + .75 * (math.sin(animation.value * math.pi * 2 - i * .9) + 1) / 2;
          return Padding(padding: const EdgeInsets.all(3), child: Opacity(opacity: opacity,
            child: Container(width: 6, height: 6, decoration: BoxDecoration(shape: BoxShape.circle, color: Theme.of(context).colorScheme.primary))));
        }))),
    ]));
}

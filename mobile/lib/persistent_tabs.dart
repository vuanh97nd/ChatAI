import 'package:flutter/material.dart';

/// Mount a tab on its first visit, preserving drafts and scroll positions.
/// Secondary drawer pages can opt out so their polling stops when closed.
class PersistentTabs extends StatefulWidget {
  final int selected;
  final Widget Function(int) builder;
  final bool animate;
  const PersistentTabs({super.key, required this.selected, required this.builder, this.animate = true});
  @override
  State<PersistentTabs> createState() => _PersistentTabsState();
}
class _PersistentTabsState extends State<PersistentTabs> with SingleTickerProviderStateMixin {
  final visited = <int>{};
  final pages = <int, Widget>{};
  late final AnimationController transition = AnimationController(vsync: this, duration: const Duration(milliseconds: 160), value: 1);
  bool retained(int index) => const {0, 3, 6, 7}.contains(index);
  @override
  void didUpdateWidget(covariant PersistentTabs oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.selected != widget.selected) {
      visited.removeWhere((index) => !retained(index));
      pages.removeWhere((index, _) => !retained(index));
      if (widget.animate && !MediaQuery.disableAnimationsOf(context)) {
        transition.forward(from: 0);
      } else { transition.value = 1; }
    }
  }
  @override
  void dispose() { transition.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) {
    visited.add(widget.selected);
    pages[widget.selected] = widget.builder(widget.selected);
    return Stack(fit: StackFit.expand, children: [
      for (final index in visited) Offstage(key: ValueKey(index), offstage: index != widget.selected,
        child: TickerMode(enabled: index == widget.selected,
          child: ExcludeFocus(excluding: index != widget.selected,
            child: SlideTransition(position: index == widget.selected
                ? Tween<Offset>(begin: const Offset(.018, 0), end: Offset.zero).chain(CurveTween(curve: Curves.easeOutCubic)).animate(transition)
                : const AlwaysStoppedAnimation(Offset.zero),
              child: RepaintBoundary(child: pages[index]!))))),
    ]);
  }
}

import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

/// Shared inset groups keep secondary screens consistent with the tab shell.
class IosPageList extends StatelessWidget {
  final String title;
  final String? subtitle;
  final List<Widget> children;
  final Key? storageKey;
  const IosPageList({super.key, required this.title, this.subtitle, required this.children, this.storageKey});
  @override
  Widget build(BuildContext context) => ListView(key: storageKey, padding: const EdgeInsets.fromLTRB(16, 12, 16, 28), children: [
    Padding(padding: const EdgeInsets.only(left: 4, bottom: 16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(title, style: Theme.of(context).textTheme.headlineLarge?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -.8)),
      if (subtitle != null) Padding(padding: const EdgeInsets.only(top: 6), child: Text(subtitle!, style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, height: 1.4))),
    ])),
    ...children,
  ]);
}
class IosSection extends StatelessWidget {
  final String? title;
  final List<Widget> children;
  const IosSection({super.key, this.title, required this.children});
  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.only(bottom: 20), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
    if (title != null) Padding(padding: const EdgeInsets.fromLTRB(16, 0, 16, 8), child: Text(title!, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: Theme.of(context).colorScheme.onSurfaceVariant))),
    Material(color: Theme.of(context).colorScheme.surface, borderRadius: BorderRadius.circular(18), clipBehavior: Clip.antiAlias, child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      for (var i = 0; i < children.length; i++) ...[
        if (i > 0) Divider(height: 1, thickness: .5, indent: 16, color: Theme.of(context).dividerColor.withValues(alpha: .18)),
        children[i],
      ],
    ])),
  ]));
}
class IosChoice extends StatelessWidget {
  final String title, subtitle;
  final bool selected;
  final VoidCallback onTap;
  const IosChoice({super.key, required this.title, required this.subtitle, required this.selected, required this.onTap});
  @override
  Widget build(BuildContext context) => Semantics(selected: selected, child: ListTile(onTap: onTap,
    title: Text(title), subtitle: Text(subtitle),
    trailing: selected ? Icon(CupertinoIcons.check_mark, color: Theme.of(context).colorScheme.primary) : null));
}

class IosTabHeader extends StatelessWidget implements PreferredSizeWidget {
  final List<String> labels;
  const IosTabHeader({super.key, required this.labels});
  @override
  Size get preferredSize => const Size.fromHeight(56);
  @override
  Widget build(BuildContext context) {
    final controller = DefaultTabController.of(context);
    return AnimatedBuilder(animation: controller, builder: (context, _) => Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
      child: SizedBox(width: double.infinity, child: CupertinoSlidingSegmentedControl<int>(
        groupValue: controller.index,
        children: {for (var i = 0; i < labels.length; i++) i: Padding(padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4), child: Text(labels[i], maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13)))},
        onValueChanged: (index) { if (index != null) controller.animateTo(index); },
      )),
    ));
  }
}

/// Cupertino confirmations still provide Material for existing form fields.
class IosAlertDialog extends StatelessWidget {
  final Widget? title, content;
  final List<Widget>? actions;
  const IosAlertDialog({super.key, this.title, this.content, this.actions});
  @override
  Widget build(BuildContext context) {
    if (Theme.of(context).platform != TargetPlatform.iOS) {
      return AlertDialog(title: title, content: content, actions: actions);
    }
    return CupertinoAlertDialog(title: title,
      content: content == null ? null : Material(type: MaterialType.transparency, child: content),
      actions: [for (final action in actions ?? <Widget>[]) if (action is ButtonStyleButton)
        CupertinoDialogAction(onPressed: action.onPressed, child: action.child ?? const SizedBox.shrink()) else action],
    );
  }
}

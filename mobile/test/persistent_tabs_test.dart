import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import '../lib/persistent_tabs.dart';

void main() {
  testWidgets('updates to the active tab do not rebuild a hidden tab', (tester) async {
    var selected = 0;
    late StateSetter update;
    final builds = <int, int>{};
    await tester.pumpWidget(MaterialApp(home: StatefulBuilder(builder: (context, setState) {
      update = setState;
      return Scaffold(body: PersistentTabs(selected: selected, builder: (index) {
        builds.update(index, (n) => n + 1, ifAbsent: () => 1);
        return Text('page $index');
      }));
    })));
    update(() => selected = 6); await tester.pumpAndSettle();
    update(() {}); await tester.pumpAndSettle();
    update(() {}); await tester.pumpAndSettle();
    expect(builds[0], 1);
    expect(builds[6], 3);
    expect(tester.takeException(), isNull);
  });
  testWidgets('bottom tabs mount lazily and retain edits across rapid switches', (tester) async {
    var selected = 0;
    late StateSetter update;
    final mounts = <int, int>{};
    await tester.pumpWidget(MaterialApp(home: StatefulBuilder(builder: (context, setState) {
      update = setState;
      return Scaffold(body: PersistentTabs(selected: selected, builder: (index) => _Draft(index, mounts)));
    })));
    expect(mounts, {0: 1});
    await tester.enterText(find.byType(TextField), 'Câu hỏi chưa gửi');
    update(() => selected = 6); await tester.pump();
    await tester.enterText(find.byType(TextField), 'Kế hoạch đang viết');
    update(() => selected = 7); await tester.pump();
    update(() => selected = 6); await tester.pumpAndSettle();
    expect(find.text('Kế hoạch đang viết'), findsOneWidget);
    update(() => selected = 0); await tester.pumpAndSettle();
    expect(find.text('Câu hỏi chưa gửi'), findsOneWidget);
    expect(mounts, {0: 1, 6: 1, 7: 1});
    expect(tester.takeException(), isNull);
  });
  testWidgets('drawer page is disposed and reduced motion has no transition', (tester) async {
    var selected = 4;
    late StateSetter update;
    await tester.pumpWidget(MaterialApp(home: StatefulBuilder(builder: (context, setState) {
      update = setState;
      return MediaQuery(data: const MediaQueryData(disableAnimations: true), child: Scaffold(
        body: PersistentTabs(selected: selected, builder: (index) => Text('page $index'))));
    })));
    update(() => selected = 0); await tester.pump();
    expect(find.text('page 4', skipOffstage: false), findsNothing);
    expect(tester.binding.hasScheduledFrame, isFalse);
    expect(find.text('page 0'), findsOneWidget);
  });
}
class _Draft extends StatefulWidget {
  final int index;
  final Map<int, int> mounts;
  const _Draft(this.index, this.mounts);
  @override
  State<_Draft> createState() => _DraftState();
}
class _DraftState extends State<_Draft> {
  final controller = TextEditingController();
  @override
  void initState() { super.initState(); widget.mounts.update(widget.index, (n) => n + 1, ifAbsent: () => 1); }
  @override
  void dispose() { controller.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => TextField(controller: controller);
}

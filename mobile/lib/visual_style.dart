import 'dart:math' as math;
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/cupertino.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'sound_effects.dart';
import 'location_context.dart';
import 'ios_settings.dart';

enum VisualEffects { full, light, off }
final visualEffects = ValueNotifier<VisualEffects>(VisualEffects.full);

ThemeData futuristicTheme(Brightness brightness) {
  final dark = brightness == Brightness.dark;
  final scheme = ColorScheme.fromSeed(seedColor: const Color(0xff007aff), brightness: brightness).copyWith(primary: dark ? const Color(0xff0a84ff) : const Color(0xff007aff), surface: dark ? const Color(0xff1c1c1e) : Colors.white, surfaceContainerLow: dark ? const Color(0xff1c1c1e) : Colors.white, primaryContainer: dark ? const Color(0xff153551) : const Color(0xffe4f0ff));
  return ThemeData(splashFactory: NoSplash.splashFactory, highlightColor: Colors.transparent,
    listTileTheme: const ListTileThemeData(contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 4), minVerticalPadding: 10),
    checkboxTheme: CheckboxThemeData(shape: const CircleBorder(), side: BorderSide(color: scheme.onSurfaceVariant, width: 1.5)),
    outlinedButtonTheme: OutlinedButtonThemeData(style: OutlinedButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)), side: BorderSide(color: scheme.outlineVariant.withValues(alpha: .3)))),
    tabBarTheme: TabBarThemeData(dividerColor: Colors.transparent, indicatorSize: TabBarIndicatorSize.tab, labelColor: scheme.primary, unselectedLabelColor: scheme.onSurfaceVariant, indicator: BoxDecoration(color: scheme.primary.withValues(alpha: .12), borderRadius: BorderRadius.circular(12))),
    useMaterial3: true, fontFamily: 'Roboto', platform: TargetPlatform.iOS, cupertinoOverrideTheme: CupertinoThemeData(brightness: brightness, primaryColor: scheme.primary, textTheme: CupertinoTextThemeData(textStyle: TextStyle(fontFamily:'Roboto',fontSize:17,color:scheme.onSurface), actionTextStyle: TextStyle(fontFamily:'Roboto',fontSize:20,color:scheme.primary))), colorScheme: scheme, scaffoldBackgroundColor: Colors.transparent,
    appBarTheme: AppBarTheme(backgroundColor: dark ? const Color(0xe61c1c1e) : const Color(0xe6f2f2f7),
      surfaceTintColor: Colors.transparent, centerTitle: true, elevation: 0,
      titleTextStyle: TextStyle(fontFamily: 'Roboto', fontSize: 20, fontWeight: FontWeight.w600, color: scheme.onSurface)),
    cardTheme: CardThemeData(color: dark ? const Color(0xff1c1c1e) : const Color(0xffffffff), elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: scheme.outline.withValues(alpha: .08)))),
    inputDecorationTheme: InputDecorationTheme(floatingLabelBehavior: FloatingLabelBehavior.never, filled: true, fillColor: scheme.surfaceContainerHighest.withValues(alpha: .4),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide(color: scheme.primary, width: 1))),
    filledButtonTheme: FilledButtonThemeData(style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)))),
    navigationBarTheme: NavigationBarThemeData(backgroundColor: Colors.transparent, elevation: 0,
      indicatorColor: Colors.transparent, iconTheme: WidgetStateProperty.resolveWith((states)=>IconThemeData(color:states.contains(WidgetState.selected)?scheme.primary:scheme.onSurfaceVariant,size:24)), labelTextStyle: WidgetStateProperty.resolveWith((states)=>TextStyle(fontSize:11,fontWeight:FontWeight.w500,color:states.contains(WidgetState.selected)?scheme.primary:scheme.onSurfaceVariant)), height: 62),
    snackBarTheme: SnackBarThemeData(behavior: SnackBarBehavior.floating, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
  );
}

class AmbientScene extends StatefulWidget {
  final Widget child;
  final VisualEffects effects;
  const AmbientScene({super.key, required this.child, required this.effects});
  @override
  State<AmbientScene> createState() => _AmbientSceneState();
}
class _AmbientSceneState extends State<AmbientScene> with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  late final AnimationController motion;
  bool foreground = true;
  @override
  void initState() { super.initState(); motion = AnimationController(vsync: this, duration: const Duration(seconds: 18)); WidgetsBinding.instance.addObserver(this); }
  void updateMotion() {
    if (foreground && widget.effects == VisualEffects.full && !MediaQuery.disableAnimationsOf(context) && MediaQuery.viewInsetsOf(context).bottom == 0 && TickerMode.of(context)) {
      if (!motion.isAnimating) motion.repeat();
    } else { motion.stop(); }
  }
  @override
  void didChangeDependencies() { super.didChangeDependencies(); updateMotion(); }
  @override
  void didUpdateWidget(covariant AmbientScene oldWidget) { super.didUpdateWidget(oldWidget); updateMotion(); }
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) { foreground = state == AppLifecycleState.resumed; updateMotion(); }
  @override
  void dispose() { WidgetsBinding.instance.removeObserver(this); motion.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => Stack(
    fit: StackFit.expand,
    children: [
      Positioned.fill(
        child: IgnorePointer(
          child: RepaintBoundary(
            child: AnimatedBuilder(
              animation: motion,
              builder: (_, child) => CustomPaint(
                painter: _AuroraPainter(motion.value, Theme.of(context).brightness == Brightness.dark, widget.effects),
              ),
            ),
          ),
        ),
      ),
      widget.child,
    ],
  );
}
class _AuroraPainter extends CustomPainter {
  final double phase;
  final bool dark;
  final VisualEffects effects;
  _AuroraPainter(this.phase, this.dark, this.effects);
  @override
  void paint(Canvas canvas, Size size) {
    final bounds = Offset.zero & size;
    canvas.drawRect(bounds, Paint()..color = dark ? const Color(0xff000000) : const Color(0xfff2f2f7));
    if (effects == VisualEffects.off) return;
    final t = phase * math.pi * 2;
    final colors = [const Color(0xff336dff), const Color(0xff8a3ffc), const Color(0xff00c6e5)];
    final centers = [Offset(size.width * (.12 + .13 * math.sin(t)), size.height * .16),
      Offset(size.width * (.8 + .1 * math.cos(t)), size.height * (.48 + .12 * math.sin(t))),
      Offset(size.width * .2, size.height * (.88 + .05 * math.cos(t)))];
    for (var i = 0; i < centers.length; i++) {
      final radius = size.width * .9;
      canvas.drawCircle(centers[i], radius, Paint()..shader = RadialGradient(colors: [colors[i].withValues(alpha: dark ? .055 : .025), colors[i].withValues(alpha: 0)])
        .createShader(Rect.fromCircle(center: centers[i], radius: radius)));
    }

  }
  @override
  bool shouldRepaint(covariant _AuroraPainter oldDelegate) => phase != oldDelegate.phase || dark != oldDelegate.dark || effects != oldDelegate.effects;
}

class GlassPanel extends StatelessWidget {
  final Widget child;
  final BorderRadius radius;
  const GlassPanel({super.key, required this.child, this.radius = const BorderRadius.all(Radius.circular(24))});
  @override
  Widget build(BuildContext context) => ValueListenableBuilder<VisualEffects>(valueListenable: visualEffects, builder: (context, effects, _) {
    final scheme = Theme.of(context).colorScheme;
    final content = DecoratedBox(decoration: BoxDecoration(borderRadius: radius,
      color: scheme.surface.withValues(alpha: effects == VisualEffects.off ? 1 : .84),
      border: Border.all(color: scheme.outline.withValues(alpha: .1))), child: child);
    return ClipRRect(borderRadius: radius, child: effects == VisualEffects.off ? content :
      BackdropFilter(filter: ImageFilter.blur(sigmaX: effects == VisualEffects.full ? 12 : 5, sigmaY: effects == VisualEffects.full ? 12 : 5), child: content));
  });
}

class EffectsPage extends StatelessWidget {
  const EffectsPage({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Hiệu ứng giao diện')),
    body: ValueListenableBuilder<VisualEffects>(valueListenable: visualEffects, builder: (context, value, _) => IosPageList(title: 'Cá nhân hóa', subtitle: 'Cài đặt Giảm chuyển động của hệ thống luôn được ưu tiên.', children: [
      IosSection(title: 'QUYỀN RIÊNG TƯ VÀ ÂM THANH', children: [
      ValueListenableBuilder<bool>(valueListenable: locationForQuestions, builder: (context, enabled, _) => SwitchListTile.adaptive(
        title: const Text('Vị trí cho thời tiết và địa điểm'), subtitle: const Text('Chỉ lấy khi câu hỏi cần vị trí, sau khi bạn cấp quyền Android. Không theo dõi nền.'),
        value: enabled, onChanged: (next) async {
          try { await const FlutterSecureStorage().write(key: 'location_for_questions', value: '$next'); locationForQuestions.value = next; }
          catch (_) { if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Chưa lưu được cài đặt vị trí.'))); }
        })),
      ValueListenableBuilder<bool>(valueListenable: SoundEffects.enabled, builder: (context, enabled, _) => SwitchListTile.adaptive(
        title: const Text('Âm thanh hiệu ứng'),
        subtitle: const Text('Âm nhẹ khi gửi tin, nhận câu trả lời và tạo ảnh xong. Tôn trọng chế độ im lặng và Không làm phiền. Không phát lúc đang thu hoặc đọc; âm báo thu phát trước khi mở micro.'),
        value: enabled, onChanged: (next) async {
          try { await const FlutterSecureStorage().write(key: 'sound_effects', value: '$next'); SoundEffects.enabled.value = next; }
          catch (_) { if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Chưa lưu được cài đặt âm thanh.'))); }
        })),
      ValueListenableBuilder<double>(valueListenable: SoundEffects.volume, builder: (context, volume, _) => Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
        Padding(padding:const EdgeInsets.symmetric(horizontal:16),child:Text('Âm lượng hiệu ứng · ${(volume*100).round()}%')),
        CupertinoSlider(value:volume,divisions:20,onChanged:(next)=>SoundEffects.volume.value=next,onChangeEnd:(next) async {
          try { await const FlutterSecureStorage().write(key:'sound_volume',value:'$next'); }
          catch (_) { if(context.mounted)ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content:Text('Chưa lưu được âm lượng.'))); }
        }),
      ])),
      Padding(padding:const EdgeInsets.symmetric(horizontal:16),child:Wrap(spacing:6,children:[
        for(final cue in const {AppSound.sent:'Gửi tin',AppSound.reply:'Trả lời',AppSound.listening:'Bắt đầu thu',AppSound.ended:'Kết thúc',AppSound.created:'Tạo ảnh',AppSound.saved:'Lưu tệp',AppSound.error:'Lỗi'}.entries)
          TextButton(onPressed:()=>SoundEffects.play(cue.key),child:Text('Nghe: ${cue.value}')),
      ])),
      ]),
      IosSection(title: 'CHUYỂN ĐỘNG', children: [
      for (final mode in VisualEffects.values) IosChoice(selected: mode == value,
        title: switch(mode) { VisualEffects.full => 'Đầy đủ', VisualEffects.light => 'Nhẹ', VisualEffects.off => 'Tắt hiệu ứng' },
        subtitle: switch(mode) { VisualEffects.full => 'Kính mờ, chuyển động nhẹ và bảng chọn kiểu iOS', VisualEffects.light => 'Nền tĩnh, kính mờ nhẹ; giảm hoạt ảnh trang trí', VisualEffects.off => 'Nền đơn sắc, tắt chuyển động trang trí' },
        onTap: () async {
          try { await const FlutterSecureStorage().write(key: 'visual_effects', value: mode.name); visualEffects.value = mode; }
          catch (_) { if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Chưa lưu được mức hiệu ứng. Hãy thử lại.'))); }
        }),
      ]),
    ])));
}

class MessageEntrance extends StatelessWidget {
  final Widget child;
  const MessageEntrance({super.key, required this.child});
  @override
  Widget build(BuildContext context) {
    final animate = visualEffects.value == VisualEffects.full && !MediaQuery.disableAnimationsOf(context);
    return TweenAnimationBuilder<double>(tween: Tween(begin: animate ? 0 : 1, end: 1),
      duration: Duration(milliseconds: animate ? 320 : 0), curve: Curves.easeOutCubic,
      child: child, builder: (_, value, child) => Opacity(opacity: value,
        child: Transform.translate(offset: Offset(0, 14 * (1 - value)), child: child)));
  }
}

import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import '../lib/sound_effects.dart';

void main() {
  final binding = TestWidgetsFlutterBinding.ensureInitialized();
  final calls = <MethodCall>[];
  setUp(() {
    calls.clear(); SoundEffects.enabled.value = true; SoundEffects.suspended = false; SoundEffects.microphoneActive=false; SoundEffects.volume.value=.35;
    binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    binding.defaultBinaryMessenger.setMockMethodCallHandler(SoundEffects.channel, (call) async { calls.add(call); return null; });
  });
  tearDown(() {
    binding.defaultBinaryMessenger.setMockMethodCallHandler(SoundEffects.channel, null);
    SoundEffects.enabled.value = true; SoundEffects.suspended = false; SoundEffects.microphoneActive=false; SoundEffects.volume.value=.35;
    binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
  });
  test('send reply and image completion use distinct sounds', () async {
    for (final sound in AppSound.values) { await SoundEffects.play(sound); }
    expect(calls.map((c) => (c.arguments as Map)['name']), AppSound.values.map((s)=>s.name));
    expect(calls.every((c)=>(c.arguments as Map)['volume']==.35),isTrue);
  });
  test('disabled voice-session and background events stay silent', () async {
    SoundEffects.enabled.value = false; await SoundEffects.play(AppSound.sent);
    SoundEffects.enabled.value = true; SoundEffects.suspended = true; await SoundEffects.play(AppSound.reply);
    SoundEffects.suspended = false; SoundEffects.microphoneActive=false; SoundEffects.volume.value=.35; binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await SoundEffects.play(AppSound.created);
    expect(calls, isEmpty);
  });
  test('muted volume and active microphone suppress even boundary cues',() async {
    SoundEffects.volume.value=0; await SoundEffects.play(AppSound.reply);
    SoundEffects.volume.value=.5; SoundEffects.microphoneActive=true;
    await SoundEffects.play(AppSound.listening,voiceBoundary:true);
    expect(calls,isEmpty);
  });
  test('start cue may play while voice screen is suspended before the microphone starts',() async {
    SoundEffects.suspended=true;
    await SoundEffects.play(AppSound.listening,voiceBoundary:true);
    expect(calls.length,1);expect((calls.single.arguments as Map)['name'],'listening');
  });
  test('audio platform errors cannot fail chat', () async {
    binding.defaultBinaryMessenger.setMockMethodCallHandler(SoundEffects.channel, (_) async => throw PlatformException(code: 'audio'));
    await expectLater(SoundEffects.play(AppSound.sent), completes);
  });
}

import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:chatai_mobile/streaming_speech.dart';
void main() {
  test('speaks a completed sentence before final text and never repeats it', () async {
    final spoken = <String>[];
    final queue = StreamingSpeech((text) async => spoken.add(text));
    const first = 'Xin chào bạn, hôm nay tôi có thể giúp bạn việc gì? ';
    queue.add(first); await Future<void>.delayed(Duration.zero);
    expect(spoken, [first.trim()]);
    queue.add('${first}Một phần chưa xong');
    await queue.finish('${first}Một phần chưa xong và đã hoàn tất.');
    expect(spoken.join(' '), '${first}Một phần chưa xong và đã hoàn tất.');
  });
  test('serializes audio and cancels pending parts', () async {
    final gate = Completer<void>(); final spoken = <String>[];
    final queue = StreamingSpeech((text) async { spoken.add(text); await gate.future; });
    queue.add('Đây là câu đầu tiên đủ dài để bắt đầu đọc. Đây là câu thứ hai cũng đủ dài để đọc. ');
    await Future<void>.delayed(Duration.zero);
    expect(spoken.length, 1); queue.cancel(); gate.complete();
    await queue.finish('Đây là câu đầu tiên đủ dài để bắt đầu đọc. Đây là câu thứ hai cũng đủ dài để đọc. ');
    expect(spoken.length, 1);
  });
  test('short fragments wait for the end and audio failures propagate once', () async {
    final spoken = <String>[]; final queue = StreamingSpeech((text) async => spoken.add(text));
    queue.add('Xin chào'); await Future<void>.delayed(Duration.zero); expect(spoken, isEmpty);
    await queue.finish('Xin chào bạn.'); expect(spoken, ['Xin chào bạn.']);
    final failed = StreamingSpeech((_) async => throw StateError('TTS unavailable'));
    failed.add('Câu trả lời hoàn chỉnh và đủ dài để có thể đọc.');
    await Future<void>.delayed(Duration.zero);
    await expectLater(failed.finish('Câu trả lời hoàn chỉnh và đủ dài để có thể đọc.'), throwsStateError);
  });
}

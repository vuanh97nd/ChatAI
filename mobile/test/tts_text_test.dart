import 'package:flutter_test/flutter_test.dart';
import 'package:chatai_mobile/tts_text.dart';
import 'package:chatai_mobile/voice.dart';
void main() {
  test('prefers higher-quality installed Vietnamese voice', () {
    final voice = vietnameseVoice([
      {'locale': 'en-US', 'name': 'English', 'quality': 500},
      {'locale': 'vi-VN', 'name': 'Basic', 'quality': 100},
      {'locale': 'vi-VN', 'name': 'Unavailable', 'quality': 600, 'features': ['notInstalled']},
      {'locale': 'vi-VN', 'name': 'Natural', 'quality': '400'},
    ]);
    expect(voice!['name'], 'Natural');
  });
  test('spoken text avoids reading markdown symbols and link URLs', () {
    expect(spokenText('## Xin chào\n**Hôm nay** trời đẹp. [Nguồn](https://example.com)'),
      'Xin chào\nHôm nay trời đẹp. Nguồn');
  });
  test('splits on sentence boundaries while retaining words', () {
    final chunks = speechChunks('Xin chào bạn. Hôm nay trời đẹp. Bạn khỏe không?', 30);
    expect(chunks.first, 'Xin chào bạn.');
    expect(chunks.every((s) => s.length <= 30), isTrue);
    expect(chunks.join(' '), 'Xin chào bạn. Hôm nay trời đẹp. Bạn khỏe không?');
  });
  test('long text respects Android limit without cutting a Unicode pair', () {
    final input = 'Xin chào ${'😀' * 20} kết thúc.';
    final chunks = speechChunks(input, 12);
    expect(chunks.every((s) => s.length <= 12), isTrue);
    expect(chunks.join('').replaceAll(' ', ''), input.replaceAll(' ', ''));
    expect(chunks.every((s) => !s.runes.contains(0xfffd)), isTrue);
  });
}

import 'package:flutter_test/flutter_test.dart';
import '../lib/media_intent.dart';

void main() {
  test('Vietnamese creation requests open media with original prompt', () {
    for (final text in ['Tạo ảnh con mèo', 'Vẽ cho tôi một bức tranh biển', 'Hãy tạo hình một robot', 'Tạo video hoàng hôn', 'tao anh con meo']) {
      expect(isMediaCreationRequest(text), isTrue, reason: text);
    }
    for (final text in ['Ảnh này là gì?', 'Tạo ảnh như thế nào?', 'Bạn có thể tạo ảnh không?', 'xin chào']) {
      expect(isMediaCreationRequest(text), isFalse, reason: text);
    }
  });
}

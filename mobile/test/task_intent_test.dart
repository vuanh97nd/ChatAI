import 'package:flutter_test/flutter_test.dart';
import '../lib/task_intent.dart';

void main() {
  test('ordinary conversation does not offer task planning', () {
    for (final text in ['xin chào', 'Hello', 'Cảm ơn', 'Thời tiết hôm nay',
      'Nhắc nhở là gì?', 'Lập kế hoạch là gì?', 'Tạo ảnh con mèo',
      'Hôm nay tôi đã lập kế hoạch xong']) {
      expect(isTaskRequest(text), isFalse, reason: text);
    }
  });
  test('explicit planning and reminder requests offer the shortcut', () {
    for (final text in ['Lập kế hoạch học tiếng Anh', 'Hãy lên kế hoạch du lịch',
      'Nhắc tôi uống thuốc lúc 8 giờ', 'Vui lòng tạo lịch học cho tôi',
      'Giúp tôi lập kế hoạch tuần này', 'lap ke hoach tap the duc',
      'Remind me to call mom']) {
      expect(isTaskRequest(text), isTrue, reason: text);
    }
  });
}

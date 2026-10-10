import 'package:flutter_test/flutter_test.dart';
import 'package:chatai_mobile/notifications.dart';
void main() {
  test('only unread unseen notifications are selected, at most five', () {
    final items = <Map<String, dynamic>>[
      {'id': 'seen', 'read_at': null}, {'id': 'read', 'read_at': 123},
      for (var i = 0; i < 10; i++) {'id': 'new$i', 'read_at': null},
    ];
    final selected = unseenNotifications(items, {'seen'});
    expect(selected.map((m) => m['id']), ['new0', 'new1', 'new2', 'new3', 'new4']);
  });
}

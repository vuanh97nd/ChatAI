/// Serializes speech while cumulative model text is still arriving.
/// Never speaks an already queued prefix again when the final answer arrives.
class StreamingSpeech {
  final Future<void> Function(String) read;
  Future<void> _tail = Future.value();
  String _committed = '';
  bool _cancelled = false;
  Object? _failure;
  StreamingSpeech(this.read);
  void add(String text, {bool complete = false}) {
    text = text.trimLeft();
    if (_cancelled || !text.startsWith(_committed)) return;
    var remaining = text.substring(_committed.length);
    while (remaining.isNotEmpty) {
      var end = 0;
      final window = remaining.length > 240 ? remaining.substring(0, 240) : remaining;
      for (final boundary in RegExp(r'[.!?…](?:\s|$)|\n').allMatches(window)) {
        if (boundary.end >= 35) { end = boundary.end; break; }
      }
      if (end == 0 && (complete || remaining.length >= 240)) {
        end = window.length;
        if (remaining.length > end) {
          final space = window.lastIndexOf(' ');
          if (space > 0) end = space;
        }
      }
      if (end == 0) break;
      // Do not split a UTF-16 surrogate pair.
      if (end < remaining.length && end > 0 && remaining.codeUnitAt(end - 1) >= 0xD800 && remaining.codeUnitAt(end - 1) <= 0xDBFF) end--;
      final part = remaining.substring(0, end);
      _committed += part;
      remaining = remaining.substring(end);
      if (part.trim().isEmpty) continue;
      _tail = _tail.then((_) async {
        if (_cancelled || _failure != null) return;
        try { await read(part.trim()); } catch (e) { _failure = e; }
      });
    }
  }
  Future<void> finish(String text) async {
    add(text, complete: true);
    await _tail;
    if (_failure != null) throw _failure!;
  }
  void cancel() { _cancelled = true; }
}

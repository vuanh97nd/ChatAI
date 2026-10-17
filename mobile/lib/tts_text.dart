/// Prepare the spoken version only; the original answer remains on screen.
String spokenText(String text) => text
  .replaceAll(RegExp(r'```[\s\S]*?```'), '\nPhần mã được hiển thị trong nội dung trả lời.\n')
  .replaceAllMapped(RegExp(r'!?\[([^\]]+)\]\(https?://[^\s)]+\)'), (m) => m[1]!)
  .replaceAll(RegExp(r'^\s{0,3}#{1,6}\s+', multiLine: true), '')
  .replaceAll(RegExp(r'^\s*[-*•]\s+', multiLine: true), '')
  .replaceAll(RegExp(r'[*_`~]'), '')
  .replaceAll(RegExp(r'[ \t]+'), ' ')
  .replaceAll(RegExp(r'\n{3,}'), '\n\n').trim();

/// Prefer sentence/paragraph boundaries, then spaces. Never split a surrogate
/// pair, and retain all text even when Android reports a smaller input limit.
List<String> speechChunks(String text, int maxLength) {
  final limit = maxLength < 2 ? 2 : maxLength;
  final chunks = <String>[];
  var rest = spokenText(text);
  while (rest.isNotEmpty) {
    if (rest.length <= limit) { chunks.add(rest); break; }
    var end = limit;
    final window = rest.substring(0, limit);
    final boundaries = RegExp(r'[.!?…][\s]+|\n+').allMatches(window).toList();
    if (boundaries.isNotEmpty) {
      end = boundaries.last.end;
    } else {
      final space = window.lastIndexOf(' ');
      if (space > 0) end = space;
    }
    if (end > 0 && rest.codeUnitAt(end - 1) >= 0xD800 && rest.codeUnitAt(end - 1) <= 0xDBFF) end--;
    chunks.add(rest.substring(0, end).trim());
    rest = rest.substring(end).trimLeft();
  }
  return chunks.where((chunk) => chunk.isNotEmpty).toList();
}

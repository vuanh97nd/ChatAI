/// Small, local intent check. Only the public question goes to web search.
String foldVietnamese(String value) {
  const groups = {'a':'àáạảãâầấậẩẫăằắặẳẵ','e':'èéẹẻẽêềếệểễ','i':'ìíịỉĩ',
    'o':'òóọỏõôồốộổỗơờớợởỡ','u':'ùúụủũưừứựửữ','y':'ỳýỵỷỹ','d':'đ'};
  var result = value.toLowerCase();
  groups.forEach((plain, accented) { for (final rune in accented.runes) { result = result.replaceAll(String.fromCharCode(rune), plain); } });
  return result;
}

class LiveSearchPlan {
  final String query;
  final String? location;
  final bool askLocation;
  const LiveSearchPlan(this.query, {this.location, this.askLocation = false});
}

LiveSearchPlan? liveSearchPlan(List<Map<String, String>> messages) {
  final users = messages.where((m) => m['role'] == 'user').map((m) => (m['content'] ?? '').split('\n').first.trim()).toList();
  if (users.isEmpty) return null;
  final question = users.last;
  if (question.isEmpty || question.length > 350 || question.split(RegExp(r'\s+')).length > 60) return null;
  if (RegExp(r'^(?:con )?(?:ngay mai|ngay kia|hom nay)(?: thi sao)?[?!.]*$').hasMatch(foldVietnamese(question)) && users.length > 1) {
    final previous = liveSearchPlan([for (final text in users.take(users.length - 1)) {'role': 'user', 'content': text}]);
    if (previous != null && (previous.location != null || previous.askLocation)) return LiveSearchPlan('${previous.query} $question', location: previous.location, askLocation: previous.askLocation);
  }
  final weather = RegExp(r'\b(thoi tiet|nhiet do|du bao thoi tiet|troi co mua|co mua khong|weather)\b');
  var request = question;
  if (!weather.hasMatch(foldVietnamese(request)) && users.length > 1 &&
      weather.hasMatch(foldVietnamese(users[users.length - 2])) &&
      messages.any((m) => m['role']=='assistant' && foldVietnamese(m['content'] ?? '').contains('tinh/thanh pho nao')) &&
      question.split(' ').length <= 8 && !RegExp(r'^(cam on|thanks|ok|khong)').hasMatch(foldVietnamese(question))) {
    request = 'thời tiết $question';
  }
  if (weather.hasMatch(foldVietnamese(request))) {
    var place = request.replaceAll(RegExp(r'[?!.,]'), ' ').trim();
    // Strip known weather/time phrases, preserving the user's place spelling.
    final folded = foldVietnamese(place);
    final match = RegExp(r'(?:thoi tiet|nhiet do|du bao thoi tiet|troi co mua|co mua khong|weather)\s*(.*)').firstMatch(folded);
    if (match != null) place = place.substring(match.start + match.group(0)!.length - match.group(1)!.length);
    final removable = RegExp(r'\b(hom nay|ngay mai|bay gio|hien tai|the nao|ra sao|bao nhieu do|co mua khong|xin cho biet|cho toi biet|giup toi|giup minh|today|tomorrow)\b');
    final matches = removable.allMatches(foldVietnamese(place)).toList().reversed;
    for (final m in matches) { place = place.replaceRange(m.start,m.end,' '); }
    place=place.replaceAll(RegExp(r'\s+'),' ').trim();
    final prefix=RegExp(r'^(o|tai|cho|cua|in)\s+').firstMatch(foldVietnamese(place));
    if(prefix!=null) place=place.substring(prefix.end).trim();
    final suffix=RegExp(r'\s+(nhe|voi|a)$').firstMatch(foldVietnamese(place));
    if(suffix!=null) place=place.substring(0,suffix.start).trim();
    if (place.isEmpty || asksNearby(place)) return LiveSearchPlan(request, askLocation: true);
    return LiveSearchPlan(request, location: place);
  }
  final live = RegExp(r'\b(tin tuc|tin moi|tin nong|tin hom nay|tin thoi su|thoi su|news|ty gia|gia vang|gia xang|chung khoan)\b');
  if (!live.hasMatch(foldVietnamese(question))) return null;
  final date = DateTime.now().toUtc().add(const Duration(hours: 7)).toIso8601String().substring(0,10);
  return LiveSearchPlan('$question $date');
}


bool asksNearby(String text) => RegExp(r'\b(gan (?:toi|day|nhat)|quanh (?:toi|day)|o day|cho toi dang o|vi tri hien tai|near me|nearby)\b').hasMatch(foldVietnamese(text));
bool asksMap(String text) => RegExp(r'\b(ban do|chi duong|duong di|tim duong|google maps|map|maps)\b').hasMatch(foldVietnamese(text));
String specialistFor(String text) {
  final q = foldVietnamese(text);
  if (RegExp(r'\b(tin tuc|tin moi|tin nong|tin hom nay|tin thoi su|thoi su|news)\b').hasMatch(q)) return 'news';
  if (RegExp(r'^(?:tra cuu |tim hieu )|\b(?:la gi|wikipedia)\b').hasMatch(q)) return 'knowledge';
  return 'search';
}

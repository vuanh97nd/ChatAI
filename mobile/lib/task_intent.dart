import 'live_search.dart';

/// Show the shortcut for explicit planning/reminder requests, not ordinary chat.
bool isTaskRequest(String text) {
  final question = foldVietnamese(text).replaceAll(RegExp(r'\s+'), ' ').trim();
  if (RegExp(r'\b(la gi|nghia la gi|nhu the nao)\b').hasMatch(question)) return false;
  return RegExp(
    r'^(?:(?:xin|hay|vui long|lam on|ban|co the|giup toi|giup minh) )*'
    r'(?:lap (?:cho (?:toi|minh) )?ke hoach|len (?:cho (?:toi|minh) )?ke hoach|'
    r'tao (?:cho (?:toi|minh) )?(?:ke hoach|lich|danh sach (?:viec|cong viec))|'
    r'nhac (?:toi|minh|nho)|dat (?:lich nhac|nhac nho)|'
    r'plan|remind me|create a plan)\b',
  ).hasMatch(question);
}

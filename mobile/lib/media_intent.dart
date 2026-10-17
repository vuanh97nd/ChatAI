import 'live_search.dart';

/// Route explicit creation requests only; questions about pictures remain chat.
bool isMediaCreationRequest(String text) => !RegExp(r'\b(nhu the nao|la gi|how to)\b').hasMatch(foldVietnamese(text)) && RegExp(
  r'^(?:(?:hay|vui long|lam on|ban)\s+)*(?:tao|ve|thiet ke|generate|create|draw)\s+(?:(?:cho (?:toi|minh)|giup (?:toi|minh)|mot|1|buc|tam|hinh)\s+)*(?:anh|hinh|tranh|video|image|picture)\b',
).hasMatch(foldVietnamese(text.trim()));

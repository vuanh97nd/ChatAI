"""
Chuẩn hóa ngôn ngữ đầu vào tiếng Việt: viết tắt, teen-speak, lỗi dấu phổ biến.
Không thay đổi câu gốc; trả về bản mở rộng và danh sách các từ viết tắt phát hiện được.
"""
import re
import unicodedata

# Viết tắt teen-speak tiếng Việt phổ biến
_ABBREV: dict[str, str] = {
    # Phủ định
    'k': 'không', 'ko': 'không', 'hok': 'không', 'hk': 'không', 'hem': 'không', 'hum': 'không',
    # Được / làm
    'đc': 'được', 'dc': 'được', 'dk': 'được',
    'lm': 'làm', 'lam': 'làm',
    # Đại từ
    'mk': 'mình', 'mik': 'mình', 'tui': 'tôi', 'tao': 'tôi',
    'bn': 'bạn', 'mày': 'bạn', 'bồ': 'bạn',
    # Trợ từ / hư từ
    'r': 'rồi', 'rùi': 'rồi', 'roi': 'rồi',
    'cx': 'cũng', 'cg': 'cũng',
    'vs': 'với', 'voi': 'với',
    'nx': 'nữa', 'nua': 'nữa',
    'ns': 'nói sao', 'nt': 'nhắn tin',
    # Thời gian
    'h': 'giờ', 'bh': 'bây giờ', 'bgio': 'bây giờ', 'bjo': 'bao giờ',
    'trc': 'trước', 'truoc': 'trước',
    # Câu hỏi
    'ntn': 'như thế nào', 'tnao': 'thế nào', 'sao v': 'sao vậy', 'sao z': 'sao vậy',
    # Địa danh
    'hn': 'Hà Nội', 'hcm': 'Hồ Chí Minh', 'vn': 'Việt Nam', 'sg': 'Sài Gòn',
    # Nghề / học
    'sv': 'sinh viên', 'hs': 'học sinh', 'gv': 'giáo viên', 'gd': 'gia đình',
    # Công nghệ
    'mt': 'máy tính', 'dt': 'điện thoại', 'đt': 'điện thoại',
    'ud': 'ứng dụng', 'app': 'ứng dụng',
    'pc': 'máy tính để bàn', 'laptop': 'máy tính xách tay',
    # Cảm ơn / chào
    'tks': 'cảm ơn', 'ty': 'cảm ơn', 'thk': 'cảm ơn',
    # Xác nhận
    'ok': 'được rồi', 'oki': 'được rồi', 'okie': 'được rồi',
    # Viết tắt thông dụng
    'tp': 'thành phố', 'qtr': 'quan trọng', 'tl': 'tài liệu',
    'hd': 'hướng dẫn', 'hdsd': 'hướng dẫn sử dụng',
    'sp': 'sản phẩm', 'kh': 'khách hàng',
    'ad': 'quản trị viên',
    'pv': 'phỏng vấn', 'cv': 'hồ sơ xin việc',
    'ck': 'chồng', 'vk': 'vợ',
    # Viết không dấu phổ biến → có dấu
    'khong': 'không', 'duoc': 'được', 'ban': 'bạn', 'minh': 'mình',
    'lam': 'làm', 'roi': 'rồi', 'cung': 'cũng', 'voi': 'với',
    'truoc': 'trước', 'sau': 'sau', 'bay gio': 'bây giờ',
    'the nao': 'thế nào', 'nhu the nao': 'như thế nào',
    'ha noi': 'Hà Nội', 'ho chi minh': 'Hồ Chí Minh', 'viet nam': 'Việt Nam',
}

# Các mẫu lỗi chính tả tiếng Việt (cặp sai→đúng, dùng regex)
_TYPO_PATTERNS: list[tuple[str, str]] = [
    # Lẫn lộn cuối từ phổ biến
    (r'\bchũ\b', 'chữ'),
    (r'\bnhũng\b', 'những'),
    (r'\bđúng\b', 'đúng'),   # thường đúng nhưng hay bị bỏ dấu
    (r'\bsữ dụng\b', 'sử dụng'),
    (r'\bthưc\b', 'thực'),
    (r'\bthưc hiện\b', 'thực hiện'),
    (r'\bthưc ra\b', 'thực ra'),
    (r'\bkiêm tra\b', 'kiểm tra'),
    (r'\bcài đăt\b', 'cài đặt'),
    (r'\bkêt quả\b', 'kết quả'),
    (r'\bkêt nối\b', 'kết nối'),
    (r'\bhê thống\b', 'hệ thống'),
    (r'\btài liêu\b', 'tài liệu'),
    (r'\btên lửa\b', 'tên lửa'),  # ok
    (r'\bứng dung\b', 'ứng dụng'),
    (r'\bphân mêm\b', 'phần mềm'),
    (r'\bphân tích\b', 'phân tích'),  # ok
    (r'\bthêm vào\b', 'thêm vào'),   # ok
    (r'\bxư lý\b', 'xử lý'),
    (r'\bxu ly\b', 'xử lý'),
    (r'\bdư liêu\b', 'dữ liệu'),
    (r'\bdư liệu\b', 'dữ liệu'),
    (r'\btai liêu\b', 'tài liệu'),
]

# Từ viết tắt chỉ mở rộng khi đứng tách biệt (không phải một phần từ khác)
_WORD_BOUNDARY = re.compile(r'(?<!\w)({})(?!\w)', re.I)


def _fold(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để so sánh không phân biệt dấu."""
    text = unicodedata.normalize('NFKD', text.casefold()).replace('đ', 'd')
    return ''.join(c for c in text if not unicodedata.combining(c))


def detect_abbreviations(text: str) -> dict[str, str]:
    """
    Trả về dict {từ_gốc: nghĩa} cho các viết tắt phát hiện trong text.
    Không bao giờ thay đổi text gốc.
    """
    found: dict[str, str] = {}
    tokens = re.findall(r"[\wÀ-ỹđĐ']+", text, re.UNICODE)
    for token in tokens:
        key = token.lower()
        if key in _ABBREV:
            found[token] = _ABBREV[key]
        else:
            # thử không dấu
            folded = _fold(token)
            if folded in _ABBREV and folded != key:
                found[token] = _ABBREV[folded]
    return found


def expand_for_ai(text: str) -> tuple[str, list[str]]:
    """
    Tạo bản mở rộng các viết tắt trong text để gửi kèm cho AI như ngữ cảnh.
    Trả về (bản_mở_rộng, danh_sách_mô_tả_thay_thế).
    Không dùng để ghi đè câu gốc của người dùng.
    """
    abbrevs = detect_abbreviations(text)
    if not abbrevs:
        return text, []

    expanded = text
    notes: list[str] = []
    for original, meaning in abbrevs.items():
        # Chỉ mở rộng từ đứng độc lập
        pattern = re.compile(r'(?<!\w)' + re.escape(original) + r'(?!\w)', re.I | re.UNICODE)
        expanded = pattern.sub(meaning, expanded)
        notes.append(f'"{original}" = "{meaning}"')
    return expanded, notes


def abbreviation_hint(text: str) -> str:
    """
    Trả về chuỗi gợi ý ngắn để chèn vào system prompt nếu phát hiện viết tắt.
    Trả về chuỗi rỗng nếu không cần.
    """
    _, notes = expand_for_ai(text)
    if not notes:
        return ''
    return 'Người dùng dùng viết tắt: ' + '; '.join(notes) + '. Hãy hiểu và trả lời theo ngữ cảnh.'


def fix_common_typos(text: str) -> str:
    """
    Sửa các lỗi chính tả tiếng Việt phổ biến trong text.
    Chỉ sửa các lỗi đã biết chắc chắn, không đoán mò.
    Dùng kết quả này để log/debug, không thay thế câu gốc.
    """
    result = text
    for pattern, replacement in _TYPO_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.I | re.UNICODE)
    return result


def normalize_user_input(text: str) -> dict:
    """
    Phân tích đầy đủ văn bản đầu vào.
    Trả về dict với:
      - original: câu gốc
      - expanded: bản mở rộng viết tắt
      - typo_fixed: bản sửa lỗi chính tả
      - abbreviations: dict {từ: nghĩa}
      - hint: chuỗi gợi ý cho AI (chèn vào system prompt)
      - has_abbrev: bool
    """
    expanded, notes = expand_for_ai(text)
    typo_fixed = fix_common_typos(text)
    abbrevs = detect_abbreviations(text)
    return {
        'original': text,
        'expanded': expanded,
        'typo_fixed': typo_fixed,
        'abbreviations': abbrevs,
        'hint': abbreviation_hint(text),
        'has_abbrev': bool(abbrevs),
    }

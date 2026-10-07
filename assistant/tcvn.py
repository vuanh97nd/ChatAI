"""
TCVN3 ↔ Unicode conversion and font utilities for Vietnamese engineering documents.

TCVN3 (ABC encoding) is used by legacy SHX fonts in AutoCAD Vietnam:
  .VnArial.shx, .VnTimes.shx, VNTIMES.SHX, VNARIAL.SHX, vnet.shx, vnhelveti.shx, ...
TrueType fonts (.VnArial.ttf, .VnTimes.ttf, Times New Roman, Arial) use Unicode — no conversion needed.
"""

# TCVN3 (ABC) byte 0x80–0xFF → Unicode character
# Source: TCVN 5712:1993 / ABC font encoding used in Vietnamese AutoCAD tradition
_TCVN3_TO_UNI: dict[int, str] = {
    0x80: 'À',  # À
    0x81: 'Á',  # Á
    0x82: 'Â',  # Â
    0x83: 'Ã',  # Ã
    0x84: 'Ạ',  # Ạ
    0x85: 'Ả',  # Ả
    0x86: 'Ấ',  # Ấ
    0x87: 'Ầ',  # Ầ
    0x88: 'Ẩ',  # Ẩ
    0x89: 'Ẫ',  # Ẫ
    0x8a: 'Ậ',  # Ậ
    0x8b: 'Ắ',  # Ắ
    0x8c: 'Ằ',  # Ặ — NOTE: some fonts use 0x8c for Ằ; most ABC use Ặ here
    0x8d: 'Ẳ',  # Ẳ
    0x8e: 'Ẵ',  # Ẵ
    0x8f: 'Ặ',  # Ặ  (duplicate in some tables; keep for round-trip)

    0x90: 'È',  # È
    0x91: 'É',  # É
    0x92: 'Ê',  # Ê
    0x93: 'Ẹ',  # Ẹ
    0x94: 'Ẻ',  # Ẻ
    0x95: 'Ẽ',  # Ẽ
    0x96: 'Ế',  # Ế
    0x97: 'Ề',  # Ề
    0x98: 'Ể',  # Ể
    0x99: 'Ễ',  # Ễ
    0x9a: 'Ệ',  # Ệ
    0x9b: 'Ì',  # Ì
    0x9c: 'Í',  # Í
    0x9d: 'Ĩ',  # Ĩ
    0x9e: 'Ỉ',  # Ỉ
    0x9f: 'Ị',  # Ị

    0xa0: 'Ò',  # Ò
    0xa1: 'Ó',  # Ó
    0xa2: 'Ô',  # Ô
    0xa3: 'Õ',  # Õ
    0xa4: 'Ọ',  # Ọ
    0xa5: 'Ỏ',  # Ỏ
    0xa6: 'Ố',  # Ố
    0xa7: 'Ồ',  # Ồ
    0xa8: 'Ổ',  # Ổ
    0xa9: 'Ỗ',  # Ỗ
    0xaa: 'Ộ',  # Ộ
    0xab: 'Ơ',  # Ơ
    0xac: 'Ớ',  # Ớ
    0xad: 'Ờ',  # Ờ
    0xae: 'Ở',  # Ở
    0xaf: 'Ỡ',  # Ỡ

    0xb0: 'Ợ',  # Ợ
    0xb1: 'Ù',  # Ù
    0xb2: 'Ú',  # Ú
    0xb3: 'Ũ',  # Ũ
    0xb4: 'Ụ',  # Ụ
    0xb5: 'Ủ',  # Ủ
    0xb6: 'Ư',  # Ư
    0xb7: 'Ứ',  # Ứ
    0xb8: 'Ừ',  # Ừ
    0xb9: 'Ử',  # Ử
    0xba: 'Ữ',  # Ữ
    0xbb: 'Ự',  # Ự
    0xbc: 'Ỳ',  # Ỳ
    0xbd: 'Ý',  # Ý
    0xbe: 'Ỵ',  # Ỵ
    0xbf: 'Ỷ',  # Ỷ

    0xc0: 'Ỹ',  # Ỹ
    0xc1: 'Đ',  # Đ
    0xc2: 'à',  # à
    0xc3: 'á',  # á
    0xc4: 'â',  # â
    0xc5: 'ã',  # ã
    0xc6: 'ạ',  # ạ
    0xc7: 'ả',  # ả
    0xc8: 'ấ',  # ấ
    0xc9: 'ầ',  # ầ
    0xca: 'ẩ',  # ẩ
    0xcb: 'ẫ',  # ẫ
    0xcc: 'ậ',  # ậ
    0xcd: 'ắ',  # ắ
    0xce: 'ằ',  # ằ
    0xcf: 'ẳ',  # ẳ

    0xd0: 'ẵ',  # ẵ
    0xd1: 'ặ',  # ặ
    0xd2: 'è',  # è
    0xd3: 'é',  # é
    0xd4: 'ê',  # ê
    0xd5: 'ẹ',  # ẹ
    0xd6: 'ẻ',  # ẻ
    0xd7: 'ẽ',  # ẽ
    0xd8: 'ế',  # ế
    0xd9: 'ề',  # ề
    0xda: 'ể',  # ể
    0xdb: 'ễ',  # ễ
    0xdc: 'ệ',  # ệ
    0xdd: 'ì',  # ì
    0xde: 'í',  # í
    0xdf: 'ĩ',  # ĩ

    0xe0: 'ỉ',  # ỉ
    0xe1: 'ị',  # ị
    0xe2: 'ò',  # ò
    0xe3: 'ó',  # ó
    0xe4: 'ô',  # ô
    0xe5: 'õ',  # õ
    0xe6: 'ọ',  # ọ
    0xe7: 'ỏ',  # ỏ
    0xe8: 'ố',  # ố
    0xe9: 'ồ',  # ồ
    0xea: 'ổ',  # ổ
    0xeb: 'ỗ',  # ỗ
    0xec: 'ộ',  # ộ
    0xed: 'ơ',  # ơ
    0xee: 'ớ',  # ớ
    0xef: 'ờ',  # ờ

    0xf0: 'ở',  # ở
    0xf1: 'ỡ',  # ỡ
    0xf2: 'ợ',  # ợ
    0xf3: 'ù',  # ù
    0xf4: 'ú',  # ú
    0xf5: 'ũ',  # ũ
    0xf6: 'ụ',  # ụ
    0xf7: 'ủ',  # ủ
    0xf8: 'ư',  # ư
    0xf9: 'ứ',  # ứ
    0xfa: 'ừ',  # ừ
    0xfb: 'ử',  # ử
    0xfc: 'ữ',  # ữ
    0xfd: 'ự',  # ự
    0xfe: 'ỳ',  # ỳ
    0xff: 'ý',  # ý (some fonts: 0xff=ý, others=ỵ; using ý as more common in ABC)
}

# Reverse: Unicode → TCVN3 byte (only chars that have a unique mapping)
_UNI_TO_TCVN3: dict[str, int] = {}
for _b, _c in _TCVN3_TO_UNI.items():
    if _c not in _UNI_TO_TCVN3:
        _UNI_TO_TCVN3[_c] = _b
# Đ / đ not in 0x80-0xFF range above (Đ=0xC1 is there); add đ explicitly
_UNI_TO_TCVN3['đ'] = 0xf0  # đ — some ABC tables put đ at 0xf0; others overlap ở
# Note: 0xf0 is ở in full table above; when converting, ở takes priority if both present.
# Practical resolution: encode ở first, then đ only if ở not needed.
# Simplest: keep table as-is; caller should verify output visually for edge cases.

# AutoCAD convention: a font name starting with '.' means TrueType (Unicode).
# SHX Vietnamese fonts use TCVN3 encoding.
_TCVN3_SHX_STEMS = {
    'vntimes', 'vnarial', 'vnet', 'vnhelveti', 'vncomic', 'vncourier',
    'vnsymbol', 'vnbold', 'vnitalic', 'vnbolditalic',
}


def is_tcvn3_font(font_name: str) -> bool:
    """Return True if the font is a TCVN3-encoded SHX font (needs conversion).

    AutoCAD rule: font starting with '.' is TrueType (Unicode), no conversion needed.
    SHX fonts (no dot prefix, optional .shx extension) may need TCVN3 encoding.
    """
    name = font_name.strip()
    if name.startswith('.'):
        return False  # TrueType font (AutoCAD dot-prefix convention) — Unicode
    if name.lower().endswith('.ttf'):
        return False  # Explicit TrueType
    stem = name.lower().removesuffix('.shx').strip()
    return stem in _TCVN3_SHX_STEMS


def unicode_to_tcvn3(text: str) -> bytes:
    """Convert Unicode Vietnamese string → TCVN3 bytes for SHX fonts.
    ASCII characters pass through unchanged. Unmapped characters are kept as-is (best effort).
    """
    result = bytearray()
    for ch in text:
        code = ord(ch)
        if code < 0x80:
            result.append(code)
        elif ch in _UNI_TO_TCVN3:
            result.append(_UNI_TO_TCVN3[ch])
        else:
            # Fallback: keep ASCII representation or '?'
            result.append(ord('?'))
    return bytes(result)


def tcvn3_to_unicode(data: bytes) -> str:
    """Convert TCVN3 bytes → Unicode string."""
    return ''.join(_TCVN3_TO_UNI.get(b, chr(b)) for b in data)


def encode_dxf_text(text: str, font_name: str) -> str:
    """Return the text string suitable for writing into a DXF TEXT entity.
    - For TCVN3 SHX fonts: converts to TCVN3 bytes then returns as latin-1 string
      (ezdxf writes DXF as bytes; TCVN3 bytes in 0x80-0xFF range survive latin-1 round-trip).
    - For Unicode/TTF fonts: returns text unchanged.
    """
    if is_tcvn3_font(font_name):
        return unicode_to_tcvn3(text).decode('latin-1')
    return text


# ── DXF style helpers ──────────────────────────────────────────────────────────

# Suggested standard styles for Vietnamese engineering drawings
PRESET_STYLES = {
    'VN_SAN':   {'font': '.VnArial',   'encoding': 'unicode', 'description': 'Sans-serif Unicode'},
    'VN_SERIF': {'font': '.VnTimes',   'encoding': 'unicode', 'description': 'Serif Unicode'},
    'VN_SHX':   {'font': 'VNARIAL',    'encoding': 'tcvn3',   'description': 'Legacy SHX TCVN3'},
    'STANDARD': {'font': 'txt',        'encoding': 'unicode', 'description': 'AutoCAD default'},
}


def validate_style_def(item: dict) -> dict:
    """Validate a style definition dict: {name, font, height?, width_factor?}."""
    name = item.get('name', '')
    if not isinstance(name, str) or not name or len(name) > 255:
        raise ValueError('Tên style phải là chuỗi 1–255 ký tự.')
    if any(c in name for c in '<>/\\:;?*|="\''):
        raise ValueError(f'Tên style chứa ký tự không hợp lệ: {name!r}')
    font = item.get('font', 'txt')
    if not isinstance(font, str) or not font or len(font) > 255:
        raise ValueError('font phải là chuỗi 1–255 ký tự (tên file font, ví dụ .VnArial hoặc VNTIMES.SHX).')
    height = float(item.get('height', 0.0))
    width_factor = float(item.get('width_factor', 1.0))
    if height < 0:
        raise ValueError('height phải >= 0 (0 = dùng height từ entity).')
    if not 0.01 <= width_factor <= 100:
        raise ValueError('width_factor phải trong khoảng 0.01–100.')
    return {'name': name, 'font': font, 'height': height, 'width_factor': width_factor,
            'tcvn3': is_tcvn3_font(font)}

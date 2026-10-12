"""Slash-command templates for AutoCAD drawing workflows.

Usage: user types /cdm, /tracdoc, /mcn, /tru, /xldy alone → expanded to a
ready-to-fill template so they only need to supply numbers.
"""

SLASH_COMMANDS: dict[str, str] = {
    "/cdm": (
        "Vẽ sơ đồ bố trí cọc CDM với thông số sau:\n"
        "- Chiều rộng nền đường B = [m]\n"
        "- Chiều dài đoạn xử lý L = [m]\n"
        "- Đường kính cọc D = [m]  (thường 0.6–1.0 m)\n"
        "- Chiều sâu xử lý = [m]\n"
        "- Khoảng cách cọc theo tim đường: [m]\n"
        "- Khoảng cách cọc ngang tim đường: [m]\n"
        "- Đơn vị bản vẽ: m\n\n"
        "(Thay các giá trị [m] bằng số thực tế rồi gửi)"
    ),
    "/tracdoc": (
        "Vẽ trắc dọc tuyến đường với dữ liệu sau:\n"
        "Tên dự án: [tên tuyến đường]\n"
        "Tỷ lệ ngang: 1:[H_scale]  (thường 1000 hoặc 2000)\n"
        "Tỷ lệ đứng:  1:[V_scale]  (thường 100 hoặc 200)\n\n"
        "Lý trình  | Cao độ TN | Cao độ TK\n"
        "KM0+000   | [TN]      | [TK]\n"
        "KM0+100   | [TN]      | [TK]\n"
        "KM0+200   | [TN]      | [TK]\n\n"
        "(Điền đầy đủ cột TN và TK theo từng cọc rồi gửi)"
    ),
    "/mcn": (
        "Vẽ mặt cắt ngang XLDY cho đoạn xử lý đất yếu:\n"
        "Tên đoạn: [tên]\n"
        "Lý trình: KM[start] – KM[end]\n"
        "Phương pháp xử lý: [PVD / CDM / ĐÀO THAY / CỌC TRE / CỪ TRÀM]\n"
        "Chiều rộng nền đường B_nen = [m]\n"
        "Chiều cao đắp H_dap = [m]\n"
        "Chiều sâu lớp đất yếu H_yeu = [m]\n"
        "Khoảng cách bố trí (nếu PVD/CDM): s = [m]\n\n"
        "(Điền thông số thực tế rồi gửi)"
    ),
    "/tru": (
        "Vẽ trụ địa chất (hố khoan) với thông tin sau:\n"
        "Tên hố khoan: [BH-1]\n"
        "Cao độ mặt đất: [m]\n"
        "Mực nước ngầm: [m] (tính từ mặt đất)\n\n"
        "Lớp đất (từ trên xuống):\n"
        "1. Tên lớp: [Bùn sét/Cát/Sét...], Dày: [m], "
        "γ=[kN/m³], e₀=[...], Cc=[...], c=[kPa], φ=[°], N-SPT=[...]\n"
        "2. Tên lớp: [...], Dày: [m], ...\n\n"
        "(Điền đầy đủ thông số từng lớp rồi gửi)"
    ),
    "/xldy": (
        "Phân tích và vẽ bản vẽ XLDY (xử lý đất yếu) cho tuyến đường:\n"
        "File trắc dọc DXF: [đường dẫn .dxf]\n"
        "File mặt cắt ngang DXF: [đường dẫn .dxf]\n"
        "File Excel THSH mẫu: [đường dẫn .xlsx]\n\n"
        "Hố khoan:\n"
        "BH-1 tại cọc K[lý trình], cao độ mặt đất [m], mực nước [m]\n"
        "  Lớp 1: [Bùn sét], dày [m], γ=[...], e₀=[...], Cc=[...]\n"
        "  Lớp 2: [Sét cứng], dày [m], γ=[...], e₀=[...]\n\n"
        "(Thay thông tin thực tế rồi gửi để AI phân tích và xuất DXF + Excel)"
    ),
    "/cad": (
        "Vẽ bản vẽ 2D AutoCAD với các đối tượng sau:\n"
        "(Mô tả hình vẽ, ví dụ:)\n"
        "- Line từ (0,0) đến (10,0)\n"
        "- Circle tâm (5,5) bán kính 3\n"
        "- Text 'TÊN BẢN VẼ' tại (5,10) cỡ chữ 0.5\n"
        "Layer: [tên layer]\n"
        "Tên file: [tên file .dxf]\n\n"
        "(Mô tả bản vẽ thực tế rồi gửi)"
    ),
}


def expand_slash(text: str) -> str | None:
    """Return expanded template if text is a known slash command, else None."""
    key = text.strip().lower().split()[0] if text.strip() else ""
    # Only expand when user typed the command alone (no extra content)
    if text.strip().lower() in SLASH_COMMANDS:
        return SLASH_COMMANDS[text.strip().lower()]
    return None


CAD_FOLLOWUPS = [
    ("Vẽ CDM", "/cdm"),
    ("Trắc dọc", "/tracdoc"),
    ("Mặt cắt XLDY", "/mcn"),
]

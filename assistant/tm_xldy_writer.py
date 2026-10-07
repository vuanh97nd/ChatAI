"""Thuyết minh xử lý đất yếu (XLDY) Word writer.

Generates a design report (thuyết minh) following the TMXLDY-VD4 template:
  Chương I   – Giới thiệu chung
  Chương II  – Các cơ sở tính toán
  Chương III – Lý thuyết và công thức tính toán
  Chương IV  – Giải pháp và kết quả tính toán
  Chương V   – Quan trắc tại hiện trường

Treatment methods supported: CDM, PVD, SD, Đào thay, Cọc tre, Cừ tràm.
"""
from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from docx import Document
    from docx.shared import Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_ALIGN_VERTICAL
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    import docx
    _DOCX_OK = True
except ImportError:
    _DOCX_OK = False


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

def _set_heading(para, level: int = 1):
    para.style = f"Heading {level}"


def _bold(run): run.bold = True


def _set_font(run, name="Times New Roman", size_pt=12):
    run.font.name = name
    run.font.size = Pt(size_pt)


def _para(doc, text="", bold=False, size=12, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p = doc.add_paragraph()
    p.alignment = align
    run = p.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    run.bold = bold
    return p


def _chapter(doc, number: str, title: str):
    p = doc.add_heading(level=1)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"CHƯƠNG {number}\n{title.upper()}")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.bold = True
    return p


def _section(doc, number: str, title: str):
    p = doc.add_heading(level=2)
    run = p.add_run(f"{number}. {title}")
    run.font.name = "Times New Roman"
    run.font.size = Pt(12)
    run.bold = True
    return p


def _subsection(doc, number: str, title: str):
    p = doc.add_heading(level=3)
    run = p.add_run(f"{number} {title}")
    run.font.name = "Times New Roman"
    run.font.size = Pt(12)
    run.bold = True
    run.italic = True
    return p


def _add_table_row(table, cells, bold=False):
    row = table.add_row()
    for ci, val in enumerate(cells):
        cell = row.cells[ci]
        cell.text = str(val) if val is not None else ""
        for para in cell.paragraphs:
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in para.runs:
                run.font.name = "Times New Roman"
                run.font.size = Pt(10)
                run.bold = bold
    return row


def _shade_row(row, hex_color="D9E1F2"):
    for cell in row.cells:
        tc_pr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), hex_color)
        tc_pr.append(shd)


# ---------------------------------------------------------------------------
# Chapter content generators
# ---------------------------------------------------------------------------

def _chapter1(doc, meta: dict):
    _chapter(doc, "I", "GIỚI THIỆU CHUNG")
    _section(doc, "1.1", "Tổng quan dự án")
    _para(doc, (
        f"Dự án: {meta.get('project_name', '[Tên dự án]')}. "
        f"Đoạn thiết kế từ {meta.get('sta_from', 'KM?+???')} đến "
        f"{meta.get('sta_to', 'KM?+???')}, chiều dài "
        f"{meta.get('route_length_km', '?')} km. "
        "Khu vực có đất yếu (sét/bụi hữu cơ trạng thái dẻo chảy đến dẻo mềm) "
        "phân bố dọc theo tuyến, cần có biện pháp xử lý phù hợp."
    ))
    _section(doc, "1.2", "Mục tiêu thiết kế")
    _para(doc, (
        "Mục tiêu của báo cáo thuyết minh tính toán xử lý đất yếu nhằm:"
    ))
    for item in [
        "Đánh giá hiện trạng địa kỹ thuật của nền đất yếu dọc tuyến;",
        "Lựa chọn giải pháp xử lý phù hợp theo điều kiện địa chất, chiều cao đắp và yêu cầu kỹ thuật;",
        "Tính toán khối lượng, thông số kỹ thuật và thời gian thi công;",
        "Đề xuất chương trình quan trắc trong và sau thi công.",
    ]:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(item).font.name = "Times New Roman"

    _section(doc, "1.3", "Phạm vi áp dụng")
    _para(doc, (
        f"Thuyết minh áp dụng cho {meta.get('n_segments', '?')} đoạn xử lý đất yếu, "
        f"tổng chiều dài {meta.get('total_length_m', '?')} m, "
        f"gồm các biện pháp: {meta.get('methods_used', 'CDM, PVD, Đào thay, Cọc tre')}."
    ))
    _section(doc, "1.4", "Căn cứ pháp lý và tài liệu áp dụng")
    for ref in [
        "TCVN 9362:2012 – Thiết kế nền nhà và công trình;",
        "TCVN 9403:2012 – Gia cố đất nền yếu bằng trụ đất xi măng;",
        "TCVN 9355:2012 – Gia cố nền đất yếu bằng bấc thấm thoát nước;",
        "22TCN 262-2000 – Quy trình khảo sát thiết kế nền đường ô tô đắp trên đất yếu;",
        "TCVN 9351:2012 – Đất xây dựng – Phương pháp thí nghiệm hiện trường;",
        "Kết quả khảo sát địa chất công trình của dự án.",
    ]:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(ref).font.name = "Times New Roman"


def _chapter2(doc, boreholes: list[dict], soil_params: list[dict]):
    _chapter(doc, "II", "CÁC CƠ SỞ TÍNH TOÁN")
    _section(doc, "2.1", "Tiêu chuẩn thiết kế")
    _para(doc, (
        "Các tiêu chí kiểm toán theo 22TCN 262-2000 và TCVN 9362:2012:"
    ))
    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    hdr = _add_table_row(table, ["Tiêu chí", "Yêu cầu", "Ghi chú"], bold=True)
    _shade_row(hdr, "D9E1F2")
    criteria = [
        ("Độ lún sau thi công", "≤ 30 cm (đắp thường), ≤ 20 cm (cống)", "22TCN 262-2000"),
        ("Độ lún còn lại cạnh mố cầu", "≤ 10 cm", ""),
        ("Hệ số ổn định thi công", "Kj ≥ 1.2", "TCVN 9362:2012"),
        ("Hệ số ổn định khai thác", "Kj ≥ 1.4", ""),
        ("Tốc độ lún", "≤ 10 mm/ngày", "Quan trắc"),
        ("Chuyển vị ngang", "≤ 5 mm/ngày", "Quan trắc"),
    ]
    for row_data in criteria:
        _add_table_row(table, row_data)

    _section(doc, "2.2", "Đặc trưng tính toán của đất nền")
    _para(doc, "Bảng 1. Chỉ tiêu cơ lý đất yếu dùng cho tính toán:")
    if soil_params:
        cols = ["Lớp", "Mô tả", "γ (kN/m³)", "Su (kPa)", "e₀", "Cc", "Cs", "Cv (×10⁻³ cm²/s)", "Pc (T/m²)"]
        table2 = doc.add_table(rows=1, cols=len(cols))
        table2.style = "Table Grid"
        hdr2 = _add_table_row(table2, cols, bold=True)
        _shade_row(hdr2, "D9E1F2")
        for sp in soil_params:
            _add_table_row(table2, [
                sp.get("code", ""), sp.get("description", ""),
                sp.get("gamma", ""), sp.get("Su", ""),
                sp.get("e0", ""), sp.get("Cc", ""),
                sp.get("Cs", ""), sp.get("Cv", ""),
                sp.get("Pc", ""),
            ])
    else:
        _para(doc, "(Xem hồ sơ khảo sát địa chất đính kèm)")


def _chapter3(doc, methods: set[str]):
    _chapter(doc, "III", "LÝ THUYẾT VÀ CÔNG THỨC TÍNH TOÁN")
    _section(doc, "3.1", "Thông số yêu cầu và điều kiện áp dụng")

    conditions = {
        "CDM": "hdy > 8m: Dùng cọc đất xi măng (CDM), D=800mm, khoảng cách 1.6–2.5m.",
        "PVD": "hdy 3–8m: Dùng bấc thấm PVD kết hợp gia tải trước, khoảng cách 1.2–1.5m.",
        "SD":  "hdy 3–8m (đất cát): Dùng giếng cát (SD) kết hợp gia tải trước, D=300–400mm.",
        "ĐÀO THAY": "hdy ≤ 3m: Đào bỏ lớp đất yếu, thay bằng cát đầm chặt K95, max 4m.",
        "CỌC TRE":  "hdy ≤ 1.5m, htk < 1.5m: Cọc tre L≤3m, mật độ 16–25 cọc/m².",
        "CỪ TRÀM":  "hdy ≤ 2.5m, htk < 2m: Cừ tràm L≤4m, khoảng cách 0.8–1.0m.",
    }
    for m, cond in conditions.items():
        if m in methods:
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(cond).font.name = "Times New Roman"

    _section(doc, "3.2", "Công thức tính toán")
    _subsection(doc, "3.2.1", "Tính lún cố kết (phương pháp Terzaghi)")
    _para(doc, "Độ lún cố kết sơ cấp tính theo công thức:")
    _para(doc, "• Đất OC (Pc > P₀): Sc = Cs/(1+e₀) × H × log(Pc/P₀) + Cc/(1+e₀) × H × log((P₀+ΔP)/Pc)")
    _para(doc, "• Đất NC (Pc ≤ P₀): Sc = Cc/(1+e₀) × H × log((P₀+ΔP)/P₀)")
    _para(doc, "Trong đó: Cc – chỉ số nén lún; Cs – chỉ số nở; e₀ – hệ số rỗng ban đầu; "
               "H – chiều dày lớp đất; P₀ – áp lực hữu hiệu ban đầu; "
               "ΔP = γtt × Htk (ứng suất do đắp); Pc – áp lực tiền cố kết.")

    _subsection(doc, "3.2.2", "Kiểm toán ổn định (Phương pháp Bishop đơn giản)")
    _para(doc, "Hệ số ổn định mái dốc:")
    _para(doc, "Fs = 5.14 × Su_tb / (γ_đắp × Htk)  [ước lượng bảo thủ]")
    _para(doc, "Yêu cầu: Fs ≥ 1.2 (thi công), Fs ≥ 1.4 (khai thác).")

    if "CDM" in methods:
        _subsection(doc, "3.2.3", "Tính toán cọc CDM")
        _para(doc, "Tỷ diện thay thế: ap = As/A = π×D²/(4×a²) (lưới vuông)")
        _para(doc, "Ứng suất đầu cọc: σp = γ_đắp × Htk / ap")
        _para(doc, "Kiểm tra cường độ: σp / ap ≤ [qu] = qu90/Fs  (Fs = 1.2)")
        _para(doc, "Mô đun nền tương đương: Ech = ap×Ec + (1-ap)×Es")
        _para(doc, "Độ lún vùng gia cố: S1 = q×Lgc/Ech")

    if "PVD" in methods or "SD" in methods:
        _subsection(doc, "3.2.4", "Tính toán cố kết với thoát nước thẳng đứng (Hansbo)")
        _para(doc, "Mức độ cố kết theo phương ngang (Hansbo 1981):")
        _para(doc, "Uh = 1 – exp(–8Th/F(n));  F(n) = ln(n) – 3/4  (n = de/dw)")
        _para(doc, "de = 1.13×d (lưới vuông); de = 1.05×d (lưới tam giác)")
        _para(doc, "Kết hợp Carrillo: U = 1 – (1–Uv)(1–Uh)")


def _chapter4(doc, segments: list[dict]):
    _chapter(doc, "IV", "GIẢI PHÁP VÀ KẾT QUẢ TÍNH TOÁN XỬ LÝ")
    _section(doc, "4.1", "Tổng hợp biện pháp xử lý theo từng đoạn")
    _para(doc, "Bảng 2. Bảng tổng hợp kết quả tính toán xử lý đất yếu:")

    cols = ["TT", "Lý trình", "L (m)", "Htk (m)", "hdy (m)",
            "Biện pháp", "Thông số chính", "Sc (cm)", "St (cm)", "Fs", "Ghi chú"]
    table = doc.add_table(rows=1, cols=len(cols))
    table.style = "Table Grid"
    hdr = _add_table_row(table, cols, bold=True)
    _shade_row(hdr, "D9E1F2")

    for i, seg in enumerate(segments, 1):
        t = (seg.get("treatment") or "").upper()
        spacing = (seg.get("pvd_spacing") or seg.get("pile_spacing") or
                   seg.get("cdm_spacing") or "")
        depth   = (seg.get("pvd_depth") or seg.get("pile_length") or
                   seg.get("excavation_depth") or seg.get("hdy") or "")
        if spacing and depth:
            params = f"a={spacing}m, L={depth}m"
        elif depth:
            params = f"H={depth}m"
        else:
            params = ""
        sta_f = seg.get("station_from", 0)
        sta_t = seg.get("station_to", 0)
        _add_table_row(table, [
            i,
            f"KM{sta_f/1000:.3f}÷{sta_t/1000:.3f}",
            seg.get("length", ""),
            seg.get("htk", ""),
            seg.get("hdy", ""),
            seg.get("treatment", ""),
            params,
            seg.get("Sc", ""),
            seg.get("St", ""),
            seg.get("Fs", ""),
            seg.get("borehole_ref", ""),
        ])

    # Sub-sections per treatment method
    seen_methods: set[str] = set()
    for seg in segments:
        t = (seg.get("treatment") or "").upper()
        if t and t not in seen_methods:
            seen_methods.add(t)

    for method in ["CDM", "PVD", "SD", "ĐÀO THAY", "CỌC TRE", "CỪ TRÀM"]:
        if method not in seen_methods:
            continue
        segs_m = [s for s in segments if (s.get("treatment") or "").upper() == method]
        label = {
            "CDM": "Cọc đất xi măng (CDM)",
            "PVD": "Bấc thấm (PVD)",
            "SD":  "Giếng cát (SD)",
            "ĐÀO THAY": "Đào thay đất",
            "CỌC TRE":  "Cọc tre",
            "CỪ TRÀM":  "Cừ tràm",
        }[method]
        method_order = ["CDM","PVD","SD","ĐÀO THAY","CỌC TRE","CỪ TRÀM"]
        midx = method_order.index(method) + 2 if method in method_order else "x"
        _section(doc, f"4.{midx}", f"Kết quả tính toán – {label}")
        _para(doc, f"Số đoạn áp dụng {label}: {len(segs_m)} đoạn.")
        _method_result_table(doc, method, segs_m)


def _method_result_table(doc, method: str, segs: list[dict]):
    if method == "CDM":
        cols = ["Đoạn", "Lý trình", "n cọc (cọc)", "L cọc (m)", "Σ L (m)",
                "σp (T/m²)", "[qu] (T/m²)", "Vải ĐKT (m²)"]
        table = doc.add_table(rows=1, cols=len(cols))
        table.style = "Table Grid"
        _add_table_row(table, cols, bold=True)
        for i, seg in enumerate(segs, 1):
            from .klxldy_writer import _seg_volumes
            v = _seg_volumes(seg)
            _add_table_row(table, [
                i,
                f"KM{seg.get('station_from',0)/1000:.3f}÷{seg.get('station_to',0)/1000:.3f}",
                v.get("n_coc", ""),
                v.get("cdm_depth", ""),
                v.get("total_len_coc", ""),
                v.get("sigma_p", ""),
                v.get("cdm_qu_allow", ""),
                v.get("vai_dkt_m2", ""),
            ])

    elif method in ("PVD", "SD"):
        label = "bấc thấm" if method == "PVD" else "giếng cát"
        cols = ["Đoạn", "Lý trình", f"n {label} (cái)", f"L {label} (m)",
                f"Σ L (m)", "H gia tải (m)", "Vải ĐKT (m²)"]
        table = doc.add_table(rows=1, cols=len(cols))
        table.style = "Table Grid"
        _add_table_row(table, cols, bold=True)
        for i, seg in enumerate(segs, 1):
            from .klxldy_writer import _seg_volumes
            v = _seg_volumes(seg)
            _add_table_row(table, [
                i,
                f"KM{seg.get('station_from',0)/1000:.3f}÷{seg.get('station_to',0)/1000:.3f}",
                v.get("n_pvd", ""),
                v.get("pvd_depth", ""),
                v.get("total_len_pvd", ""),
                v.get("h_giatai", ""),
                v.get("vai_dkt_m2", ""),
            ])

    elif method == "ĐÀO THAY":
        cols = ["Đoạn", "Lý trình", "Sâu đào (m)", "V đào (m³)", "V lấp cát (m³)", "Vải ĐKT (m²)"]
        table = doc.add_table(rows=1, cols=len(cols))
        table.style = "Table Grid"
        _add_table_row(table, cols, bold=True)
        for i, seg in enumerate(segs, 1):
            from .klxldy_writer import _seg_volumes
            v = _seg_volumes(seg)
            _add_table_row(table, [
                i,
                f"KM{seg.get('station_from',0)/1000:.3f}÷{seg.get('station_to',0)/1000:.3f}",
                v.get("exc_depth", ""),
                v.get("vol_dao", ""),
                v.get("vol_lap_cat", ""),
                v.get("vai_dkt_m2", ""),
            ])

    else:
        label = "cọc tre" if method == "CỌC TRE" else "cừ tràm"
        cols = ["Đoạn", "Lý trình", f"Mật độ (c/m²)", f"L {label} (m)",
                f"n {label} (cọc)", "Σ L (m)", "Vải ĐKT (m²)"]
        table = doc.add_table(rows=1, cols=len(cols))
        table.style = "Table Grid"
        _add_table_row(table, cols, bold=True)
        for i, seg in enumerate(segs, 1):
            from .klxldy_writer import _seg_volumes
            v = _seg_volumes(seg)
            _add_table_row(table, [
                i,
                f"KM{seg.get('station_from',0)/1000:.3f}÷{seg.get('station_to',0)/1000:.3f}",
                v.get("mat_do", ""),
                v.get("pile_length", ""),
                v.get("n_coc", ""),
                v.get("total_len_coc", ""),
                v.get("vai_dkt_m2", ""),
            ])


def _chapter5(doc):
    _chapter(doc, "V", "QUAN TRẮC TẠI HIỆN TRƯỜNG")
    _section(doc, "5.1", "Bàn đo lún mặt (Settlement plate)")
    _para(doc, (
        "Bố trí 3 bàn đo lún/mặt cắt: 1 tại tim tuyến, 2 tại vai đắp, khoảng cách dọc "
        "tuyến ≤ 50m tại các đoạn xử lý. Kích thước bản thép 50×50 cm. "
        "Tần suất đọc: hàng ngày trong thi công, hàng tuần sau khi đắp xong."
    ))
    _section(doc, "5.2", "Quan trắc chuyển vị ngang (Inclinometer / Cọc địa chấn)")
    _para(doc, (
        "Bố trí 6 cọc/mặt cắt (3 mỗi bên), cách chân taluy 1m và 3m, 5m, "
        "khoảng cách dọc ≤ 100m. "
        "Tần suất đọc: hàng ngày trong thi công."
    ))
    _section(doc, "5.3", "Tiêu chí dừng thi công")
    _para(doc, "Dừng thi công và kiểm tra khi:")
    for item in [
        "Tốc độ lún đứng > 10 mm/ngày;",
        "Chuyển vị ngang > 5 mm/ngày;",
        "Hệ số ổn định tính toán Kj < 1.05 (không kể các yếu tố an toàn thiết kế).",
    ]:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(item).font.name = "Times New Roman"


# ---------------------------------------------------------------------------
# Top-level API
# ---------------------------------------------------------------------------

def write_tm_xldy(path: str | Path, segments: list[dict],
                  project_meta: dict | None = None,
                  soil_params: list[dict] | None = None) -> dict:
    """Write thuyết minh XLDY Word document to *path*.

    segments    : list of segment dicts (from road_analyze / road_verify).
    project_meta: {project_name, sta_from, sta_to, route_length_km, ...}
    soil_params : list of soil layer dicts {code, description, gamma, Su, e0, Cc, Cs, Cv, Pc}
    Returns {output_path, pages_estimate, warnings}.
    """
    if not _DOCX_OK:
        raise RuntimeError("python-docx không được cài đặt.")

    path = str(path)
    doc = Document()

    # Page setup A4
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width  = Cm(21.0)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.0)
    section.top_margin   = Cm(2.5)
    section.bottom_margin = Cm(2.5)

    meta = project_meta or {}

    # Derive meta from segments if not provided
    if segments:
        sta_list = [s.get("station_from", 0) for s in segments] + [s.get("station_to", 0) for s in segments]
        meta.setdefault("sta_from", f"KM{min(sta_list)/1000:.3f}")
        meta.setdefault("sta_to",   f"KM{max(sta_list)/1000:.3f}")
        total_len = sum(s.get("length", 0) for s in segments)
        meta.setdefault("route_length_km", round(total_len / 1000, 3))
        meta.setdefault("n_segments", len(segments))
        meta.setdefault("total_length_m", round(total_len, 0))
        methods = {(s.get("treatment") or "").capitalize() for s in segments if s.get("treatment")}
        meta.setdefault("methods_used", ", ".join(sorted(methods)))

    # Title page
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_para.add_run("THUYẾT MINH TÍNH TOÁN\nXỬ LÝ NỀN ĐẤT YẾU (XLDY)")
    run.font.name = "Times New Roman"
    run.font.size = Pt(16)
    run.bold = True

    if meta.get("project_name"):
        _para(doc, meta["project_name"], bold=True, size=13,
              align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_page_break()

    methods_used = {(s.get("treatment") or "").upper() for s in segments if s.get("treatment")}

    _chapter1(doc, meta)
    doc.add_page_break()
    _chapter2(doc, [], soil_params or [])
    doc.add_page_break()
    _chapter3(doc, methods_used)
    doc.add_page_break()
    _chapter4(doc, segments)
    doc.add_page_break()
    _chapter5(doc)

    doc.save(path)
    return {
        "output_path": path,
        "pages_estimate": 15 + len(segments) // 5,
        "warnings": [] if _DOCX_OK else ["python-docx not installed"],
    }

"""Khối lượng xử lý đất yếu (XLDY) Excel writer.

Generates a volume-calculation workbook following the XLDY_THU_THIEM_4 template
with four treatment-method sections:
  I.  CDM (cọc đất xi măng)
  II. PVD / SD (bấc thấm / giếng cát)
  III. Đào thay đất
  IV. Cọc tre / Cừ tràm
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

try:
    import openpyxl
    from openpyxl.styles import (Alignment, Border, Font, PatternFill,
                                  Side, numbers)
    from openpyxl.utils import get_column_letter
except ImportError:
    openpyxl = None  # type: ignore


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TITLE_FONT   = Font(name="Times New Roman", bold=True, size=12)
_HDR_FONT     = Font(name="Times New Roman", bold=True, size=10)
_BODY_FONT    = Font(name="Times New Roman", size=10)
_NUM_FORMAT   = '#,##0.00'
_INT_FORMAT   = '#,##0'

_THIN = Side(style="thin")
_THICK = Side(style="medium")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_BORDER_THICK_LEFT = Border(left=_THICK, right=_THIN, top=_THIN, bottom=_THIN)

_FILL_SECTION = PatternFill("solid", fgColor="D9E1F2")  # blue section header
_FILL_CDM     = PatternFill("solid", fgColor="E2EFDA")  # green CDM
_FILL_PVD     = PatternFill("solid", fgColor="FFF2CC")  # yellow PVD
_FILL_DAO     = PatternFill("solid", fgColor="FCE4D6")  # orange đào thay
_FILL_COC     = PatternFill("solid", fgColor="EDE7F6")  # purple cọc tre

_METHOD_FILL = {
    "CDM":       _FILL_CDM,
    "PVD":       _FILL_PVD,
    "SD":        _FILL_PVD,
    "ĐÀO THAY":  _FILL_DAO,
    "CỌC TRE":   _FILL_COC,
    "CỪ TRÀM":   _FILL_COC,
}

# Geotextile default specs per treatment method
_GEOTEXTILE = {
    "CDM":      "200×200 kN/m",
    "PVD":      "200×50 kN/m",
    "SD":       "200×50 kN/m",
    "ĐÀO THAY": "200×50 kN/m",
    "CỌC TRE":  "200×50 kN/m",
    "CỪ TRÀM":  "200×50 kN/m",
}

CDM_DIAMETER = 0.8        # m
CDM_AREA     = math.pi / 4 * CDM_DIAMETER ** 2   # 0.5027 m²
CDM_QU_ALLOW = 70.0       # T/m²  (= 7 kg/cm²)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _cell(ws, row, col, value=None, font=None, fill=None, align=None,
          border=True, num_format=None):
    c = ws.cell(row=row, column=col, value=value)
    c.font  = font  or _BODY_FONT
    if fill:
        c.fill = fill
    if align:
        c.alignment = align
    if border:
        c.border = _BORDER
    if num_format:
        c.number_format = num_format
    return c


def _hdr(ws, row, col, value, fill=None):
    return _cell(ws, row, col, value, font=_HDR_FONT, fill=fill,
                 align=Alignment(horizontal="center", vertical="center",
                                 wrap_text=True))


def _merge(ws, r1, c1, r2, c2, value=None, font=None, fill=None, align=None):
    ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)
    c = ws.cell(row=r1, column=c1, value=value)
    c.font  = font or _BODY_FONT
    if fill:
        c.fill = fill
    c.alignment = align or Alignment(horizontal="center", vertical="center",
                                     wrap_text=True)
    c.border = _BORDER
    return c


# ---------------------------------------------------------------------------
# Per-segment volume calculations
# ---------------------------------------------------------------------------

def _seg_volumes(seg: dict) -> dict:
    """Return volume calculation results for one segment dict."""
    L        = float(seg.get("length", 0))
    b_nen    = float(seg.get("b_nen") or 12.0)
    htk      = float(seg.get("htk") or 0.0)
    hdy      = float(seg.get("hdy") or 0.0)
    treatment = (seg.get("treatment") or "").upper().strip()

    # Base width for treatment = road base + slope allowance
    b_xl = round(b_nen + 2 * 1.5 * htk + 2.0, 1)  # 1:1.5 taluy + 1m margin

    v: dict[str, Any] = {
        "segment":    seg.get("id"),
        "station_from": seg.get("station_from"),
        "station_to":   seg.get("station_to"),
        "L":    L,
        "b_nen": b_nen,
        "b_xl":  b_xl,
        "htk":   htk,
        "hdy":   hdy,
        "treatment": treatment,
    }

    area = L * b_xl  # m² treatment area

    # Monitoring quantities (common to all methods)
    v["ban_do_lun"] = max(1, round(L / 50))    # 1 plate per 50m
    v["coc_ctv"]    = max(1, round(L / 100))   # 1 lateral stake per 100m

    # -- CDM --
    if treatment == "CDM":
        cdm_spacing = float(seg.get("pvd_spacing") or 2.0)
        cdm_depth   = float(seg.get("pvd_depth") or hdy)
        cdm_top_elev = float(seg.get("design_elev") or 0.0)
        cdm_bot_elev = cdm_top_elev - cdm_depth

        n_coc = math.ceil(area / cdm_spacing ** 2)
        total_len = n_coc * cdm_depth
        n_khoan   = max(1, math.ceil(n_coc * 0.02))
        len_khoan = n_khoan * cdm_depth
        # Stress at pile head (simplified)
        gamma_fill = 18.5  # kN/m³
        ap = CDM_AREA / cdm_spacing ** 2   # area replacement ratio
        sigma_p = gamma_fill * htk / max(ap, 0.01)  # T/m² approx
        p_tk    = round(sigma_p * CDM_AREA, 1)
        p_tn    = round(1.5 * p_tk, 1)

        v.update({
            "cdm_spacing":  cdm_spacing,
            "cdm_depth":    cdm_depth,
            "cdm_top_elev": round(cdm_top_elev, 2),
            "cdm_bot_elev": round(cdm_bot_elev, 2),
            "n_coc":        n_coc,
            "total_len_coc": round(total_len, 0),
            "n_khoan":      n_khoan,
            "len_khoan":    round(len_khoan, 0),
            "vua_lap_ho":   round(n_khoan * math.pi / 4 * 0.1**2 * cdm_depth, 2),
            "n_mau_qu":     round(len_khoan),
            "n_nen_tinh":   n_khoan,
            "sigma_p":      round(sigma_p, 1),
            "cdm_qu_allow": CDM_QU_ALLOW,
            "p_tk":         p_tk,
            "p_tn":         p_tn,
            "vai_dkt_m2":   round(area, 0),
            "geotextile_spec": _GEOTEXTILE["CDM"],
        })

    # -- PVD / SD --
    elif treatment in ("PVD", "SD"):
        pvd_spacing = float(seg.get("pvd_spacing") or 1.5)
        pvd_depth   = float(seg.get("pvd_depth") or hdy)
        # Triangular grid: effective spacing de = 1.05d
        n_pvd = math.ceil(area / (pvd_spacing ** 2 * math.sqrt(3) / 2))
        total_len = n_pvd * pvd_depth
        h_giatai  = round(htk * 0.25, 2)     # surcharge height ~25% fill
        vol_giatai = round(L * b_xl * h_giatai, 0)

        label = "bấc thấm" if treatment == "PVD" else "giếng cát"
        v.update({
            "pvd_label":    label,
            "pvd_spacing":  pvd_spacing,
            "pvd_depth":    pvd_depth,
            "n_pvd":        n_pvd,
            "total_len_pvd": round(total_len, 0),
            "vai_dkt_m2":   round(area, 0),
            "h_giatai":     h_giatai,
            "vol_giatai":   vol_giatai,
            "geotextile_spec": _GEOTEXTILE[treatment],
        })

    # -- Đào thay đất --
    elif treatment == "ĐÀO THAY":
        exc_depth = float(seg.get("excavation_depth") or min(hdy, 4.0))
        vol_dao   = round(L * b_xl * exc_depth, 0)
        vol_lap   = vol_dao   # fill same volume with K95 sand

        v.update({
            "exc_depth":  exc_depth,
            "vol_dao":    vol_dao,
            "vol_lap_cat": vol_lap,
            "vai_dkt_m2": round(area, 0),
            "geotextile_spec": _GEOTEXTILE["ĐÀO THAY"],
        })

    # -- Cọc tre / Cừ tràm --
    elif treatment in ("CỌC TRE", "CỪ TRÀM"):
        pile_length  = float(seg.get("pile_length") or hdy)
        pile_spacing = float(seg.get("pile_spacing") or 0.6)
        pile_length  = min(pile_length, 3.0 if treatment == "CỌC TRE" else 4.0)
        matdo        = round(1 / pile_spacing ** 2, 1)   # cọc/m²
        n_coc        = math.ceil(area * matdo)
        total_len    = round(n_coc * pile_length, 0)

        label = "Cọc tre" if treatment == "CỌC TRE" else "Cừ tràm"
        v.update({
            "pile_label":   label,
            "pile_length":  pile_length,
            "pile_spacing": pile_spacing,
            "mat_do":       matdo,
            "n_coc":        n_coc,
            "total_len_coc": total_len,
            "vai_dkt_m2":   round(area, 0),
            "geotextile_spec": _GEOTEXTILE[treatment],
        })

    return v


# ---------------------------------------------------------------------------
# Sheet writers
# ---------------------------------------------------------------------------

def _write_summary_sheet(wb, segments: list[dict], project_name: str = ""):
    """Sheet 1: THKQ — per-segment summary."""
    ws = wb.create_sheet("THKQ")
    ws.sheet_view.showGridLines = True

    # Title
    _merge(ws, 1, 1, 1, 12,
           f"BẢNG TỔNG HỢP KẾT QUẢ TÍNH TOÁN NỀN ĐẮP TRÊN ĐẤT YẾU",
           font=Font(name="Times New Roman", bold=True, size=13),
           fill=_FILL_SECTION)
    if project_name:
        _merge(ws, 2, 1, 2, 12, f"Dự án: {project_name}",
               font=_HDR_FONT)

    hdr_row = 3
    hdrs = ["TT", "Lý trình\nTừ – Đến", "Chiều dài\n(m)", "Htk\n(m)",
            "hdy\n(m)", "Bn\n(m)", "Bxl\n(m)",
            "Biện pháp\nxử lý",
            "Khoảng cách\nbố trí (m)",
            "Chiều sâu\n(m)",
            "Fs ổn định",
            "Ghi chú"]
    for ci, h in enumerate(hdrs, 1):
        _hdr(ws, hdr_row, ci, h, fill=_FILL_SECTION)
    ws.row_dimensions[hdr_row].height = 36

    for i, seg in enumerate(segments, 1):
        r = hdr_row + i
        vols = _seg_volumes(seg)
        spacing = (vols.get("cdm_spacing") or vols.get("pvd_spacing") or
                   vols.get("pile_spacing") or "-")
        depth   = (vols.get("cdm_depth") or vols.get("pvd_depth") or
                   vols.get("exc_depth") or vols.get("pile_length") or "-")
        _cell(ws, r, 1,  i)
        _cell(ws, r, 2,  f"KM{seg.get('station_from',0)/1000:.3f}÷KM{seg.get('station_to',0)/1000:.3f}")
        _cell(ws, r, 3,  vols["L"],          num_format=_NUM_FORMAT)
        _cell(ws, r, 4,  vols["htk"],        num_format=_NUM_FORMAT)
        _cell(ws, r, 5,  vols["hdy"],        num_format=_NUM_FORMAT)
        _cell(ws, r, 6,  vols["b_nen"],      num_format=_NUM_FORMAT)
        _cell(ws, r, 7,  vols["b_xl"],       num_format=_NUM_FORMAT)
        _cell(ws, r, 8,  seg.get("treatment",""), fill=_METHOD_FILL.get(vols["treatment"]))
        _cell(ws, r, 9,  spacing,            num_format=_NUM_FORMAT if isinstance(spacing, float) else None)
        _cell(ws, r, 10, depth,              num_format=_NUM_FORMAT if isinstance(depth, float) else None)
        _cell(ws, r, 11, seg.get("Fs"))
        _cell(ws, r, 12, seg.get("notes",""))

    _auto_col_width(ws)


def _write_kl_sheet(wb, segs_by_method: dict[str, list[dict]]):
    """Sheet 2: Khoi luong — four treatment-method sub-tables."""
    ws = wb.create_sheet("Khoi luong")

    row = 1
    _merge(ws, row, 1, row, 10,
           "BẢNG KHỐI LƯỢNG XỬ LÝ ĐẤT YẾU",
           font=Font(name="Times New Roman", bold=True, size=13),
           fill=_FILL_SECTION)
    row += 1

    section_idx = 0
    ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]

    for method_key, segs in segs_by_method.items():
        if not segs:
            continue
        fill = _METHOD_FILL.get(method_key.upper(), _FILL_SECTION)
        method_label = {
            "CDM":      "CỌC ĐẤT GIA CỐ XI MĂNG (CDM)",
            "PVD":      "BẤC THẤM (PVD)",
            "SD":       "GIẾNG CÁT (SD)",
            "ĐÀO THAY": "ĐÀO THAY ĐẤT",
            "CỌC TRE":  "CỌC TRE",
            "CỪ TRÀM":  "CỪ TRÀM",
        }.get(method_key.upper(), method_key)

        row = _write_method_block(ws, row, ROMAN[section_idx],
                                  method_label, method_key, segs, fill)
        row += 1
        section_idx += 1

    _auto_col_width(ws)


def _write_method_block(ws, start_row: int, roman: str, title: str,
                        method_key: str, segs: list[dict], fill) -> int:
    """Write one treatment-method block. Returns last row written."""
    r = start_row
    n_segs = len(segs)
    n_cols = 4 + n_segs + 2   # TT + Hạng mục + ĐVT + STT + segments + Tổng + Ghi chú

    # Section header
    _merge(ws, r, 1, r, n_cols,
           f"{roman}. PHƯƠNG ÁN XỬ LÝ BẰNG {title}",
           font=Font(name="Times New Roman", bold=True, size=11),
           fill=fill)
    r += 1

    # Column headers row
    hdrs = ["TT", "Hạng mục", "Đơn vị"] + [f"Đoạn {i+1}" for i in range(n_segs)] + ["Tổng cộng", "Ghi chú"]
    for ci, h in enumerate(hdrs, 1):
        _hdr(ws, r, ci, h, fill=fill)
    r += 1

    # Chainage sub-header
    _cell(ws, r, 1, "")
    _cell(ws, r, 2, "Lý trình")
    _cell(ws, r, 3, "")
    for i, seg in enumerate(segs):
        _cell(ws, r, 4 + i,
              f"KM{seg.get('station_from',0)/1000:.3f}÷{seg.get('station_to',0)/1000:.3f}",
              align=Alignment(horizontal="center", wrap_text=True))
    _cell(ws, r, 4 + n_segs, "")
    _cell(ws, r, 5 + n_segs, "")
    r += 1

    # Compute volumes per segment
    all_v = [_seg_volumes(seg) for seg in segs]

    # Build item rows per method
    mk = method_key.upper()
    if mk == "CDM":
        items = _cdm_items(all_v)
    elif mk in ("PVD", "SD"):
        items = _pvd_items(all_v, mk)
    elif mk == "ĐÀO THAY":
        items = _dao_items(all_v)
    else:
        items = _coc_items(all_v, mk)

    for tt, (label, unit, vals, note) in enumerate(items, 1):
        _cell(ws, r, 1, tt, align=Alignment(horizontal="center"))
        _cell(ws, r, 2, label)
        _cell(ws, r, 3, unit, align=Alignment(horizontal="center"))
        total = 0.0
        for ci, val in enumerate(vals):
            _cell(ws, r, 4 + ci, val,
                  num_format=_NUM_FORMAT if isinstance(val, float) else (_INT_FORMAT if isinstance(val, int) else None))
            if isinstance(val, (int, float)):
                total += val
        _cell(ws, r, 4 + n_segs, round(total, 2) if total else None,
              num_format=_NUM_FORMAT)
        _cell(ws, r, 5 + n_segs, note or "")
        r += 1

    return r


def _cdm_items(vols: list[dict]) -> list[tuple]:
    def g(key, default=None): return [v.get(key, default) for v in vols]

    return [
        ("Chiều dài đoạn",                  "m",    g("L"),            ""),
        ("Bề rộng xử lý Bxl",               "m",    g("b_xl"),         ""),
        ("Chiều cao đắp Htk",               "m",    g("htk"),          ""),
        ("Cao độ đỉnh CDM",                 "m",    g("cdm_top_elev"), ""),
        ("Cao độ đáy CDM",                  "m",    g("cdm_bot_elev"), ""),
        ("Chiều dài 1 cọc CDM",             "m",    g("cdm_depth"),    ""),
        ("Tổng số lượng cọc CDM D=0.8m XM 260 kg/m³", "cọc", g("n_coc"),  ""),
        ("Tổng chiều dài cọc CDM D=0.8m",   "m",    g("total_len_coc"), ""),
        ("Cọc đại trà khoan lấy mẫu (2%)",  "cọc",  g("n_khoan"),      "2%"),
        ("Chiều dài khoan lấy mẫu",         "m",    g("len_khoan"),    ""),
        ("Vữa xi măng M100 lấp hố khoan",   "m³",   g("vua_lap_ho"),   ""),
        ("Nén 1 trục nở hông qu (đại trà)",  "mẫu",  g("n_mau_qu"),     "1 mẫu/1m"),
        ("Nén tĩnh dọc trục cọc đại trà",   "test", g("n_nen_tinh"),   "2% tổng cọc"),
        ("Ứng suất đầu cọc tính toán",      "T/m²", g("sigma_p"),      ""),
        ("Cường độ cọc cho phép [qu]",       "T/m²", g("cdm_qu_allow"), "= 70 T/m²"),
        ("Tải trọng đầu cọc Ptk",           "T",    g("p_tk"),         "Ptk=σp×Ac"),
        ("Tải trọng thí nghiệm Ptn",        "T",    g("p_tn"),         "Ptn=1.5Ptk"),
        ("Vải địa kỹ thuật gia cường",      "m²",   g("vai_dkt_m2"),   g("geotextile_spec")[0] if vols else ""),
        ("Bàn đo lún mặt",                  "bàn",  g("ban_do_lun"),   "3 bàn/mặt cắt @50m"),
        ("Cọc quan trắc chuyển vị ngang",   "bàn",  g("coc_ctv"),      "@100m"),
    ]


def _pvd_items(vols: list[dict], mk: str) -> list[tuple]:
    def g(key, default=None): return [v.get(key, default) for v in vols]

    label_drain = "bấc thấm" if mk == "PVD" else "giếng cát"
    return [
        ("Chiều dài đoạn",                    "m",    g("L"),            ""),
        ("Bề rộng xử lý Bxl",                "m",    g("b_xl"),         ""),
        ("Chiều cao đắp Htk",                "m",    g("htk"),          ""),
        (f"Khoảng cách bố trí {label_drain}", "m",    g("pvd_spacing"),  "lưới tam giác"),
        (f"Chiều sâu {label_drain}",          "m",    g("pvd_depth"),    ""),
        (f"Tổng số lượng {label_drain}",      "cái",  g("n_pvd"),        ""),
        (f"Tổng chiều dài {label_drain}",     "m",    g("total_len_pvd"), ""),
        ("Chiều cao gia tải trước",           "m",    g("h_giatai"),     "~25% Htk"),
        ("Khối lượng đất gia tải",            "m³",   g("vol_giatai"),   ""),
        ("Vải địa kỹ thuật lọc",             "m²",   g("vai_dkt_m2"),   g("geotextile_spec")[0] if vols else ""),
        ("Bàn đo lún mặt",                   "bàn",  g("ban_do_lun"),   "@50m"),
        ("Cọc quan trắc chuyển vị ngang",    "bàn",  g("coc_ctv"),      "@100m"),
    ]


def _dao_items(vols: list[dict]) -> list[tuple]:
    def g(key, default=None): return [v.get(key, default) for v in vols]

    return [
        ("Chiều dài đoạn",                   "m",   g("L"),           ""),
        ("Bề rộng xử lý Bxl",               "m",   g("b_xl"),        ""),
        ("Chiều sâu đào thay đất yếu",       "m",   g("exc_depth"),   "max 4m"),
        ("Khối lượng đào lớp đất yếu (cấp I–III)", "m³", g("vol_dao"), ""),
        ("Khối lượng lấp bằng cát K95",      "m³",  g("vol_lap_cat"), ""),
        ("Vải địa kỹ thuật ngăn cách",       "m²",  g("vai_dkt_m2"),  g("geotextile_spec")[0] if vols else ""),
        ("Bàn đo lún mặt",                   "bàn", g("ban_do_lun"),  "@50m"),
        ("Cọc quan trắc chuyển vị ngang",    "bàn", g("coc_ctv"),     "@100m"),
    ]


def _coc_items(vols: list[dict], mk: str) -> list[tuple]:
    def g(key, default=None): return [v.get(key, default) for v in vols]

    label = "Cọc tre" if mk == "CỌC TRE" else "Cừ tràm"
    return [
        ("Chiều dài đoạn",                  "m",     g("L"),             ""),
        ("Bề rộng xử lý Bxl",              "m",     g("b_xl"),          ""),
        (f"Mật độ {label}",                 "cọc/m²", g("mat_do"),        ""),
        (f"Chiều sâu đóng {label.lower()}", "m",     g("pile_length"),   f"max {3 if mk == 'CỌC TRE' else 4}m"),
        (f"Tổng số lượng {label.lower()}",  "cọc",   g("n_coc"),         ""),
        (f"Tổng chiều dài {label.lower()}", "m",     g("total_len_coc"), ""),
        ("Vải địa kỹ thuật gia cường",      "m²",    g("vai_dkt_m2"),    g("geotextile_spec")[0] if vols else ""),
        ("Bàn đo lún mặt",                  "bàn",   g("ban_do_lun"),    "@50m"),
        ("Cọc quan trắc chuyển vị ngang",   "bàn",   g("coc_ctv"),       "@100m"),
    ]


def _auto_col_width(ws):
    for col in ws.columns:
        max_len = 0
        for cell in col:
            try:
                if cell.value:
                    for line in str(cell.value).split("\n"):
                        max_len = max(max_len, len(line))
            except Exception:
                pass
        letter = get_column_letter(col[0].column)
        ws.column_dimensions[letter].width = min(max(max_len * 0.9 + 2, 8), 40)


# ---------------------------------------------------------------------------
# Top-level API
# ---------------------------------------------------------------------------

def write_klxldy(path: str | Path, segments: list[dict],
                 project_name: str = "") -> dict:
    """Write XLDY volume workbook to *path*.

    segments: list of segment dicts (from road_analyze / road_verify / THSH).
    Returns {output_path, rows_written, warnings}.
    """
    if openpyxl is None:
        raise RuntimeError("openpyxl không được cài đặt.")

    path = str(path)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # remove default sheet

    # Group segments by treatment method
    from collections import OrderedDict
    segs_by_method: dict[str, list[dict]] = OrderedDict()
    for seg in segments:
        t = (seg.get("treatment") or "").upper().strip()
        if t not in segs_by_method:
            segs_by_method[t] = []
        segs_by_method[t].append(seg)

    _write_summary_sheet(wb, segments, project_name)
    _write_kl_sheet(wb, segs_by_method)

    wb.save(path)
    return {
        "output_path": path,
        "rows_written": len(segments),
        "warnings": [],
    }

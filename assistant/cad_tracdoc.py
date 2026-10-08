"""Generate a standard Vietnamese highway longitudinal profile (trắc dọc) DXF.

Input: a list of profile points (station, ground_elev, design_elev, pile_name).
Output: ezdxf document with:
  - Profile view (ground line green, design line red, cut/fill hatch)
  - Standard table below (8 rows matching TCVN 4054 sheet format)
"""

import json
import math
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path, PureWindowsPath

from .windows_apps import fingerprint

UNITS_MAP = {'mm': 4, 'cm': 5, 'm': 6, 'inch': 1}

# Standard layer names (matching the template DXF)
_LAYERS = {
    "TK-ADS-9302-Bảng trắc dọc":     7,   # grid/table outline – white
    "TK-ADS-9303-Chữ trắc dọc":      7,   # table text – white
    "TK-ADS-9307-Lý trình trắc dọc": 7,   # station labels
    "KS-TUY-2401-Trắc dọc tự nhiên": 3,   # natural ground – green
    "TK-DBO-1601-Đtk tim tuyến":     1,   # design profile – red
    "TRACDOC-HATCHING":               4,   # cut/fill hatch
    "TRACDOC-DIM":                    6,   # dimension lines
    "TRACDOC-TITLE":                  1,   # drawing title
}

# Vertical scale: 1 m elevation → V_SCALE drawing units high
V_SCALE = 5.0
# Horizontal scale: 1 m station → 1 drawing unit wide (use real coords, scale with plot scale)
# Table row heights (m in drawing)
_ROW_H = [8, 8, 8, 8, 8, 8, 8, 8]  # 8 rows × 8 = 64 units total table height
_ROW_LABELS = [
    "Cao độ TK",
    "Cao độ TN",
    "Dốc dọc TK",
    "Kc cộng dồn",
    "Kc lẻ",
    "Tên cọc",
    "Lý trình",
    "Đoạn thẳng/cong",
]
_LABEL_COL_W = 30  # width of left label column
_TABLE_TOTAL_H = sum(_ROW_H)   # 64
_PROFILE_GAP   = 10            # gap between table top and profile baseline
_PROFILE_H     = 80            # max profile drawing height


def _setup(doc):
    for name, color in _LAYERS.items():
        if name not in doc.layers:
            doc.layers.new(name).color = color


def _text(msp, value, x, y, h=2.5, layer="TK-ADS-9303-Chữ trắc dọc",
          align=None):
    from ezdxf.enums import TextEntityAlignment
    if align is None:
        align = TextEntityAlignment.MIDDLE_CENTER
    t = msp.add_text(str(value),
                     dxfattribs={"height": h, "layer": layer})
    t.set_placement((x, y), align=align)
    return t


def build_tracdoc_dxf(points, title="TRẮC DỌC TUYẾN ĐƯỜNG", units="m",
                      h_scale=1, v_scale=None):
    """
    Build and return an ezdxf document with a standard longitudinal profile.

    Args:
        points  – list of dicts with keys:
                    station     (float, m from start)
                    ground_elev (float, m)
                    design_elev (float, m)
                    pile_name   (str, optional) – stake label e.g. "1", "P2"
                    curve_note  (str, optional) – tangent/curve label
        title   – drawing title string
        units   – 'm' / 'mm' / 'cm' / 'inch'
        h_scale – horizontal scale factor (1 = 1 drawing unit per metre of station)
        v_scale – vertical exaggeration factor (default 5)
    """
    import ezdxf
    from ezdxf.enums import TextEntityAlignment

    if not points:
        raise ValueError("points list is empty")
    if len(points) < 2:
        raise ValueError("points cần ít nhất 2 điểm để vẽ trắc dọc.")
    if v_scale is None:
        v_scale = V_SCALE

    doc = ezdxf.new("R2010")
    doc.units = UNITS_MAP.get(units, 6)
    _setup(doc)
    msp = doc.modelspace()

    n = len(points)
    first_sta = points[0]["station"]

    def sx(sta):
        return (sta - first_sta) * h_scale

    total_width = sx(points[-1]["station"])

    grid_layer = "TK-ADS-9302-Bảng trắc dọc"
    txt_layer  = "TK-ADS-9303-Chữ trắc dọc"

    # ----------------------------------------------------------------
    # Table grid
    # ----------------------------------------------------------------
    ox = 0.0  # left edge of data area (right of label column)
    oy = 0.0  # bottom of table

    # Horizontal lines
    y = oy
    for rh in _ROW_H:
        msp.add_line((-_LABEL_COL_W, y), (total_width, y),
                     dxfattribs={"layer": grid_layer})
        y += rh
    msp.add_line((-_LABEL_COL_W, y), (total_width, y),
                 dxfattribs={"layer": grid_layer})

    # Left column borders
    msp.add_line((-_LABEL_COL_W, oy), (-_LABEL_COL_W, y),
                 dxfattribs={"layer": grid_layer})
    msp.add_line((0, oy), (0, y),
                 dxfattribs={"layer": grid_layer})

    # Right border
    msp.add_line((total_width, oy), (total_width, y),
                 dxfattribs={"layer": grid_layer})

    # Row labels
    row_y = oy
    for label, rh in zip(_ROW_LABELS, _ROW_H):
        _text(msp, label, -_LABEL_COL_W / 2.0, row_y + rh / 2.0 - 1.2,
              h=2.0, layer=grid_layer)
        row_y += rh

    # Vertical station lines
    for pt in points:
        x = sx(pt["station"])
        msp.add_line((x, oy), (x, y),
                     dxfattribs={"layer": grid_layer, "color": 8})

    # ----------------------------------------------------------------
    # Table data cells – fill per station point
    # ----------------------------------------------------------------
    # Row y positions (bottom of each row)
    row_bottoms = []
    ry = oy
    for rh in _ROW_H:
        row_bottoms.append(ry)
        ry += rh

    # For cells between two consecutive points we centre in the span;
    # for the last point we put data right at its x.
    cumulative = 0.0
    for i, pt in enumerate(points):
        x_pt = sx(pt["station"])
        if i < n - 1:
            x_next = sx(points[i + 1]["station"])
            cx = (x_pt + x_next) / 2.0
            span = x_next - x_pt
            cumulative += span
        else:
            cx = x_pt
            span = 0.0

        de = pt.get("design_elev")
        ge = pt.get("ground_elev")
        pile = pt.get("pile_name", "")
        curve = pt.get("curve_note", "")

        # Row 0 (top): Cao độ TK
        if de is not None:
            _text(msp, f"{de:.2f}", cx, row_bottoms[0] + _ROW_H[0] / 2.0 - 1.2)

        # Row 1: Cao độ TN
        if ge is not None:
            _text(msp, f"{ge:.2f}", cx, row_bottoms[1] + _ROW_H[1] / 2.0 - 1.2)

        # Row 2: Dốc dọc (slope between this and next point)
        if i < n - 1 and de is not None and span > 0:
            de_next = points[i + 1].get("design_elev")
            if de_next is not None:
                slope = (de_next - de) / span * 100.0
                _text(msp, f"{slope:+.2f}%", cx, row_bottoms[2] + _ROW_H[2] / 2.0 - 1.2)

        # Row 3: Khoảng cách cộng dồn
        if i > 0:
            _text(msp, f"{cumulative:.0f}", cx, row_bottoms[3] + _ROW_H[3] / 2.0 - 1.2)

        # Row 4: Khoảng cách lẻ
        if i < n - 1 and span > 0:
            _text(msp, f"{span:.1f}", cx, row_bottoms[4] + _ROW_H[4] / 2.0 - 1.2)

        # Row 5: Tên cọc
        if pile:
            _text(msp, pile, x_pt, row_bottoms[5] + _ROW_H[5] / 2.0 - 1.2)

        # Row 6: Lý trình
        sta_km   = int(pt["station"]) // 1000
        sta_m    = pt["station"] % 1000
        sta_str  = f"Km{sta_km}+{sta_m:06.2f}"
        _text(msp, sta_str, x_pt, row_bottoms[6] + _ROW_H[6] / 2.0 - 1.2,
              h=2.0, layer="TK-ADS-9307-Lý trình trắc dọc")

        # Row 7: Đoạn thẳng/cong
        if curve:
            _text(msp, curve, cx, row_bottoms[7] + _ROW_H[7] / 2.0 - 1.2)

    # ----------------------------------------------------------------
    # Profile view
    # ----------------------------------------------------------------
    profile_y0 = _TABLE_TOTAL_H + _PROFILE_GAP   # baseline of profile area

    ground_elevs = [p["ground_elev"] for p in points if p.get("ground_elev") is not None]
    design_elevs = [p["design_elev"] for p in points if p.get("design_elev") is not None]
    all_elevs    = ground_elevs + design_elevs
    if not all_elevs:
        return doc

    baseline_elev = min(all_elevs) - 0.5

    def ey(elev):
        return profile_y0 + (elev - baseline_elev) * v_scale

    # Ground profile polyline
    gpts = [(sx(p["station"]), ey(p["ground_elev"]))
            for p in points if p.get("ground_elev") is not None]
    if len(gpts) >= 2:
        msp.add_lwpolyline(gpts,
                           dxfattribs={"layer": "KS-TUY-2401-Trắc dọc tự nhiên",
                                       "color": 3, "lineweight": 50})

    # Design profile polyline
    dpts = [(sx(p["station"]), ey(p["design_elev"]))
            for p in points if p.get("design_elev") is not None]
    if len(dpts) >= 2:
        msp.add_lwpolyline(dpts,
                           dxfattribs={"layer": "TK-DBO-1601-Đtk tim tuyến",
                                       "color": 1, "lineweight": 70})

    # Elevation grid lines (every 1m of elevation)
    if all_elevs:
        e_min = math.floor(baseline_elev)
        e_max = math.ceil(max(all_elevs)) + 1
        for e in range(e_min, e_max + 1):
            yy = ey(e)
            msp.add_line((-_LABEL_COL_W, yy), (total_width, yy),
                         dxfattribs={"layer": "TRACDOC-DIM", "color": 251})
            # Elevation label on left
            _text(msp, f"{e:.0f}", -_LABEL_COL_W / 2.0, yy,
                  h=2.0, layer="TRACDOC-DIM")

    # Profile left/right borders
    msp.add_line((0, profile_y0), (0, ey(max(all_elevs)) + 10),
                 dxfattribs={"layer": "TK-ADS-9302-Bảng trắc dọc"})
    msp.add_line((total_width, profile_y0),
                 (total_width, ey(max(all_elevs)) + 10),
                 dxfattribs={"layer": "TK-ADS-9302-Bảng trắc dọc"})

    # Dip lines from each station to the table
    for pt in points:
        x = sx(pt["station"])
        if pt.get("design_elev") is not None:
            y_top = ey(pt["design_elev"])
            msp.add_line((x, profile_y0), (x, y_top),
                         dxfattribs={"layer": "TRACDOC-DIM", "color": 251})

    # Cut/fill hatch between ground and design
    try:
        hatch = msp.add_hatch(color=4, dxfattribs={"layer": "TRACDOC-HATCHING"})
        hatch.set_pattern_fill("ANSI31", scale=0.3)
        # Boundary = design line + reversed ground line
        hatch_pts = dpts + list(reversed(gpts))
        if len(hatch_pts) >= 3:
            hatch.paths.add_polyline_path(hatch_pts, is_closed=True)
    except Exception:
        pass

    # Title
    title_y = ey(max(all_elevs)) + 15
    _text(msp, title, total_width / 2.0, title_y,
          h=4.0, layer="TRACDOC-TITLE")

    return doc


class CadTracDocApp:
    """Prepare/commit pattern for trắc dọc DXF creation + AutoCAD launch."""

    def __init__(self, windows, files, audit):
        self.windows = windows
        self.files   = files
        self.audit   = audit

    def prepare(self, name, args):
        self.windows.check()
        app = self.windows.allowed_path(args["app"])
        if app.name.lower() not in {"acad.exe", "acadlt.exe"}:
            raise ValueError("Chọn acad.exe hoặc acadlt.exe đã được phép.")

        raw_pts = args["points"]
        if isinstance(raw_pts, str):
            raw_pts = json.loads(raw_pts)
        if not isinstance(raw_pts, list) or len(raw_pts) < 2:
            raise ValueError("points phải là mảng JSON có ít nhất 2 điểm.")

        parsed = []
        for i, p in enumerate(raw_pts):
            try:
                sta  = float(p["station"])
                ge   = float(p["ground_elev"])
                de   = float(p["design_elev"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Điểm [{i}]: {exc}") from exc
            parsed.append({
                "station":     sta,
                "ground_elev": ge,
                "design_elev": de,
                "pile_name":   str(p.get("pile_name", "") or ""),
                "curve_note":  str(p.get("curve_note", "") or ""),
            })

        if not self.files.roots:
            raise PermissionError("Thêm thư mục lưu bản vẽ trong Cài đặt.")
        path = self.files.path(
            str(self.files.roots[0] / ("TRACDOC-" + uuid.uuid4().hex[:8] + ".dxf")),
            exists=False)

        return {
            "action":  "cad_tracdoc_stations",
            "app":     str(app),
            "sha256":  fingerprint(app),
            "path":    str(path),
            "points":  parsed,
            "title":   args.get("title", "TRẮC DỌC TUYẾN ĐƯỜNG"),
            "units":   args.get("units", "m"),
        }

    def commit(self, plan):
        self.windows.check()
        app = self.windows.allowed_path(plan["app"])
        if fingerprint(app) != plan["sha256"]:
            raise PermissionError("EXE AutoCAD đã thay đổi; không mở.")

        doc = build_tracdoc_dxf(
            points=plan["points"],
            title=plan.get("title", "TRẮC DỌC TUYẾN ĐƯỜNG"),
            units=plan.get("units", "m"),
        )

        path = self.files.path(plan["path"], exists=False)
        if path.exists():
            raise FileExistsError("Không ghi đè bản vẽ đã có.")

        with tempfile.TemporaryDirectory(prefix=".tracdoc-", dir=path.parent) as folder:
            tmp = Path(folder) / "drawing.dxf"
            doc.saveas(tmp)
            self.windows.check()
            self.files.path(str(path), exists=False)
            with path.open("xb") as out, tmp.open("rb") as src:
                shutil.copyfileobj(src, out)

        self.audit("cad_document_created", {
            "path": str(path), "type": "tracdoc_stations",
            "n_points": len(plan["points"]),
        })

        self.windows.check()
        if fingerprint(app) != plan["sha256"]:
            raise PermissionError("Đã tạo DXF nhưng EXE AutoCAD đã thay đổi; chưa mở.")
        subprocess.Popen([str(app), str(path)], shell=False)

        n = len(plan["points"])
        total = plan["points"][-1]["station"] - plan["points"][0]["station"]
        return {
            "ok":                True,
            "path":              str(path),
            "n_points":          n,
            "total_length_m":    total,
            "document_created":  True,
            "cad_launch_requested": True,
            "note": (
                f"Đã tạo DXF trắc dọc ({n} điểm, L={total:.0f}m). "
                "Gồm đường cao độ TN/TK và bảng số liệu 8 hàng. Đã gửi lệnh mở AutoCAD."
            ),
        }

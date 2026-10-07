"""Generate DXF drawings for road soft-ground treatment (XLDY) from THSH segment data."""

import ezdxf
from ezdxf import colors
from ezdxf.enums import TextEntityAlignment


# ---------------------------------------------------------------------------
# Layer definitions
# ---------------------------------------------------------------------------
LAYERS = {
    "TK-ADS-9302-Bảng trắc dọc":   {"color": 7},
    "TK-ADS-9303-Chữ trắc dọc":    {"color": 7},
    "TK-ADS-9331-Chênh cđ tim tuyến": {"color": 2},
    "TK-DBO-1601-Đtk tim tuyến":   {"color": 1},
    "KS-TUY-2401-Trắc dọc tự nhiên": {"color": 3},
    "XLDY-PVD-ZONE":                {"color": 4},
    "XLDY-CDM-ZONE":                {"color": 5},
    "XLDY-PVD-DEPTH":               {"color": 4, "linetype": "DASHED"},
    "XLDY-ANNOT":                   {"color": 6},
    "NEN-DUONG":                    {"color": 2},
    "CT-TRDUONG":                   {"color": 1},
    "PLINETNTN":                    {"color": 3},
    "PLINEVETBUN":                  {"color": 3},
    "GT_MCN":                       {"color": 4},
    "XLDY-CDM":                     {"color": 5},
    "VolUnsoil":                    {"color": 8},
    "TEXT125":                      {"color": 7},
    "TEXTL":                        {"color": 7},
    "DIM":                          {"color": 6},
    "0":                            {"color": 7},
}

ROW_HEADERS = [
    "Đoạn thẳng - Đoạn cong",
    "Lý trình",
    "Tên cọc",
    "K/c cộng dồn",
    "Khoảng cách lẻ",
    "Cao độ tự nhiên",
    "Dốc dọc TK",
    "Cao độ thiết kế",
    "Chênh cđ tim tuyến",
]

ROW_Y_STARTS = [0, 10, 20, 30, 40, 50, 60, 70, 80]  # bottom edges
ROW_HEIGHTS  = [10, 10, 10, 10, 10, 10, 10, 10, 20]  # last row is double

ELEV_SCALE = 5.0  # 1m elevation = 5 drawing units
LABEL_COL_WIDTH = 15  # units to the left of origin_x for row labels


def _setup_doc(doc):
    """Ensure layers and text styles exist in doc."""
    for lname, props in LAYERS.items():
        if lname not in doc.layers:
            layer = doc.layers.new(lname)
            layer.color = props.get("color", 7)
            lt = props.get("linetype")
            if lt:
                if lt not in doc.linetypes:
                    try:
                        doc.linetypes.load(lt)
                    except Exception:
                        pass
                layer.linetype = lt

    if "VNARIAL" not in doc.styles:
        doc.styles.new("VNARIAL", dxfattribs={"font": ".VnArial.ttf"})


def _seg_x(seg, origin_x):
    """Return the drawing x coordinate for the start of this segment."""
    return origin_x + seg["station_from"] / 1.0  # 1 unit = 1 m station


def _seg_cx(seg, origin_x):
    return origin_x + (seg["station_from"] + seg["station_to"]) / 2.0


def _add_text(msp, text, x, y, height=1.5, layer="TK-ADS-9303-Chữ trắc dọc",
              style="VNARIAL", halign=ezdxf.enums.TextEntityAlignment.LEFT):
    """Add a text entity."""
    t = msp.add_text(text, dxfattribs={"height": height, "layer": layer, "style": style})
    t.set_placement((x, y), align=halign)
    return t


# ---------------------------------------------------------------------------
# Function 1 – Trắc dọc XLDY
# ---------------------------------------------------------------------------

def build_tracdoc_xldy(doc, segments, origin_x=0, origin_y=0):
    """Draw trắc dọc XLDY table + profile for a list of segment dicts."""
    _setup_doc(doc)
    msp = doc.modelspace()

    if not segments:
        return

    # Compute x-coords for each segment boundary
    # x is offset from origin_x by (station - first_station)
    first_sta = segments[0]["station_from"]

    def sta_to_x(sta):
        return origin_x + (sta - first_sta)

    x_start = sta_to_x(segments[0]["station_from"])
    x_end   = sta_to_x(segments[-1]["station_to"])

    # ----------------------------------------------------------------
    # Table grid
    # ----------------------------------------------------------------
    grid_layer = "TK-ADS-9302-Bảng trắc dọc"

    # Horizontal lines
    y_cursor = origin_y
    for i, rh in enumerate(ROW_HEIGHTS):
        msp.add_line((x_start - LABEL_COL_WIDTH, y_cursor + origin_y - origin_y),
                     (x_end, y_cursor + origin_y - origin_y),
                     dxfattribs={"layer": grid_layer})
        y_cursor += rh
    # top border
    msp.add_line((x_start - LABEL_COL_WIDTH, origin_y + y_cursor),
                 (x_end, origin_y + y_cursor),
                 dxfattribs={"layer": grid_layer})

    # Vertical lines at segment boundaries
    total_table_height = sum(ROW_HEIGHTS)
    for seg in segments:
        sx = sta_to_x(seg["station_from"])
        msp.add_line((sx, origin_y), (sx, origin_y + total_table_height),
                     dxfattribs={"layer": grid_layer})
    # right border
    msp.add_line((x_end, origin_y), (x_end, origin_y + total_table_height),
                 dxfattribs={"layer": grid_layer})

    # Left label column vertical lines
    msp.add_line((x_start - LABEL_COL_WIDTH, origin_y),
                 (x_start - LABEL_COL_WIDTH, origin_y + total_table_height),
                 dxfattribs={"layer": grid_layer})

    # Row header labels
    y_cursor = origin_y
    for i, (header, rh) in enumerate(zip(ROW_HEADERS, ROW_HEIGHTS)):
        ty = y_cursor + rh / 2.0 - 0.75
        _add_text(msp, header,
                  x_start - LABEL_COL_WIDTH + 0.5, ty,
                  height=1.5, layer=grid_layer)
        y_cursor += rh

    # ----------------------------------------------------------------
    # Table data rows
    # ----------------------------------------------------------------
    cumulative = 0.0
    text_layer = "TK-ADS-9303-Chữ trắc dọc"

    for seg in segments:
        sx  = sta_to_x(seg["station_from"])
        ex  = sta_to_x(seg["station_to"])
        cx  = (sx + ex) / 2.0
        lh  = 1.5  # label height

        # Row 0: treatment type
        _add_text(msp, seg.get("treatment", ""), cx, origin_y + 3,
                  height=lh, layer=text_layer,
                  halign=TextEntityAlignment.MIDDLE_CENTER)

        # Row 1: Lý trình
        sta_label = f"KM{seg['station_from']//1000}+{seg['station_from']%1000:03d}"
        _add_text(msp, sta_label, sx + 0.5, origin_y + 10 + 3,
                  height=lh, layer=text_layer)

        # Row 2: Tên cọc (borehole ref)
        bref = seg.get("borehole_ref") or ""
        _add_text(msp, bref, cx, origin_y + 20 + 3,
                  height=lh, layer=text_layer,
                  halign=TextEntityAlignment.MIDDLE_CENTER)

        # Row 3: Khoảng cách cộng dồn
        cumulative += seg.get("length", seg["station_to"] - seg["station_from"])
        _add_text(msp, f"{cumulative:.0f}", cx, origin_y + 30 + 3,
                  height=lh, layer=text_layer,
                  halign=TextEntityAlignment.MIDDLE_CENTER)

        # Row 4: Khoảng cách lẻ
        seg_len = seg.get("length", seg["station_to"] - seg["station_from"])
        _add_text(msp, f"{seg_len:.0f}", cx, origin_y + 40 + 3,
                  height=lh, layer=text_layer,
                  halign=TextEntityAlignment.MIDDLE_CENTER)

        # Row 5: Cao độ tự nhiên
        ge = seg.get("ground_elev")
        if ge is not None:
            _add_text(msp, f"{ge:.2f}", cx, origin_y + 50 + 3,
                      height=lh, layer=text_layer,
                      halign=TextEntityAlignment.MIDDLE_CENTER)

        # Row 6: Dốc dọc thiết kế
        de = seg.get("design_elev")
        if de is not None and ge is not None and seg_len > 0:
            slope_pct = (de - ge) / seg_len * 100
            _add_text(msp, f"{slope_pct:+.2f}%", cx, origin_y + 60 + 3,
                      height=lh, layer=text_layer,
                      halign=TextEntityAlignment.MIDDLE_CENTER)

        # Row 7: Cao độ thiết kế
        if de is not None:
            _add_text(msp, f"{de:.2f}", cx, origin_y + 70 + 3,
                      height=lh, layer=text_layer,
                      halign=TextEntityAlignment.MIDDLE_CENTER)

        # Row 8: Chênh cđ tim tuyến (Htk)
        htk = seg.get("htk")
        if htk is not None:
            _add_text(msp, f"{htk:.2f}", cx, origin_y + 80 + 5,
                      height=lh, layer="TK-ADS-9331-Chênh cđ tim tuyến",
                      halign=TextEntityAlignment.MIDDLE_CENTER)

    # ----------------------------------------------------------------
    # Profile area
    # ----------------------------------------------------------------
    profile_base_y = origin_y + total_table_height  # y=100 for default

    ground_elevs   = [s["ground_elev"]  for s in segments if s.get("ground_elev")  is not None]
    design_elevs   = [s["design_elev"]  for s in segments if s.get("design_elev")  is not None]

    if not ground_elevs:
        return

    baseline_elev = min(ground_elevs + design_elevs) - 1.0

    def elev_to_y(elev):
        return profile_base_y + (elev - baseline_elev) * ELEV_SCALE

    # Ground profile polyline
    ground_pts = []
    for seg in segments:
        ge = seg.get("ground_elev")
        if ge is not None:
            sx = sta_to_x(seg["station_from"])
            ground_pts.append((sx, elev_to_y(ge)))
    if segments[-1].get("ground_elev") is not None:
        ground_pts.append((sta_to_x(segments[-1]["station_to"]),
                           elev_to_y(segments[-1]["ground_elev"])))

    if len(ground_pts) >= 2:
        msp.add_lwpolyline(ground_pts,
                           dxfattribs={"layer": "KS-TUY-2401-Trắc dọc tự nhiên",
                                       "color": 3})

    # Design profile polyline
    design_pts = []
    for seg in segments:
        de = seg.get("design_elev")
        if de is not None:
            sx = sta_to_x(seg["station_from"])
            design_pts.append((sx, elev_to_y(de)))
    if segments[-1].get("design_elev") is not None:
        design_pts.append((sta_to_x(segments[-1]["station_to"]),
                           elev_to_y(segments[-1]["design_elev"])))

    if len(design_pts) >= 2:
        msp.add_lwpolyline(design_pts,
                           dxfattribs={"layer": "TK-DBO-1601-Đtk tim tuyến",
                                       "color": 1, "lineweight": 50})

    # Treatment zones + annotations
    for seg in segments:
        treatment = (seg.get("treatment") or "").upper()
        sx  = sta_to_x(seg["station_from"])
        ex  = sta_to_x(seg["station_to"])
        ge  = seg.get("ground_elev")
        de  = seg.get("design_elev")
        cx  = (sx + ex) / 2.0

        if ge is None or de is None:
            continue

        gy = elev_to_y(ge)
        dy = elev_to_y(de)

        if treatment in ("PVD", "CDM"):
            zone_layer = "XLDY-PVD-ZONE" if treatment == "PVD" else "XLDY-CDM-ZONE"
            hatch_pattern = "ANSI31" if treatment == "PVD" else "AR-SAND"
            hatch_color   = 4 if treatment == "PVD" else 5

            # Zone rectangle as hatch
            boundary = [(sx, gy), (ex, gy), (ex, dy), (sx, dy), (sx, gy)]
            try:
                hatch = msp.add_hatch(color=hatch_color,
                                      dxfattribs={"layer": zone_layer})
                hatch.set_pattern_fill(hatch_pattern, scale=0.5)
                hatch.paths.add_polyline_path(boundary, is_closed=True)
            except Exception:
                # Fallback: just draw outline rectangle
                msp.add_lwpolyline(boundary,
                                   dxfattribs={"layer": zone_layer,
                                               "color": hatch_color})

        # PVD depth line (dashed, from design surface down pvd_depth)
        if treatment == "PVD":
            pvd_depth = seg.get("pvd_depth") or 0
            if pvd_depth > 0:
                depth_y = elev_to_y(de - pvd_depth)
                msp.add_line((cx, dy), (cx, depth_y),
                             dxfattribs={"layer": "XLDY-PVD-DEPTH", "color": 4})

        # CDM depth annotation
        if treatment == "CDM":
            hdy = seg.get("hdy") or 0
            _add_text(msp, f"H.CDM={hdy:.1f}m",
                      cx, dy + 3, height=1.5, layer="0")

        # Settlement annotations
        sc = seg.get("Sc")
        st = seg.get("St")
        if sc is not None:
            _add_text(msp, f"Sc={sc:.1f}cm",
                      cx, dy + 6, height=1.5, layer="XLDY-ANNOT",
                      halign=TextEntityAlignment.MIDDLE_CENTER)
        if st is not None:
            _add_text(msp, f"St={st:.1f}cm",
                      cx, dy + 8, height=1.5, layer="XLDY-ANNOT",
                      halign=TextEntityAlignment.MIDDLE_CENTER)


# ---------------------------------------------------------------------------
# Function 2 – MCN điển hình XLDY
# ---------------------------------------------------------------------------

def build_mcn_xldy(doc, segment, origin_x=0, origin_y=0):
    """Draw one typical cross-section (MCN) for a single segment."""
    _setup_doc(doc)
    msp = doc.modelspace()

    b_nen      = float(segment.get("b_nen") or 12.0)
    htk        = float(segment.get("htk") or 0.0)
    hdy        = float(segment.get("hdy") or 0.0)
    pvd_spacing= float(segment.get("pvd_spacing") or 0.0)
    pvd_depth  = float(segment.get("pvd_depth") or 0.0)
    taluy      = float(segment.get("taluy") or 1.5)
    treatment  = (segment.get("treatment") or "").upper()

    half_bn    = b_nen / 2.0
    toe_half   = half_bn + taluy * htk        # half-width at base of embankment
    extent     = toe_half + 5.0               # natural ground extends extra 5 m each side

    # 1. Natural ground line
    msp.add_lwpolyline(
        [(-extent, origin_y), (extent, origin_y)],
        dxfattribs={"layer": "PLINETNTN", "color": 3}
    )

    # 2. Embankment shape (closed polyline)
    crest_y  = origin_y + htk
    emb_pts  = [
        (-toe_half, origin_y),
        (toe_half,  origin_y),
        (half_bn,   crest_y),
        (-half_bn,  crest_y),
        (-toe_half, origin_y),
    ]
    msp.add_lwpolyline(emb_pts, close=True,
                       dxfattribs={"layer": "NEN-DUONG", "color": 2})

    # 3. Road surface with 2% cross-slope
    road_thickness = 0.5  # approximate pavement thickness
    road_pts = [
        (-half_bn, crest_y),
        (0, crest_y + half_bn * 0.02),
        (half_bn, crest_y),
    ]
    msp.add_lwpolyline(road_pts,
                       dxfattribs={"layer": "CT-TRDUONG", "color": 1})

    # 4. Soft soil zone (hatch)
    soft_left  = -(toe_half + 5.0)
    soft_right = toe_half + 5.0
    soft_pts   = [
        (soft_left,  origin_y - hdy),
        (soft_right, origin_y - hdy),
        (soft_right, origin_y),
        (soft_left,  origin_y),
        (soft_left,  origin_y - hdy),
    ]
    if hdy > 0:
        try:
            hatch = msp.add_hatch(color=8, dxfattribs={"layer": "VolUnsoil"})
            hatch.set_pattern_fill("ANSI31", scale=0.5)
            hatch.paths.add_polyline_path(soft_pts, is_closed=True)
        except Exception:
            msp.add_lwpolyline(soft_pts,
                               dxfattribs={"layer": "VolUnsoil", "color": 8})

    # 5. PVD symbols (vertical lines spaced at pvd_spacing)
    if treatment == "PVD" and pvd_spacing > 0 and pvd_depth > 0:
        pvd_zone_left  = -toe_half
        pvd_zone_right =  toe_half
        x = pvd_zone_left
        while x <= pvd_zone_right + 0.01:
            msp.add_line(
                (x, crest_y),
                (x, crest_y - pvd_depth),
                dxfattribs={"layer": "GT_MCN", "color": 4}
            )
            x += pvd_spacing

    # 6. CDM circles
    if treatment == "CDM" and hdy > 0:
        cdm_radius  = 0.4   # 0.8 m diameter
        cdm_spacing = segment.get("pvd_spacing") or 1.6
        cdm_spacing = float(cdm_spacing) if cdm_spacing else 1.6
        x = -toe_half
        while x <= toe_half + 0.01:
            # CDM from design surface to bottom of soft soil
            y_top = origin_y
            y_bot = origin_y - hdy
            n_cdm = max(1, int((y_top - y_bot) / (cdm_radius * 2)))
            for row in range(n_cdm):
                cy = y_top - cdm_radius - row * cdm_radius * 2
                msp.add_circle(
                    (x, cy), cdm_radius,
                    dxfattribs={"layer": "XLDY-CDM", "color": 5}
                )
            x += cdm_spacing

    # 7. Dimension annotations
    ann_y_above = crest_y + 2.0
    # Bn annotation
    msp.add_line((-half_bn, ann_y_above), (half_bn, ann_y_above),
                 dxfattribs={"layer": "DIM", "color": 6})
    _add_text(msp, f"Bn={b_nen:.1f}m",
              0, ann_y_above + 0.5, height=1.0, layer="DIM",
              halign=TextEntityAlignment.MIDDLE_CENTER)

    # Htk annotation
    htk_x = half_bn + taluy * htk + 2.0
    msp.add_line((htk_x, origin_y), (htk_x, crest_y),
                 dxfattribs={"layer": "DIM", "color": 6})
    _add_text(msp, f"Htk={htk:.2f}m",
              htk_x + 0.5, (origin_y + crest_y) / 2.0,
              height=1.0, layer="DIM")

    # hdy annotation
    if hdy > 0:
        hdy_x = soft_right + 2.0
        msp.add_line((hdy_x, origin_y - hdy), (hdy_x, origin_y),
                     dxfattribs={"layer": "DIM", "color": 6})
        _add_text(msp, f"hdy={hdy:.1f}m",
                  hdy_x + 0.5, origin_y - hdy / 2.0,
                  height=1.0, layer="DIM")

    # 8. Title text
    treatment_label = f" ({treatment})" if treatment else ""
    bref = segment.get("borehole_ref") or ""
    _add_text(msp,
              f"MẶT CẮT NGANG ĐIỂN HÌNH XLDY{treatment_label}  [{bref}]",
              origin_x, crest_y + 5.0,
              height=2.0, layer="TEXT125",
              halign=TextEntityAlignment.MIDDLE_CENTER)

    # Slope label
    _add_text(msp, f"1:{taluy:.1f}",
              toe_half + 1.0, origin_y + htk / 2.0,
              height=1.0, layer="TEXTL")


# ---------------------------------------------------------------------------
# Function 3 – Top-level write functions
# ---------------------------------------------------------------------------

def _create_doc():
    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"] = 6  # metres
    _setup_doc(doc)
    return doc


def write_tracdoc_dxf(path: str, segments: list) -> None:
    """Create a trắc dọc XLDY DXF file from segment list and save to path."""
    doc = _create_doc()
    build_tracdoc_xldy(doc, segments)
    doc.saveas(path)


def write_mcn_dxf(path: str, segments: list) -> None:
    """Create MCN điển hình XLDY DXF with one cross-section per segment, tiled horizontally."""
    doc = _create_doc()
    msp = doc.modelspace()

    x_offset = 0.0
    for seg in segments:
        # Estimate horizontal extent so sections don't overlap
        b_nen   = float(seg.get("b_nen") or 12.0)
        htk     = float(seg.get("htk") or 0.0)
        taluy   = float(seg.get("taluy") or 1.5)
        section_width = (b_nen / 2.0 + taluy * htk + 10.0) * 2.0
        build_mcn_xldy(doc, seg, origin_x=x_offset + section_width / 2.0, origin_y=0.0)
        x_offset += section_width + 20.0  # 20 m gap between sections

    doc.saveas(path)


# ---------------------------------------------------------------------------
# CadDrawingApp
# ---------------------------------------------------------------------------

class CadDrawingApp:
    """Prepare/commit pattern app for generating XLDY DXF drawings."""

    def __init__(self, files=None, audit=None):
        self.files = files or {}
        self.audit = audit

    def prepare(self, name: str, args: dict) -> dict:
        """
        Build a plan dict describing what will be written.

        name: 'cad_tracdoc_xldy' or 'cad_mcn_xldy'
        args keys:
            segments_json  – list[dict] or JSON string of segment dicts
            output_dxf     – output file path
        """
        import json

        segments_raw = args.get("segments_json", [])
        if isinstance(segments_raw, str):
            segments = json.loads(segments_raw)
        else:
            segments = segments_raw

        output_path = args.get("output_dxf", "/tmp/xldy_output.dxf")

        if name not in ("cad_tracdoc_xldy", "cad_mcn_xldy"):
            return {"error": f"Unknown drawing name: {name}"}

        return {
            "action": name,
            "segments": segments,
            "output_path": output_path,
        }

    def commit(self, plan: dict) -> dict:
        """Execute the plan and return result dict."""
        if "error" in plan:
            return plan

        action      = plan["action"]
        segments    = plan["segments"]
        output_path = plan["output_path"]

        try:
            if action == "cad_tracdoc_xldy":
                write_tracdoc_dxf(output_path, segments)
            elif action == "cad_mcn_xldy":
                write_mcn_dxf(output_path, segments)
            else:
                return {"error": f"Unknown action: {action}"}

            return {"status": "ok", "output": output_path,
                    "segments": len(segments)}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

"""Extract station+elevation data from road DXF files (trắc dọc + mặt cắt ngang)."""
from __future__ import annotations
import re
import math
from pathlib import Path
from typing import Optional
from collections import defaultdict


def parse_station(text: str) -> Optional[float]:
    """Parse Vietnamese station label to metres.

    Examples: 'KM5+230' → 5230.0, '93+350' → 93350.0, '800.00' → 800.0
    """
    t = text.strip()
    m = re.match(r'(?i)km\s*(\d+)\s*\+\s*(\d+(?:\.\d+)?)', t)
    if m:
        return float(m.group(1)) * 1000.0 + float(m.group(2))
    m = re.match(r'^(\d{1,3})\+(\d{3}(?:\.\d+)?)$', t)
    if m:
        return float(m.group(1)) * 1000.0 + float(m.group(2))
    m = re.match(r'^(\d{3,6}(?:\.\d+)?)$', t)
    if m:
        return float(m.group(1))
    return None


def _decode_text(ent) -> str:
    """Return plain text from a DXF TEXT or MTEXT entity, with TCVN3 fallback."""
    try:
        raw = ent.dxf.text
    except Exception:
        raw = ''
    if raw and any(0x80 <= ord(c) <= 0xFF for c in raw):
        try:
            from .tcvn import tcvn3_to_unicode
            raw = tcvn3_to_unicode(raw.encode('latin-1'))
        except Exception:
            pass
    raw = re.sub(r'\\[A-Za-z][^;]*;', '', raw)
    raw = re.sub(r'[{}]', '', raw)
    raw = raw.replace('\\P', ' ').replace('\n', ' ').strip()
    return raw


def _is_elevation(text: str) -> bool:
    m = re.match(r'^-?\d{1,3}\.\d{2,4}$', text.strip())
    return bool(m)


def _texts_by_layer(msp) -> dict[str, list[tuple[float, float, str]]]:
    result: dict[str, list] = defaultdict(list)
    for ent in msp:
        if ent.dxftype() in ('TEXT', 'ATTDEF', 'MTEXT'):
            try:
                ins = ent.dxf.insert
                txt = _decode_text(ent)
                if txt:
                    result[ent.dxf.layer].append((ins.x, ins.y, txt))
            except Exception:
                pass
    return result


# ── Trắc dọc (longitudinal profile) reader ────────────────────────────────────

# Nova/Civil3D layer names for Vietnamese road profiles
_TD_LAYERS = {
    'acc': 'Prf-acc',    # accumulated station values
    'ege': 'Prf-ege',    # existing ground elevation
    'fge': 'Prf-fge',    # finished grade elevation
    'ctf': 'Prf-ctf',    # cut/fill height
    'xsta': 'XSTA',      # cross-section block annotations
}


def _build_x_to_station(items: list[tuple[float, float]]) -> callable:
    """Build a linear-interpolation function x → station from (drawing_x, station_m) pairs."""
    pairs = sorted(items, key=lambda p: p[0])
    xs = [p[0] for p in pairs]
    vs = [p[1] for p in pairs]

    def interp(x: float) -> float:
        if x <= xs[0]:
            return vs[0]
        if x >= xs[-1]:
            return vs[-1]
        for i in range(len(xs) - 1):
            if xs[i] <= x <= xs[i + 1]:
                dx = xs[i + 1] - xs[i]
                if dx == 0:
                    return vs[i]
                t = (x - xs[i]) / dx
                return vs[i] + t * (vs[i + 1] - vs[i])
        return vs[-1]
    return interp


def read_profile_dxf(path: str | Path) -> list[dict]:
    """Read a trắc dọc DXF → list of {station, ground_elev, design_elev} sorted by station.

    Nova/Civil3D layer convention:
      XSTA    → KM chainage labels (primary station calibration)
      Prf-ege → ground elevation text labels
      Prf-fge → design/finished grade elevation text labels
    Falls back to y-band clustering for generic DXF files.
    """
    import ezdxf

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    by_layer = _texts_by_layer(msp)

    ege_items = by_layer.get(_TD_LAYERS['ege'], [])
    fge_items = by_layer.get(_TD_LAYERS['fge'], [])
    xsta_items = by_layer.get(_TD_LAYERS['xsta'], [])

    # Build x→station calibration from XSTA KM labels (most reliable)
    xsta_pairs = [(x, parse_station(t)) for x, y, t in xsta_items if parse_station(t) is not None]
    if not xsta_pairs:
        # Try Prf-acc as fallback calibration
        acc_items = by_layer.get(_TD_LAYERS['acc'], [])
        xsta_pairs = [(x, parse_station(t)) for x, y, t in acc_items if parse_station(t) is not None]

    if xsta_pairs and (ege_items or fge_items):
        return _read_profile_layer_aware(xsta_pairs, ege_items, fge_items)

    # Fallback: generic y-band clustering
    return _read_profile_generic(by_layer)


def _read_profile_layer_aware(sta_pairs: list[tuple[float, float]], ege_items, fge_items) -> list[dict]:
    """Extract profile points using station calibration pairs + elevation layer items."""
    if not sta_pairs:
        return []

    x_to_sta = _build_x_to_station(sta_pairs)

    result: dict[float, dict] = {}

    def add_elevs(items, key: str):
        for x, y, t in items:
            if _is_elevation(t):
                sta = round(x_to_sta(x), 1)
                if sta not in result:
                    result[sta] = {'station': sta, 'ground_elev': None, 'design_elev': None}
                result[sta][key] = float(t)

    add_elevs(ege_items, 'ground_elev')
    add_elevs(fge_items, 'design_elev')

    return sorted(result.values(), key=lambda r: r['station'])


def _read_profile_generic(by_layer: dict) -> list[dict]:
    """Generic profile reader using y-band clustering (fallback)."""
    texts = [(x, y, t) for items in by_layer.values() for x, y, t in items]
    if not texts:
        return []

    ys = [y for _, y, _ in texts]
    tol = max(0.3, (max(ys) - min(ys)) * 0.01)
    sorted_ys = sorted(ys)
    bands: list[list[float]] = [[sorted_ys[0]]]
    for v in sorted_ys[1:]:
        if abs(v - bands[-1][-1]) <= tol:
            bands[-1].append(v)
        else:
            bands.append([v])
    band_centres = [sum(b) / len(b) for b in bands]

    def nearest(y: float) -> float:
        return min(band_centres, key=lambda b: abs(b - y))

    band_texts: dict[float, list] = defaultdict(list)
    for x, y, txt in texts:
        band_texts[nearest(y)].append((x, txt))

    station_band = max(band_centres, key=lambda b: sum(1 for _, t in band_texts[b] if parse_station(t) is not None))
    sta_pairs = [(x, parse_station(t)) for x, t in band_texts[station_band] if parse_station(t) is not None]
    if not sta_pairs:
        return []

    x_to_sta = _build_x_to_station(sta_pairs)

    elev_bands = sorted(
        [b for b in band_centres if b != station_band and
         sum(1 for _, t in band_texts[b] if _is_elevation(t)) >= 2],
        key=lambda b: sum(1 for _, t in band_texts[b] if _is_elevation(t)),
        reverse=True
    )

    result: dict[float, dict] = {}

    def add_band(band, key: str):
        if band is None:
            return
        for x, t in band_texts[band]:
            if _is_elevation(t):
                sta = round(x_to_sta(x), 1)
                if sta not in result:
                    result[sta] = {'station': sta, 'ground_elev': None, 'design_elev': None}
                result[sta][key] = float(t)

    add_band(elev_bands[0] if elev_bands else None, 'ground_elev')
    add_band(elev_bands[1] if len(elev_bands) > 1 else None, 'design_elev')
    return sorted(result.values(), key=lambda r: r['station'])


# ── XSTA cross-section block reader (from trắc dọc) ───────────────────────────

def read_xsta_blocks(path: str | Path) -> list[dict]:
    """Parse the XSTA layer from a trắc dọc DXF.

    Returns list of {station, htk, b_nen, taluy, borehole_ref} per cross-section.
    The XSTA layer in Nova-generated DXF has paired TEXT entities:
      line 1: 'KM5+900.00'
      line 2: 'Bn=55.5m; taluy 1/1.75'  (or similar)
      line 3: 'Hd = 1.91m'
      line 4: 'KM5-CH01'   (borehole reference)
    All are within ~2m of each other vertically.
    """
    import ezdxf

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    by_layer = _texts_by_layer(msp)

    xsta_items = sorted(by_layer.get('XSTA', []), key=lambda t: (t[0], t[1]))
    if not xsta_items:
        return []

    # Group by proximity: same cross-section annotation cluster within 30 drawing units
    groups: list[list[tuple]] = []
    for item in xsta_items:
        placed = False
        for g in groups:
            if abs(item[0] - g[0][0]) < 30 and abs(item[1] - g[0][1]) < 30:
                g.append(item)
                placed = True
                break
        if not placed:
            groups.append([item])

    result = []
    for g in groups:
        sta = next((parse_station(t) for _, _, t in g if parse_station(t) is not None), None)
        if sta is None:
            continue
        htk = None
        b_nen = None
        taluy = None
        borehole = None

        for _, _, t in g:
            # Hd = 1.91m  (fill height)
            m = re.search(r'[Hh][dk]\s*=\s*([\d.]+)', t)
            if m:
                htk = float(m.group(1))
            # Bn=55.5m or Bn = 55.5
            m = re.search(r'[Bb]n\s*=\s*([\d.]+)', t)
            if m:
                b_nen = float(m.group(1))
            # taluy 1/1.75
            m = re.search(r'taluy\s+([\d.]+/[\d.]+)', t, re.I)
            if m:
                taluy = 'taluy ' + m.group(1)
            # Borehole ref: KM5-CH01, KM-D01, KM6-DYBS01, BH-1, LK-1
            if (re.match(r'(?i)(km[\d\-][^+\s]*|BH[-\d]+|LK[-\d]+)', t)
                    and parse_station(t) is None and '+' not in t):
                borehole = t.strip()

        result.append({
            'station': sta,
            'htk': htk,
            'b_nen': b_nen,
            'taluy': taluy,
            'borehole_ref': borehole,
        })

    return sorted(result, key=lambda r: r['station'])


# ── Mặt cắt ngang (cross-section) reader ──────────────────────────────────────

def read_cross_section_dxf(path: str | Path) -> list[dict]:
    """Read a mặt cắt ngang DXF → list of {station, htk, b_nen, ground_elev, design_elev}.

    Supports Nova/Civil3D MCN DXF with layers:
      XSTA      – station label + section identifier
      XGRIDFGT  – finished grade elevation values (per grid row)
      XGRIDT    – ground terrain elevation values (per grid row)
      XFG       – LWPOLYLINE of the finished grade cross-section shape
    """
    import ezdxf

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    by_layer = _texts_by_layer(msp)

    xsta_items = by_layer.get('XSTA', [])
    fgt_items = by_layer.get('XGRIDFGT', [])
    grdt_items = by_layer.get('XGRIDT', [])

    # Find cross-section anchors (items with station labels)
    anchors: list[tuple[float, float, float]] = []  # (cx, cy, station_m)
    for x, y, t in xsta_items:
        sta = parse_station(t)
        if sta is not None:
            anchors.append((x, y, sta))

    if not anchors:
        return []

    # Dedup: keep only the first occurrence of each station
    seen: set[float] = set()
    unique_anchors = []
    for cx, cy, sta in sorted(anchors, key=lambda a: a[2]):
        if sta not in seen:
            seen.add(sta)
            unique_anchors.append((cx, cy, sta))

    # For each anchor, compute htk and b_nen from nearby elevation labels + XFG shape
    xfg_polys: list[list] = []
    for ent in msp:
        if ent.dxftype() == 'LWPOLYLINE' and ent.dxf.layer == 'XFG':
            try:
                xfg_polys.append(list(ent.get_points()))
            except Exception:
                pass

    result = []
    for cx, cy, sta in unique_anchors:
        radius = 300.0  # drawing units to search around anchor

        # Nearby XGRIDFGT elevations
        fgt_nearby = [(x - cx, float(t)) for x, y, t in fgt_items
                      if abs(x - cx) < radius and abs(y - cy) < radius and _is_elevation(t)]
        # Nearby XGRIDT elevations
        grd_nearby = [(x - cx, float(t)) for x, y, t in grdt_items
                      if abs(x - cx) < radius and abs(y - cy) < radius and _is_elevation(t)]

        # Design elevation at centerline: max value in ±10m of centerline.
        # Avoids picking cross-slope % values (< 5%) which appear near center.
        design_elev = None
        fgt_center = [(dx, v) for dx, v in fgt_nearby if abs(dx) <= 10]
        if not fgt_center:
            fgt_center = fgt_nearby
        if fgt_center:
            design_elev = max(v for _, v in fgt_center)

        # Ground elevation at centerline: max value near center (± 5m)
        ground_elev = None
        grd_center = [(dx, v) for dx, v in grd_nearby if abs(dx) <= 10]
        if not grd_center:
            grd_center = grd_nearby
        if grd_center:
            ground_elev = max(v for _, v in grd_center)

        htk = round(max(0.0, (design_elev or 0.0) - (ground_elev or 0.0)), 3)

        # Base width from XFG polyline extent nearby anchor
        b_nen = None
        for pts in xfg_polys:
            if not pts:
                continue
            if abs(pts[0][0] - cx) < radius and abs(pts[0][1] - cy) < radius:
                xs = [p[0] - cx for p in pts]
                b_nen = round(max(xs) - min(xs), 1)
                break

        result.append({
            'station': sta,
            'htk': htk,
            'b_nen': b_nen,
            'ground_elev': ground_elev,
            'design_elev': design_elev,
        })

    return sorted(result, key=lambda r: r['station'])

"""Extract station+elevation data from a road longitudinal profile DXF (trắc dọc)."""
from __future__ import annotations
import re
import math
from pathlib import Path
from typing import Optional


def parse_station(text: str) -> Optional[float]:
    """Parse Vietnamese station label to metres.

    Examples: 'KM5+230' → 5230.0, '93+350' → 93350.0, '0+000' → 0.0
    Also handles raw numeric strings like '93350' or '93.350' (treated as metres).
    """
    t = text.strip()
    # KM5+230 or KM5+230.5
    m = re.match(r'(?i)km\s*(\d+)\s*\+\s*(\d+(?:\.\d+)?)', t)
    if m:
        return float(m.group(1)) * 1000.0 + float(m.group(2))
    # 93+350 style (no KM prefix)
    m = re.match(r'^(\d{1,3})\+(\d{3}(?:\.\d+)?)$', t)
    if m:
        return float(m.group(1)) * 1000.0 + float(m.group(2))
    # pure integer that looks like a station (>= 100, likely metres)
    m = re.match(r'^(\d{3,6})$', t)
    if m:
        return float(m.group(1))
    return None


def _decode_text(ent) -> str:
    """Return plain text from a DXF TEXT or MTEXT entity, converting TCVN3 if needed."""
    try:
        raw = ent.dxf.text
    except Exception:
        raw = ''
    # ezdxf returns str; check for TCVN3 byte range disguised as latin-1
    if raw and any(0x80 <= ord(c) <= 0xFF for c in raw):
        try:
            from .tcvn import tcvn3_to_unicode
            raw = tcvn3_to_unicode(raw.encode('latin-1'))
        except Exception:
            pass
    # Strip MTEXT control codes (%%c, \P, \n, {}, ...)
    raw = re.sub(r'\\[A-Za-z][^;]*;', '', raw)
    raw = re.sub(r'[{}]', '', raw)
    raw = raw.replace('\\P', ' ').replace('\n', ' ').strip()
    return raw


def _is_elevation(text: str) -> bool:
    """Return True if text looks like a road elevation (e.g. '1.234', '12.345')."""
    m = re.match(r'^-?\d{1,3}\.\d{2,4}$', text.strip())
    return bool(m)


def _cluster_y(values: list[float], tol: float = 0.5) -> list[float]:
    """Cluster y-coordinates into bands and return sorted band centres."""
    if not values:
        return []
    sorted_v = sorted(values)
    bands: list[list[float]] = [[sorted_v[0]]]
    for v in sorted_v[1:]:
        if abs(v - bands[-1][-1]) <= tol:
            bands[-1].append(v)
        else:
            bands.append([v])
    return [sum(b) / len(b) for b in bands]


def read_profile_dxf(path: str | Path) -> list[dict]:
    """Return list of {station, ground_elev, design_elev} sorted by station.

    ground_elev or design_elev may be None if not found in the drawing.
    Works with LWPOLYLINE/LINE profiles and TEXT/MTEXT label rows.
    """
    import ezdxf  # type: ignore

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()

    # Collect all TEXT/MTEXT with their insertion point
    texts: list[tuple[float, float, str]] = []  # (x, y, text)
    for ent in msp:
        if ent.dxftype() in ('TEXT', 'ATTDEF'):
            try:
                ins = ent.dxf.insert
                txt = _decode_text(ent)
                if txt:
                    texts.append((ins.x, ins.y, txt))
            except Exception:
                pass
        elif ent.dxftype() == 'MTEXT':
            try:
                ins = ent.dxf.insert
                txt = _decode_text(ent)
                if txt:
                    texts.append((ins.x, ins.y, txt))
            except Exception:
                pass

    if not texts:
        return []

    # Find y-bands
    ys = [y for _, y, _ in texts]
    bands = _cluster_y(ys, tol=max(0.3, (max(ys) - min(ys)) * 0.01))

    def nearest_band(y: float) -> float:
        return min(bands, key=lambda b: abs(b - y))

    # Group texts by y-band
    from collections import defaultdict
    band_texts: dict[float, list[tuple[float, str]]] = defaultdict(list)
    for x, y, txt in texts:
        band_texts[nearest_band(y)].append((x, txt))

    # Identify station band: band with the most station-looking labels
    def station_score(items: list[tuple[float, str]]) -> int:
        return sum(1 for _, t in items if parse_station(t) is not None)

    station_band = max(bands, key=lambda b: station_score(band_texts[b]))

    # Extract stations sorted by x
    sta_items = sorted(
        [(x, parse_station(t)) for x, t in band_texts[station_band] if parse_station(t) is not None],
        key=lambda p: p[0]
    )
    if not sta_items:
        return []

    sta_x = [p[0] for p in sta_items]
    sta_v = [p[1] for p in sta_items]

    def x_to_station(x: float) -> float:
        """Linear interpolate station from x coordinate."""
        if x <= sta_x[0]:
            return sta_v[0]
        if x >= sta_x[-1]:
            return sta_v[-1]
        for i in range(len(sta_x) - 1):
            if sta_x[i] <= x <= sta_x[i + 1]:
                dx = sta_x[i + 1] - sta_x[i]
                if dx == 0:
                    return sta_v[i]
                t = (x - sta_x[i]) / dx
                return sta_v[i] + t * (sta_v[i + 1] - sta_v[i])
        return sta_v[-1]

    # Identify elevation bands: bands with mostly elevation-like numbers
    def elev_score(items: list[tuple[float, str]]) -> int:
        return sum(1 for _, t in items if _is_elevation(t))

    elev_bands = sorted(
        [b for b in bands if b != station_band and elev_score(band_texts[b]) >= 2],
        key=lambda b: elev_score(band_texts[b]),
        reverse=True
    )

    ground_band: Optional[float] = elev_bands[0] if len(elev_bands) > 0 else None
    design_band: Optional[float] = elev_bands[1] if len(elev_bands) > 1 else None

    # Build output keyed by station
    result: dict[float, dict] = {}

    def add_elev(band: Optional[float], key: str):
        if band is None:
            return
        for x, t in band_texts[band]:
            if _is_elevation(t):
                sta = round(x_to_station(x), 1)
                if sta not in result:
                    result[sta] = {'station': sta, 'ground_elev': None, 'design_elev': None}
                result[sta][key] = float(t)

    add_elev(ground_band, 'ground_elev')
    add_elev(design_band, 'design_elev')

    # Also try to extract elevations from LWPOLYLINE/LINE profile geometry
    # (use vertices to supplement missing text elevations)
    for ent in msp:
        if ent.dxftype() == 'LWPOLYLINE':
            try:
                pts = list(ent.get_points())
                for pt in pts:
                    x, y = pt[0], pt[1]
                    sta = round(x_to_station(x), 1)
                    if sta not in result:
                        result[sta] = {'station': sta, 'ground_elev': None, 'design_elev': None}
                    # Only fill if nothing from text
                    if result[sta]['ground_elev'] is None:
                        result[sta]['ground_elev'] = round(y, 3)
            except Exception:
                pass

    return sorted(result.values(), key=lambda r: r['station'])

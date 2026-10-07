"""Classify road segments and select ground improvement treatment (TCVN 9362:2012)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Segment:
    id: int
    station_from: float          # metres from route origin
    station_to: float
    length: float                # metres
    htk: float                   # design fill height (m)
    hdy: float                   # soft soil total depth (m)
    b_nen: float                 # embankment base width (m)
    borehole_ref: str            # reference borehole name
    ground_elev: float           # natural ground elevation (m)
    layers: list[dict] = field(default_factory=list)
    # layers: [{'code': '1c', 'thickness': 5.2}, ...]
    treatment: str = ''          # 'PVD', 'CDM', 'Đào thay', 'Không xử lý'
    pvd_spacing: float = 0.0     # m (triangular grid)
    pvd_depth: float = 0.0       # m
    geotextile: bool = False
    notes: str = ''


# ---------------------------------------------------------------------------
# Treatment classification
# ---------------------------------------------------------------------------

def classify_treatment(htk: float, hdy: float,
                        soft_layer_params: Optional[dict] = None) -> tuple[str, dict]:
    """Return (treatment_method, params_dict).

    Rules based on TCVN 9362:2012 and common Vietnamese practice:
    ─────────────────────────────────────────────────────────────
    htk < 0.5m or hdy <= 0.5m  → Không xử lý
    htk 0.5–1.5m, hdy 0.5–3m   → Đào thay đất (or cừ tràm if very shallow)
    htk 0.5–1.5m, hdy 3–8m     → PVD spacing 1.5m, gia tải nhẹ
    htk 1.5–4m,   hdy 0.5–3m   → Đào thay đất
    htk 1.5–4m,   hdy 3–8m     → PVD spacing 1.5m, gia tải
    htk > 4m,     hdy 3–8m     → PVD spacing 1.2m, gia tải lớn
    hdy > 8m (any htk)          → CDM hoặc PVD sâu
    Fs_initial < 1.1             → thêm vải địa kỹ thuật
    """
    params: dict = {}
    slp = soft_layer_params or {}
    fs_initial = slp.get('fs_initial', 1.5)

    if htk < 0.5 or hdy <= 0.5:
        method = 'Không xử lý'

    elif hdy > 8.0:
        method = 'CDM'
        params['cdm_depth'] = hdy
        params['cdm_spacing'] = 2.0

    elif hdy <= 3.0:
        method = 'Đào thay'
        params['excavation_depth'] = hdy

    elif htk > 4.0 and hdy > 3.0:
        method = 'PVD'
        params['pvd_spacing'] = 1.2
        params['pvd_depth'] = min(hdy, 20.0)
        params['surcharge_height'] = htk * 0.3

    elif htk >= 1.5 and hdy > 3.0:
        method = 'PVD'
        params['pvd_spacing'] = 1.5
        params['pvd_depth'] = min(hdy, 20.0)
        params['surcharge_height'] = htk * 0.2

    else:
        # htk 0.5–1.5, hdy 3–8
        method = 'PVD'
        params['pvd_spacing'] = 1.5
        params['pvd_depth'] = min(hdy, 15.0)
        params['surcharge_height'] = htk * 0.15

    if fs_initial < 1.1 and method in ('PVD', 'CDM'):
        params['geotextile'] = True

    return method, params


# ---------------------------------------------------------------------------
# Settlement estimate (simplified Terzaghi 1D)
# ---------------------------------------------------------------------------

def _settlement_estimate(htk: float, layers: list[dict]) -> dict:
    """Return simplified settlement components (cm)."""
    gamma_fill = 18.0   # kN/m³ typical
    sigma_z = htk * gamma_fill  # kPa, uniform load from fill

    Sc = 0.0  # primary consolidation
    Si = 0.0  # immediate (elastic)

    for lyr in layers:
        t = lyr.get('thickness', 0.0)
        if t <= 0:
            continue
        cc = lyr.get('Cc', 0.3)
        cs = lyr.get('Cs', 0.05)
        e0 = lyr.get('e0', 1.2)
        pc = lyr.get('Pc', 30.0)   # kPa
        p0 = lyr.get('p0', 20.0)   # in-situ effective stress kPa
        E = lyr.get('E', 1500.0)   # kPa
        nu = lyr.get('nu', 0.35)
        p1 = p0 + sigma_z

        if p1 <= pc:
            Sc += (cs / (1 + e0)) * math.log10(p1 / max(p0, 1.0)) * t * 100
        else:
            Sc += (cs / (1 + e0)) * math.log10(pc / max(p0, 1.0)) * t * 100
            Sc += (cc / (1 + e0)) * math.log10(p1 / max(pc, 1.0)) * t * 100

        Mv = (1 - 2 * nu) / (E * (1 - nu))
        Si += Mv * sigma_z * t * 100

    St = Sc + Si
    Sr = St * 0.15   # residual (rough estimate)
    return {'Sc': round(Sc, 1), 'Si': round(Si, 1), 'St': round(St, 1), 'Sr': round(Sr, 1)}


# ---------------------------------------------------------------------------
# Stability factor (simplified Bishop circular arc, conservative estimate)
# ---------------------------------------------------------------------------

def _fs_estimate(htk: float, hdy: float, layers: list[dict]) -> float:
    """Rough Fs using average shear strength of soft layer vs. driving force."""
    if htk <= 0 or hdy <= 0:
        return 9.9
    # Weighted average Su
    total_t = sum(lyr.get('thickness', 0.0) for lyr in layers if lyr.get('thickness', 0.0) > 0)
    if total_t == 0:
        return 1.5
    su_avg = sum(lyr.get('Su', 15.0) * lyr.get('thickness', 0.0) for lyr in layers) / total_t
    gamma_fill = 18.0
    # Simple formula: Fs ≈ (5.14 * su_avg) / (gamma_fill * htk)
    fs = (5.14 * su_avg) / max(gamma_fill * htk, 1.0)
    return round(min(fs, 9.9), 2)


# ---------------------------------------------------------------------------
# Segmenting the alignment
# ---------------------------------------------------------------------------

def _interp(profile: list[dict], station: float, key: str) -> Optional[float]:
    """Linear interpolate a value from profile list at a given station."""
    pts = [(p['station'], p.get(key)) for p in profile if p.get(key) is not None]
    if not pts:
        return None
    pts.sort()
    if station <= pts[0][0]:
        return pts[0][1]
    if station >= pts[-1][0]:
        return pts[-1][1]
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        if x0 <= station <= x1:
            t = (station - x0) / (x1 - x0) if x1 != x0 else 0.0
            return y0 + t * (y1 - y0)
    return None


def _nearest_borehole(boreholes: list[dict], station: float) -> Optional[dict]:
    if not boreholes:
        return None
    return min(boreholes, key=lambda b: abs(b.get('station', 0.0) - station))


def segment_profile(profile_points: list[dict],
                    boreholes: list[dict],
                    segment_length: float = 200.0,
                    xsta_blocks: Optional[list[dict]] = None,
                    mcn_sections: Optional[list[dict]] = None) -> list[Segment]:
    """Divide the alignment into segments and classify each one.

    profile_points: list of {station, ground_elev, design_elev} from read_profile_dxf.
    boreholes: list of {name, station, ground_elev, layers, hdy, b_nen, ...} dicts.
    segment_length: nominal segment length in metres (default 200 m).

    Returns list of Segment objects with treatment classification and settlement estimates.
    """
    xsta_blocks = xsta_blocks or []
    mcn_sections = mcn_sections or []
    # Build lookup: station → {htk, b_nen} from XSTA blocks (trắc dọc) and MCN
    _xsta_map = {b['station']: b for b in xsta_blocks}
    _mcn_map = {s['station']: s for s in mcn_sections}

    def _nearest_xsta(station: float) -> Optional[dict]:
        if not xsta_blocks:
            return None
        return min(xsta_blocks, key=lambda b: abs(b['station'] - station))

    def _nearest_mcn(station: float) -> Optional[dict]:
        if not mcn_sections:
            return None
        return min(mcn_sections, key=lambda s: abs(s['station'] - station))

    if not profile_points:
        return []

    stations = sorted(p['station'] for p in profile_points)
    sta_min, sta_max = stations[0], stations[-1]

    # Build segment boundaries
    n_segs = max(1, round((sta_max - sta_min) / segment_length))
    boundaries = [sta_min + i * (sta_max - sta_min) / n_segs for i in range(n_segs + 1)]

    segments: list[Segment] = []
    for i in range(n_segs):
        sta_from = boundaries[i]
        sta_to = boundaries[i + 1]
        sta_mid = (sta_from + sta_to) / 2.0

        ground_elev_from = _interp(profile_points, sta_from, 'ground_elev') or 0.0
        ground_elev_to = _interp(profile_points, sta_to, 'ground_elev') or 0.0
        ground_elev_mid = (ground_elev_from + ground_elev_to) / 2.0

        design_elev_from = _interp(profile_points, sta_from, 'design_elev') or ground_elev_from
        design_elev_to = _interp(profile_points, sta_to, 'design_elev') or ground_elev_to
        design_elev_mid = (design_elev_from + design_elev_to) / 2.0

        htk = max(0.0, round(design_elev_mid - ground_elev_mid, 3))

        bh = _nearest_borehole(boreholes, sta_mid)
        hdy = float(bh.get('hdy', 0.0)) if bh else 0.0
        b_nen = float(bh.get('b_nen', 0.0)) if bh else 0.0
        bh_name = bh.get('name', '') if bh else ''
        layers = bh.get('layers', []) if bh else []

        # Refine htk and b_nen from XSTA blocks / MCN sections when borehole lacks them
        xb = _nearest_xsta(sta_mid)
        if xb:
            if htk == 0.0 and xb.get('htk'):
                htk = float(xb['htk'])
            if b_nen == 0.0 and xb.get('b_nen'):
                b_nen = float(xb['b_nen'])
            if not bh_name and xb.get('borehole_ref'):
                bh_name = xb['borehole_ref']
        mcn = _nearest_mcn(sta_mid)
        if mcn:
            if htk == 0.0 and mcn.get('htk'):
                htk = float(mcn['htk'])
            if b_nen == 0.0 and mcn.get('b_nen'):
                b_nen = float(mcn['b_nen'])
        if b_nen == 0.0:
            b_nen = 12.0  # default fallback

        slp = {}
        if bh:
            slp['fs_initial'] = _fs_estimate(htk, hdy, layers)

        method, params = classify_treatment(htk, hdy, slp)

        seg = Segment(
            id=i + 1,
            station_from=round(sta_from, 1),
            station_to=round(sta_to, 1),
            length=round(sta_to - sta_from, 1),
            htk=round(htk, 3),
            hdy=round(hdy, 2),
            b_nen=b_nen,
            borehole_ref=bh_name,
            ground_elev=round(ground_elev_mid, 3),
            layers=layers,
            treatment=method,
            pvd_spacing=params.get('pvd_spacing', 0.0),
            pvd_depth=params.get('pvd_depth', 0.0),
            geotextile=params.get('geotextile', False),
            notes='',
        )
        # Attach settlement + Fs
        if layers and method != 'Không xử lý':
            sett = _settlement_estimate(htk, layers)
            seg.notes = (
                f"Sc={sett['Sc']}cm Si={sett['Si']}cm "
                f"St={sett['St']}cm Sr={sett['Sr']}cm "
                f"Fs={slp.get('fs_initial', 0.0)}"
            )
        segments.append(seg)

    return segments


def segments_to_dicts(segments: list[Segment]) -> list[dict]:
    """Serialise Segment list to plain dicts for JSON / THSH writer."""
    result = []
    for s in segments:
        d = {
            'id': s.id,
            'station_from': s.station_from,
            'station_to': s.station_to,
            'length': s.length,
            'htk': s.htk,
            'hdy': s.hdy,
            'b_nen': s.b_nen,
            'borehole_ref': s.borehole_ref,
            'ground_elev': s.ground_elev,
            'layers': s.layers,
            'treatment': s.treatment,
            'pvd_spacing': s.pvd_spacing,
            'pvd_depth': s.pvd_depth,
            'geotextile': s.geotextile,
            'notes': s.notes,
        }
        # parse settlement from notes for THSH
        import re as _re
        notes = s.notes
        for key in ('Sc', 'Si', 'St', 'Sr', 'Fs'):
            m = _re.search(rf'{key}=([\d.]+)', notes)
            d[key] = float(m.group(1)) if m else None
        result.append(d)
    return result

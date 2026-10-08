"""Generate DXF drawings for CDM (Cement Deep Mixing) pile treatment layout.

Produces two views in one DXF file:
 - Cross-section (mặt cắt ngang): road surface + CDM pile schematic
 - Plan view (mặt bằng): road outline + CDM pile grid (top view)
"""

import json
import math
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from .windows_apps import fingerprint

UNITS_MAP = {'mm': 4, 'cm': 5, 'm': 6, 'inch': 1}


def _add_text(msp, text, x, y, height=0.8, layer='TEXT', color=7, align=None):
    from ezdxf.enums import TextEntityAlignment
    if align is None:
        align = TextEntityAlignment.MIDDLE_CENTER
    t = msp.add_text(text, dxfattribs={'height': height, 'layer': layer, 'color': color})
    t.set_placement((x, y), align=align)
    return t


def build_cdm_dxf(b_road, l_treatment, d_pile, pile_depth, spacing_x, spacing_y, units='m'):
    """
    Build and return an ezdxf document with CDM pile layout drawings.

    Args:
        b_road      – road/treatment width (m or units)
        l_treatment – treatment length along road axis
        d_pile      – CDM pile diameter
        pile_depth  – CDM pile depth (vertical)
        spacing_x   – transverse pile spacing (across width)
        spacing_y   – longitudinal pile spacing (along length)
        units       – drawing units string: 'mm', 'cm', 'm', 'inch'
    """
    import ezdxf
    from ezdxf.enums import TextEntityAlignment

    doc = ezdxf.new('R2010')
    doc.units = UNITS_MAP.get(units, 6)

    for lname, color in [('ROAD', 2), ('GROUND', 3), ('CDM-PILE', 5),
                          ('CDM-ZONE', 4), ('DIM', 6), ('TEXT', 7), ('TITLE', 1)]:
        if lname not in doc.layers:
            doc.layers.new(lname).color = color

    msp = doc.modelspace()
    r = d_pile / 2.0
    half_b = b_road / 2.0

    # ------------------------------------------------------------------
    # Cross-section (Mặt cắt ngang) — centred at x=0, ground at y=0
    # ------------------------------------------------------------------
    ext = half_b + 3.0

    # Natural ground line
    msp.add_line((-ext, 0), (ext, 0), dxfattribs={'layer': 'GROUND', 'color': 3})

    # CDM treatment zone boundary
    zone = [(-half_b, 0), (half_b, 0),
            (half_b, -pile_depth), (-half_b, -pile_depth), (-half_b, 0)]
    msp.add_lwpolyline(zone, close=True, dxfattribs={'layer': 'CDM-ZONE', 'color': 4})

    # Hatch the treatment zone
    try:
        hatch = msp.add_hatch(color=253, dxfattribs={'layer': 'CDM-ZONE'})
        hatch.set_pattern_fill('DOTS', scale=0.3)
        hatch.paths.add_polyline_path(zone, is_closed=True)
    except Exception:
        pass

    # CDM pile columns: stacked circles (schematic vertical section)
    # Column x positions centred on road
    n_cols = max(1, round(b_road / spacing_x)) + 1
    x_first = -math.floor(half_b / spacing_x) * spacing_x
    xs = []
    x = x_first
    while x <= half_b + 1e-9:
        if -half_b - 1e-9 <= x <= half_b + 1e-9:
            xs.append(x)
        x += spacing_x
    # Circles per column (one circle per diameter step going down)
    n_rings = max(1, round(pile_depth / (2 * r)))
    for cx in xs:
        for row in range(n_rings):
            cy = -r - row * 2 * r
            if cy - r >= -pile_depth - 1e-9:
                msp.add_circle((cx, cy), r, dxfattribs={'layer': 'CDM-PILE', 'color': 5})

    # Road surface slab
    road_h = max(0.3, b_road * 0.03)  # thin road slab proportional to scale
    road_pts = [(-half_b, 0), (half_b, 0),
                (half_b, road_h), (-half_b, road_h), (-half_b, 0)]
    msp.add_lwpolyline(road_pts, close=True, dxfattribs={'layer': 'ROAD', 'color': 2})

    # Dimension: road width B (above road slab)
    dh = road_h + 1.2
    msp.add_line((-half_b, dh), (half_b, dh), dxfattribs={'layer': 'DIM', 'color': 6})
    for ex in (-half_b, half_b):
        msp.add_line((ex, dh - 0.25), (ex, dh + 0.25), dxfattribs={'layer': 'DIM', 'color': 6})
    _add_text(msp, f'B={b_road:.0f}{units}', 0, dh + 0.5)

    # Dimension: pile depth (right side)
    dx = half_b + 2.0
    msp.add_line((dx, 0), (dx, -pile_depth), dxfattribs={'layer': 'DIM', 'color': 6})
    for ey in (0, -pile_depth):
        msp.add_line((dx - 0.25, ey), (dx + 0.25, ey), dxfattribs={'layer': 'DIM', 'color': 6})
    _add_text(msp, f'H={pile_depth:.0f}{units}', dx + 0.6, -pile_depth / 2,
              align=TextEntityAlignment.MIDDLE_LEFT)

    # Annotations below section
    ann_y = -pile_depth - 1.5
    _add_text(msp, f'Cọc CDM D={d_pile:.2g}{units}, H={pile_depth:.0f}{units}', 0, ann_y)
    _add_text(msp, f'Lưới {spacing_x:.2g}×{spacing_y:.2g}{units}', 0, ann_y - 1.2)

    # Section title
    _add_text(msp, 'MẶT CẮT NGANG BỐ TRÍ CỌC CDM',
              0, road_h + 3.0, height=1.2, color=1, layer='TITLE')

    # ------------------------------------------------------------------
    # Plan view (Mặt bằng) — placed to the right
    # ------------------------------------------------------------------
    gap = ext + 6.0
    ox = gap          # x-origin of plan view (left edge)
    oy = 0.0          # y-origin (top edge = ground level)

    # Road rectangle outline
    plan_pts = [(ox, oy), (ox + l_treatment, oy),
                (ox + l_treatment, oy - b_road), (ox, oy - b_road), (ox, oy)]
    msp.add_lwpolyline(plan_pts, close=True, dxfattribs={'layer': 'ROAD', 'color': 2})

    # CDM pile circles (top view)
    # Grid layout: centre within road
    n_long  = max(1, round(l_treatment / spacing_y))
    n_trans = max(1, round(b_road    / spacing_x))
    # First pile position (centred grid)
    x0 = ox + (l_treatment - (n_long  - 1) * spacing_y) / 2.0
    y0 = oy - (b_road      - (n_trans - 1) * spacing_x) / 2.0
    for i in range(n_long):
        px = x0 + i * spacing_y
        if px < ox - 1e-9 or px > ox + l_treatment + 1e-9:
            continue
        for j in range(n_trans):
            py = y0 - j * spacing_x
            if py > oy + 1e-9 or py < oy - b_road - 1e-9:
                continue
            msp.add_circle((px, py), r, dxfattribs={'layer': 'CDM-PILE', 'color': 5})

    cx_plan = ox + l_treatment / 2.0
    cy_plan = oy - b_road / 2.0

    # Dimension: width B (left of plan)
    dx_plan = ox - 2.0
    msp.add_line((dx_plan, oy), (dx_plan, oy - b_road), dxfattribs={'layer': 'DIM', 'color': 6})
    for ey in (oy, oy - b_road):
        msp.add_line((dx_plan - 0.25, ey), (dx_plan + 0.25, ey), dxfattribs={'layer': 'DIM', 'color': 6})
    _add_text(msp, f'B={b_road:.0f}{units}', dx_plan - 0.6, cy_plan,
              align=TextEntityAlignment.MIDDLE_RIGHT)

    # Dimension: length L (above plan)
    dy_plan = oy + 1.8
    msp.add_line((ox, dy_plan), (ox + l_treatment, dy_plan), dxfattribs={'layer': 'DIM', 'color': 6})
    for ex in (ox, ox + l_treatment):
        msp.add_line((ex, dy_plan - 0.25), (ex, dy_plan + 0.25), dxfattribs={'layer': 'DIM', 'color': 6})
    _add_text(msp, f'L={l_treatment:.0f}{units}', cx_plan, dy_plan + 0.5)

    # Pile info below plan
    ann_y2 = oy - b_road - 1.5
    _add_text(msp, f'Cọc CDM D={d_pile:.2g}{units}, H={pile_depth:.0f}{units}', cx_plan, ann_y2)
    _add_text(msp, f'Lưới {spacing_x:.2g}×{spacing_y:.2g}{units}', cx_plan, ann_y2 - 1.2)
    # Pile count
    total_piles = n_long * n_trans
    _add_text(msp, f'Tổng số cọc: {total_piles} cọc', cx_plan, ann_y2 - 2.4)

    # Plan title
    _add_text(msp, 'MẶT BẰNG BỐ TRÍ CỌC CDM',
              cx_plan, oy + 3.5, height=1.2, color=1, layer='TITLE')

    return doc


class CdmLayoutApp:
    """Prepare/commit pattern for CDM pile layout DXF creation + AutoCAD launch."""

    def __init__(self, windows, files, audit):
        self.windows = windows
        self.files   = files
        self.audit   = audit

    def prepare(self, name, args):
        self.windows.check()
        app = self.windows.allowed_path(args['app'])
        if app.name.lower() not in {'acad.exe', 'acadlt.exe'}:
            raise ValueError('Chọn acad.exe hoặc acadlt.exe đã được phép.')

        def _pos(key):
            v = args[key]
            if not isinstance(v, (int, float)) or v <= 0:
                raise ValueError(f'{key} phải là số dương.')
            return float(v)

        b_road     = _pos('b_road')
        l_treatment = _pos('l_treatment')
        d_pile     = _pos('d_pile')
        pile_depth = _pos('pile_depth')
        spacing_x  = _pos('spacing_x')
        spacing_y  = _pos('spacing_y')
        units      = args.get('units', 'm')
        if units not in UNITS_MAP:
            raise ValueError('units phải là mm, cm, m hoặc inch.')

        if not self.files.roots:
            raise PermissionError('Thêm thư mục lưu bản vẽ trong Cài đặt.')
        path = self.files.path(
            str(self.files.roots[0] / ('CDM-' + uuid.uuid4().hex[:8] + '.dxf')),
            exists=False)

        return {
            'action': 'cad_cdm_layout',
            'app': str(app),
            'sha256': fingerprint(app),
            'path': str(path),
            'b_road': b_road, 'l_treatment': l_treatment,
            'd_pile': d_pile, 'pile_depth': pile_depth,
            'spacing_x': spacing_x, 'spacing_y': spacing_y,
            'units': units,
        }

    def commit(self, plan):
        self.windows.check()
        app = self.windows.allowed_path(plan['app'])
        if fingerprint(app) != plan['sha256']:
            raise PermissionError('EXE AutoCAD đã thay đổi; không mở.')

        doc = build_cdm_dxf(
            b_road=plan['b_road'],
            l_treatment=plan['l_treatment'],
            d_pile=plan['d_pile'],
            pile_depth=plan['pile_depth'],
            spacing_x=plan['spacing_x'],
            spacing_y=plan['spacing_y'],
            units=plan['units'],
        )

        path = self.files.path(plan['path'], exists=False)
        if path.exists():
            raise FileExistsError('Không ghi đè bản vẽ đã có.')

        with tempfile.TemporaryDirectory(prefix='.cdm-', dir=path.parent) as folder:
            tmp = Path(folder) / 'drawing.dxf'
            doc.saveas(tmp)
            self.windows.check()
            self.files.path(str(path), exists=False)
            with path.open('xb') as out, tmp.open('rb') as src:
                shutil.copyfileobj(src, out)

        self.audit('cad_document_created', {
            'path': str(path), 'type': 'cdm_layout',
            'b_road': plan['b_road'], 'd_pile': plan['d_pile'],
            'pile_depth': plan['pile_depth'],
        })

        self.windows.check()
        if fingerprint(app) != plan['sha256']:
            raise PermissionError('Đã tạo DXF nhưng EXE AutoCAD đã thay đổi; chưa mở.')
        subprocess.Popen([str(app), str(path)], shell=False)

        n_long  = max(1, round(plan['l_treatment'] / plan['spacing_y']))
        n_trans = max(1, round(plan['b_road']       / plan['spacing_x']))
        return {
            'ok': True,
            'path': str(path),
            'total_piles': n_long * n_trans,
            'document_created': True,
            'cad_launch_requested': True,
            'note': (
                f"Đã tạo DXF bố trí cọc CDM ({n_long}×{n_trans}={n_long * n_trans} cọc). "
                "Gồm mặt cắt ngang và mặt bằng. Đã gửi lệnh mở AutoCAD."
            ),
        }

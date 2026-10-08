"""Generate a standard Vietnamese geotechnical borehole log (trụ địa chất) as DXF."""
from __future__ import annotations

import json
import math
import shutil
import tempfile
import uuid
from pathlib import Path

# Map soil category to a standard hatch pattern
_CATEGORY_HATCH = {
    'Đất dính': 'EARTH',       # clay/silt
    'Đất rời': 'AR-SAND',      # sand/gravel
    'Đất hữu cơ': 'SWAMP',     # peat/organic
    'Đá': 'ANSI31',            # rock
}
_DEFAULT_HATCH = 'EARTH'

# Column layout (x positions, all in metres for a 1:50 log)
_COL = {
    'depth_label': 0.0,    # depth axis labels
    'depth_line': 1.5,     # depth line x
    'soil_col': 1.5,       # soil column left
    'soil_w': 3.0,         # soil column width
    'name_col': 4.5,       # layer name text x
    'gamma_col': 8.0,
    'e0_col': 9.5,
    'cc_col': 11.0,
    'c_col': 12.5,
    'phi_col': 14.0,
    'spt_col': 15.5,
    'total_w': 17.0,
}
_ROW_H = 1.0           # 1 m thickness = 1 drawing unit (1:100 scale)
_FONT = '.VnArial'     # TrueType Unicode — no TCVN3 conversion needed
_TXT_H = 0.18          # text height in drawing units
_HEADER_H = 0.5        # header row height


def _header_text(model, x, y, content, h=None):
    h = h or _TXT_H
    from ezdxf.enums import TextEntityAlignment
    t = model.add_text(content, dxfattribs={'height': h, 'layer': 'HEADER',
                                             'style': 'BOREHOLE'})
    t.set_placement((x, y), align=TextEntityAlignment.MIDDLE_CENTER)


def _cell_text(model, x, y, content, layer='DATA'):
    from ezdxf.enums import TextEntityAlignment
    t = model.add_text(str(content), dxfattribs={'height': _TXT_H, 'layer': layer,
                                                  'style': 'BOREHOLE'})
    t.set_placement((x, y), align=TextEntityAlignment.MIDDLE_CENTER)


def _fmt(v, decimals=2):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return ''
    if v == 0.0:
        return ''
    return f'{v:.{decimals}f}'


def build_borehole_dxf(doc, borehole_name: str, ground_elev: float,
                       water_depth: float, soils: list[dict]):
    import ezdxf
    from ezdxf.enums import TextEntityAlignment

    model = doc.modelspace()

    # Register text style
    try:
        st = doc.styles.new('BOREHOLE')
    except Exception:
        st = doc.styles.get('BOREHOLE')
    st.font = _FONT

    # Layers
    for lname, color in [('BORDER', 7), ('HEADER', 1), ('DATA', 7),
                          ('HATCH', 3), ('DEPTH', 2), ('WATER', 5)]:
        try:
            doc.layers.new(lname, dxfattribs={'color': color})
        except Exception:
            pass

    total_depth = sum(s.get('thickness', 0) for s in soils)
    log_h = total_depth * _ROW_H  # drawing height
    top_y = _HEADER_H + log_h
    W = _COL['total_w']

    # ── Outer border ─────────────────────────────────────────────────────────
    model.add_lwpolyline([
        (0, 0), (W, 0), (W, top_y), (0, top_y)
    ], close=True, dxfattribs={'layer': 'BORDER'})

    # ── Column dividers ───────────────────────────────────────────────────────
    for x in (_COL['depth_line'], _COL['soil_col'] + _COL['soil_w'],
              _COL['name_col'] + 3.0, _COL['gamma_col'] + 1.0,
              _COL['e0_col'] + 1.0, _COL['cc_col'] + 1.0,
              _COL['c_col'] + 1.0, _COL['phi_col'] + 1.0, _COL['spt_col'] + 1.5):
        model.add_line((x, 0), (x, top_y), dxfattribs={'layer': 'BORDER'})

    # ── Headers ───────────────────────────────────────────────────────────────
    hy = top_y - _HEADER_H / 2
    headers = [
        (_COL['depth_label'] + 0.75, 'Sâu (m)'),
        (_COL['soil_col'] + _COL['soil_w'] / 2, 'Trụ địa chất'),
        (_COL['name_col'] + 1.5, 'Tên lớp đất'),
        (_COL['gamma_col'] + 0.5, 'γ (kN/m³)'),
        (_COL['e0_col'] + 0.5, 'e₀'),
        (_COL['cc_col'] + 0.5, 'Cc'),
        (_COL['c_col'] + 0.5, 'c (kPa)'),
        (_COL['phi_col'] + 0.5, 'φ (°)'),
        (_COL['spt_col'] + 0.75, 'N-SPT'),
    ]
    model.add_line((0, top_y - _HEADER_H), (W, top_y - _HEADER_H),
                   dxfattribs={'layer': 'BORDER'})
    for hx, htxt in headers:
        _header_text(model, hx, hy, htxt)

    # Title above header
    title = f'TRỤ ĐỊA CHẤT – {borehole_name}  |  Cao độ mặt đất: {ground_elev:.2f} m'
    _header_text(model, W / 2, top_y + 0.3, title, h=_TXT_H * 1.5)

    # ── Rows per soil layer ───────────────────────────────────────────────────
    cum_depth = 0.0
    for soil in soils:
        thick = float(soil.get('thickness') or 0)
        row_h = thick * _ROW_H
        y_top = top_y - _HEADER_H - cum_depth * _ROW_H
        y_bot = y_top - row_h
        y_mid = (y_top + y_bot) / 2

        # Horizontal separator
        model.add_line((0, y_bot), (W, y_bot), dxfattribs={'layer': 'BORDER'})

        # Depth label at bottom of layer
        depth_val = cum_depth + thick
        _cell_text(model, _COL['depth_label'] + 0.75, y_bot + _TXT_H / 2,
                   f'{depth_val:.1f}', layer='DEPTH')

        # Hatch in soil column
        cat = soil.get('category', 'Đất dính')
        pattern = _CATEGORY_HATCH.get(cat, _DEFAULT_HATCH)
        sx = _COL['soil_col']
        sw = _COL['soil_w']
        boundary = [(sx, y_bot), (sx + sw, y_bot),
                    (sx + sw, y_top), (sx, y_top), (sx, y_bot)]
        hatch = model.add_hatch(dxfattribs={'layer': 'HATCH'})
        hatch.set_pattern_fill(pattern, scale=0.3)
        with hatch.edit_boundary() as ed:
            ed.add_polyline_path(boundary, is_closed=True)

        # Layer data
        _cell_text(model, _COL['name_col'] + 1.5, y_mid,
                   soil.get('name', ''), layer='DATA')
        _cell_text(model, _COL['gamma_col'] + 0.5, y_mid,
                   _fmt(soil.get('gamma'), 1))
        _cell_text(model, _COL['e0_col'] + 0.5, y_mid,
                   _fmt(soil.get('e0'), 3))
        _cell_text(model, _COL['cc_col'] + 0.5, y_mid,
                   _fmt(soil.get('cc'), 3))
        _cell_text(model, _COL['c_col'] + 0.5, y_mid,
                   _fmt(soil.get('cohesion_c'), 1))
        _cell_text(model, _COL['phi_col'] + 0.5, y_mid,
                   _fmt(soil.get('friction_phi'), 1))
        spt = soil.get('spt_n')
        _cell_text(model, _COL['spt_col'] + 0.75, y_mid,
                   _fmt(spt, 0) if spt else '')

        cum_depth += thick

    # ── Water table line ──────────────────────────────────────────────────────
    if water_depth and water_depth > 0:
        wy = top_y - _HEADER_H - water_depth * _ROW_H
        if 0 < wy < top_y - _HEADER_H:
            wattribs = {'layer': 'WATER', 'linetype': 'DASHED'}
            try:
                doc.linetypes.add('DASHED')
            except Exception:
                pass
            model.add_line((_COL['soil_col'], wy),
                           (_COL['soil_col'] + _COL['soil_w'], wy), dxfattribs=wattribs)
            _cell_text(model, _COL['soil_col'] - 0.3, wy, 'MNN', layer='WATER')


class BoreholeDxfApp:
    def __init__(self, files, windows, audit):
        self.files = files
        self.windows = windows
        self.audit = audit

    def prepare(self, name, args):
        from .windows_apps import fingerprint
        app = self.windows.allowed_path(args['app'])
        if app.name.lower() not in {'acad.exe', 'acadlt.exe'}:
            raise ValueError('Chọn acad.exe hoặc acadlt.exe đã được phép.')
        borehole_name = str(args.get('borehole_name', 'BH-1')).strip()[:50]
        ground_elev = float(args.get('ground_elevation', 0.0))
        water_depth = float(args.get('water_depth', 0.0))
        soils_raw = args['soils']
        if not isinstance(soils_raw, str) or len(soils_raw) > 100_000:
            raise ValueError('soils phải là chuỗi JSON tối đa 100000 ký tự.')
        soils = json.loads(soils_raw)
        if not isinstance(soils, list) or not 1 <= len(soils) <= 50:
            raise ValueError('soils phải là mảng 1–50 lớp.')
        for i, s in enumerate(soils):
            if not isinstance(s, dict):
                raise ValueError(f'Lớp {i+1} phải là đối tượng JSON.')
            if not s.get('name'):
                s['name'] = f'Lớp {i+1}'
        if not self.files.roots:
            raise PermissionError('Thêm thư mục lưu bản vẽ được phép trong Cài đặt.')
        path = self.files.path(
            str(self.files.roots[0] / f'BH-{uuid.uuid4().hex[:8]}.dxf'), exists=False)
        return {
            'action': 'borehole_dxf',
            'app': str(app), 'sha256': fingerprint(app),
            'path': str(path),
            'borehole_name': borehole_name,
            'ground_elevation': ground_elev,
            'water_depth': water_depth,
            'soils': soils,
        }

    def commit(self, plan):
        from .windows_apps import fingerprint
        import ezdxf
        import subprocess
        app = self.windows.allowed_path(plan['app'])
        if fingerprint(app) != plan['sha256']:
            raise PermissionError('EXE AutoCAD đã thay đổi.')
        doc = ezdxf.new('R2010')
        doc.units = 6  # metres
        build_borehole_dxf(doc, plan['borehole_name'],
                           plan['ground_elevation'], plan['water_depth'],
                           plan['soils'])
        path = self.files.path(plan['path'], exists=False)
        if path.exists():
            raise FileExistsError('Không ghi đè bản vẽ đã có.')
        with tempfile.TemporaryDirectory(prefix='.bh-', dir=path.parent) as folder:
            tmp = Path(folder) / 'borehole.dxf'
            doc.saveas(tmp)
            self.windows.check()
            with path.open('xb') as out, tmp.open('rb') as src:
                shutil.copyfileobj(src, out)
        self.audit('borehole_dxf_created', {'path': str(path),
                                             'borehole': plan['borehole_name'],
                                             'layers': len(plan['soils'])})
        self.windows.check()
        app = self.windows.allowed_path(plan['app'])
        if fingerprint(app) != plan['sha256']:
            raise PermissionError('Đã tạo DXF nhưng EXE AutoCAD đã thay đổi; chưa mở.')
        subprocess.Popen([str(app), str(path)], shell=False)
        return {
            'ok': True, 'path': str(path),
            'borehole_name': plan['borehole_name'],
            'layers': len(plan['soils']),
            'note': 'Đã tạo trụ địa chất DXF và gửi lệnh mở AutoCAD.',
        }

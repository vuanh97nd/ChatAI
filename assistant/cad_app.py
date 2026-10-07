"""Create a fresh, validated DXF and open the authorized CAD executable."""
import json
import math
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from .windows_apps import fingerprint

UNITS = {'mm': 4, 'cm': 5, 'm': 6, 'inch': 1}

# Whitelist of safe standard hatch patterns
HATCH_PATTERNS = {
    'ANSI31', 'ANSI32', 'ANSI33', 'ANSI34', 'ANSI35', 'ANSI36', 'ANSI37', 'ANSI38',
    'AR-SAND', 'AR-CONC', 'AR-BRIK', 'AR-RSHKE', 'AR-HBONE', 'AR-PARQ1',
    'DOTS', 'EARTH', 'GRASS', 'GRAVEL', 'NET', 'SOLID', 'CROSS', 'DASH',
    'DOLMIT', 'FLEX', 'GRATE', 'HEX', 'HONEY', 'INSUL', 'LINE',
    'MUDST', 'PLAST', 'SACNCR', 'SQUARE', 'STARS', 'STEEL', 'SWAMP',
    'TRANS', 'TRIANG', 'ZIGZAG',
}

_LINETYPES = {'CONTINUOUS', 'DASHED', 'DOTTED', 'CENTER', 'PHANTOM', 'HIDDEN'}


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 1e9:
        raise ValueError('Tọa độ/kích thước phải là số hữu hạn, tối đa 1e9.')
    return float(value)


def _point2d(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('Điểm phải là [x, y].')
    return [_number(v) for v in value]


def _layer_name(value):
    if not isinstance(value, str) or not value or len(value) > 255:
        raise ValueError('Tên layer phải là chuỗi 1–255 ký tự.')
    if any(c in value for c in '<>/\\:;?*|="\''):
        raise ValueError('Tên layer chứa ký tự không hợp lệ.')
    return value


def _validate_layers(raw_layers):
    if raw_layers is None:
        return []
    if not isinstance(raw_layers, list) or len(raw_layers) > 50:
        raise ValueError('layers phải là danh sách tối đa 50 phần tử.')
    result = []
    names = set()
    for item in raw_layers:
        if not isinstance(item, dict):
            raise ValueError('Mỗi layer phải là đối tượng JSON.')
        name = _layer_name(item.get('name', ''))
        if name in names:
            raise ValueError(f'Tên layer trùng: {name!r}')
        names.add(name)
        color = item.get('color', 7)
        if not isinstance(color, int) or not 1 <= color <= 256:
            raise ValueError('color phải là số nguyên ACI 1–256.')
        linetype = item.get('linetype', 'CONTINUOUS')
        if linetype not in _LINETYPES:
            raise ValueError(f'linetype phải là một trong: {", ".join(sorted(_LINETYPES))}')
        result.append({'name': name, 'color': color, 'linetype': linetype})
    return result


def entities_from_json(raw):
    if not isinstance(raw, str) or len(raw) > 300000:
        raise ValueError('entities phải là chuỗi JSON tối đa 300000 ký tự.')
    rows = json.loads(raw)
    if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
        raise ValueError('Cần 1–500 hình.')
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Hình phải là đối tượng JSON.')
        kind = row.get('type')
        base_keys = set(row) - {'layer'}

        if kind == 'circle':
            if base_keys != {'type', 'center', 'radius'}:
                raise ValueError('circle cần center, radius.')
            shape = {'type': kind, 'center': _point2d(row['center']), 'radius': _number(row['radius'])}
            if shape['radius'] <= 0:
                raise ValueError('Bán kính phải dương.')

        elif kind == 'line':
            if base_keys != {'type', 'start', 'end'}:
                raise ValueError('line cần start, end.')
            shape = {'type': kind, 'start': _point2d(row['start']), 'end': _point2d(row['end'])}
            if shape['start'] == shape['end']:
                raise ValueError('Hai đầu đoạn thẳng phải khác nhau.')

        elif kind == 'rectangle':
            if base_keys != {'type', 'origin', 'width', 'height'}:
                raise ValueError('rectangle cần origin, width, height.')
            shape = {'type': kind, 'origin': _point2d(row['origin']),
                     'width': _number(row['width']), 'height': _number(row['height'])}
            if shape['width'] <= 0 or shape['height'] <= 0:
                raise ValueError('Chiều rộng/cao phải dương.')

        elif kind == 'polyline':
            if base_keys - {'closed'} != {'type', 'points'}:
                raise ValueError('polyline cần points, tùy chọn closed.')
            points = row['points']
            if not isinstance(points, list) or not 2 <= len(points) <= 2000:
                raise ValueError('polyline cần 2–2000 điểm.')
            closed = row.get('closed', False)
            if not isinstance(closed, bool):
                raise ValueError('closed phải là true/false.')
            shape = {'type': kind, 'points': [_point2d(p) for p in points], 'closed': closed}

        elif kind == 'hatch':
            if base_keys - {'angle', 'scale'} != {'type', 'boundary', 'pattern'}:
                raise ValueError('hatch cần boundary, pattern; tùy chọn angle, scale.')
            boundary = row['boundary']
            if not isinstance(boundary, list) or not 3 <= len(boundary) <= 2000:
                raise ValueError('hatch boundary cần 3–2000 điểm.')
            pattern = row['pattern']
            if not isinstance(pattern, str) or pattern.upper() not in HATCH_PATTERNS:
                raise ValueError(f'pattern phải là một trong: {", ".join(sorted(HATCH_PATTERNS))}')
            scale = _number(row.get('scale', 1.0))
            if scale <= 0:
                raise ValueError('scale phải dương.')
            angle = _number(row.get('angle', 0.0))
            shape = {'type': kind, 'boundary': [_point2d(p) for p in boundary],
                     'pattern': pattern.upper(), 'scale': scale, 'angle': angle}

        elif kind == 'text':
            if base_keys - {'rotation', 'halign', 'valign'} != {'type', 'insert', 'content', 'height'}:
                raise ValueError('text cần insert, content, height; tùy chọn rotation, halign, valign.')
            content = row['content']
            if not isinstance(content, str) or not content or len(content) > 1000:
                raise ValueError('content phải là chuỗi 1–1000 ký tự.')
            height = _number(row['height'])
            if height <= 0:
                raise ValueError('height phải dương.')
            rotation = _number(row.get('rotation', 0.0))
            halign = row.get('halign', 'LEFT')
            if halign not in {'LEFT', 'CENTER', 'RIGHT'}:
                raise ValueError('halign phải là LEFT/CENTER/RIGHT.')
            valign = row.get('valign', 'BASELINE')
            if valign not in {'BASELINE', 'BOTTOM', 'MIDDLE', 'TOP'}:
                raise ValueError('valign phải là BASELINE/BOTTOM/MIDDLE/TOP.')
            shape = {'type': kind, 'insert': _point2d(row['insert']), 'content': content,
                     'height': height, 'rotation': rotation, 'halign': halign, 'valign': valign}

        elif kind == 'dim_linear':
            if base_keys - {'text_override'} != {'type', 'start', 'end', 'dimline'}:
                raise ValueError('dim_linear cần start, end, dimline; tùy chọn text_override.')
            text_override = row.get('text_override', '')
            if not isinstance(text_override, str) or len(text_override) > 200:
                raise ValueError('text_override tối đa 200 ký tự.')
            shape = {'type': kind, 'start': _point2d(row['start']), 'end': _point2d(row['end']),
                     'dimline': _point2d(row['dimline']), 'text_override': text_override}

        else:
            raise ValueError(f'Loại hình không hỗ trợ: {kind!r}. Dùng: circle, line, rectangle, polyline, hatch, text, dim_linear.')

        if 'layer' in row:
            shape['layer'] = _layer_name(row['layer'])
        result.append(shape)
    return result


def _apply_layer(attribs, shape):
    if 'layer' in shape:
        attribs['layer'] = shape['layer']
    return attribs


def _build_dxf(doc, shapes):
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    model = doc.modelspace()
    _ALIGN = {
        ('LEFT',   'BASELINE'): TextEntityAlignment.LEFT,
        ('CENTER', 'BASELINE'): TextEntityAlignment.CENTER,
        ('RIGHT',  'BASELINE'): TextEntityAlignment.RIGHT,
        ('LEFT',   'BOTTOM'):   TextEntityAlignment.BOTTOM_LEFT,
        ('CENTER', 'BOTTOM'):   TextEntityAlignment.BOTTOM_CENTER,
        ('RIGHT',  'BOTTOM'):   TextEntityAlignment.BOTTOM_RIGHT,
        ('LEFT',   'MIDDLE'):   TextEntityAlignment.MIDDLE_LEFT,
        ('CENTER', 'MIDDLE'):   TextEntityAlignment.MIDDLE_CENTER,
        ('RIGHT',  'MIDDLE'):   TextEntityAlignment.MIDDLE_RIGHT,
        ('LEFT',   'TOP'):      TextEntityAlignment.TOP_LEFT,
        ('CENTER', 'TOP'):      TextEntityAlignment.TOP_CENTER,
        ('RIGHT',  'TOP'):      TextEntityAlignment.TOP_RIGHT,
    }
    for row in shapes:
        attrs = _apply_layer({}, row)
        kind = row['type']
        if kind == 'circle':
            model.add_circle(row['center'], row['radius'], dxfattribs=attrs)
        elif kind == 'line':
            model.add_line(row['start'], row['end'], dxfattribs=attrs)
        elif kind == 'rectangle':
            x, y = row['origin']; w, h = row['width'], row['height']
            model.add_lwpolyline([(x, y), (x+w, y), (x+w, y+h), (x, y+h)], close=True, dxfattribs=attrs)
        elif kind == 'polyline':
            model.add_lwpolyline(row['points'], close=row['closed'], dxfattribs=attrs)
        elif kind == 'hatch':
            hatch = model.add_hatch(dxfattribs=attrs)
            hatch.set_pattern_fill(row['pattern'], scale=row['scale'], angle=row['angle'])
            with hatch.edit_boundary() as editor:
                editor.add_polyline_path(row['boundary'], is_closed=True)
        elif kind == 'text':
            align = _ALIGN.get((row['halign'], row['valign']), TextEntityAlignment.LEFT)
            text_attrs = {**attrs, 'height': row['height'], 'rotation': row['rotation']}
            t = model.add_text(row['content'], dxfattribs=text_attrs)
            t.set_placement(row['insert'], align=align)
        elif kind == 'dim_linear':
            dim_attrs = {**attrs}
            dim = model.add_linear_dim(
                base=row['dimline'], p1=row['start'], p2=row['end'],
                dxfattribs=dim_attrs,
                override={'text': row['text_override']} if row.get('text_override') else None,
            )
            dim.render()


class CadApp:
    def __init__(self, windows, files, audit):
        self.windows, self.files, self.audit = windows, files, audit

    def prepare(self, name, args):
        self.windows.check()
        app = self.windows.allowed_path(args['app'])
        if app.name.lower() not in {'acad.exe', 'acadlt.exe'}:
            raise ValueError('Chọn acad.exe hoặc acadlt.exe đã được phép.')
        units = args['units']
        if units not in UNITS:
            raise ValueError('Đơn vị phải là mm, cm, m hoặc inch.')
        shapes = entities_from_json(args['entities'])
        layers = _validate_layers(args.get('layers'))
        if not self.files.roots:
            raise PermissionError('Thêm thư mục lưu bản vẽ được phép trong Cài đặt.')
        path = self.files.path(str(self.files.roots[0] / ('ChatAI-' + uuid.uuid4().hex + '.dxf')), exists=False)
        return {'action': 'cad_create_open', 'app': str(app), 'sha256': fingerprint(app),
                'path': str(path), 'units': units, 'entities': shapes, 'layers': layers}

    def commit(self, plan):
        self.windows.check()
        app = self.windows.allowed_path(plan['app'])
        if fingerprint(app) != plan['sha256']:
            raise PermissionError('EXE AutoCAD đã thay đổi.')
        shapes = entities_from_json(json.dumps(plan['entities']))
        layers = _validate_layers(plan.get('layers'))
        import ezdxf
        doc = ezdxf.new('R2010')
        doc.units = UNITS[plan['units']]
        # Create declared layers
        for ldef in layers:
            layer = doc.layers.new(ldef['name'])
            layer.color = ldef['color']
            if ldef['linetype'] != 'CONTINUOUS':
                doc.linetypes.add(ldef['linetype'], description=ldef['linetype'])
                layer.linetype = ldef['linetype']
        _build_dxf(doc, shapes)
        path = self.files.path(plan['path'], exists=False)
        if path.exists():
            raise FileExistsError('Không ghi đè bản vẽ đã có.')
        with tempfile.TemporaryDirectory(prefix='.cad-', dir=path.parent) as folder:
            temporary = Path(folder) / 'drawing.dxf'
            doc.saveas(temporary)
            self.windows.check()
            self.files.path(str(path), exists=False)
            with path.open('xb') as out, temporary.open('rb') as source:
                shutil.copyfileobj(source, out)
        self.audit('cad_document_created', {'path': str(path), 'units': plan['units'],
                                             'entities': len(shapes), 'layers': len(layers)})
        self.windows.check()
        app = self.windows.allowed_path(plan['app'])
        if fingerprint(app) != plan['sha256']:
            raise PermissionError('Đã tạo DXF nhưng EXE AutoCAD đã thay đổi; chưa mở.')
        subprocess.Popen([str(app), str(path)], shell=False)
        return {'ok': True, 'path': str(path), 'units': plan['units'],
                'entities': len(shapes), 'layers': len(layers),
                'document_created': True, 'cad_launch_requested': True,
                'note': 'Đã tạo DXF mới và gửi lệnh mở AutoCAD; chưa xác minh cửa sổ. Không sửa bản vẽ đang mở, không tạo DWG.'}

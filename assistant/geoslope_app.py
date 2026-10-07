"""Generate a GeoSlope/W .gsz XML file for slope stability analysis."""
import json
import math
import uuid
from pathlib import Path
from xml.etree import ElementTree as ET


VALID_METHODS = {'Bishop', 'Morgenstern-Price', 'Spencer', 'Janbu', 'Ordinary'}


def _num(value, name, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} phải là số hữu hạn.')
    if not lo <= value <= hi:
        raise ValueError(f'{name} phải trong khoảng [{lo}, {hi}].')
    return float(value)


def _parse_problem(raw):
    if not isinstance(raw, str) or len(raw) > 50000:
        raise ValueError('problem phải là chuỗi JSON tối đa 50000 ký tự.')
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f'problem không phải JSON hợp lệ: {exc}') from exc
    if not isinstance(data, dict):
        raise ValueError('problem phải là đối tượng JSON.')

    # --- slope ---
    slope = data.get('slope')
    if not isinstance(slope, dict):
        raise ValueError('slope phải là đối tượng JSON.')
    height = _num(slope.get('height', None) if slope.get('height') is not None else float('nan'),
                  'slope.height', 0.1, 200)
    angle = _num(slope.get('angle', None) if slope.get('angle') is not None else float('nan'),
                 'slope.angle', 5, 85)
    crest_width = _num(slope.get('crest_width', 5.0), 'slope.crest_width', 0.0, 1000)
    toe_width = _num(slope.get('toe_width', 20.0), 'slope.toe_width', 0.0, 1000)

    # --- materials ---
    raw_mats = data.get('materials', [])
    if not isinstance(raw_mats, list) or not 1 <= len(raw_mats) <= 20:
        raise ValueError('materials phải là danh sách 1–20 vật liệu.')
    materials = []
    for i, m in enumerate(raw_mats):
        if not isinstance(m, dict):
            raise ValueError(f'materials[{i}] phải là đối tượng JSON.')
        name = m.get('name', '')
        if not isinstance(name, str) or not 1 <= len(name) <= 100:
            raise ValueError(f'materials[{i}].name phải là chuỗi 1–100 ký tự.')
        cohesion = _num(m.get('cohesion', 0), f'materials[{i}].cohesion', 0, 500)
        phi = _num(m.get('phi', 0), f'materials[{i}].phi', 0, 60)
        uw = _num(m.get('unit_weight', 18), f'materials[{i}].unit_weight', 10, 30)
        model = m.get('model', 'MohrCoulomb')
        if model not in {'MohrCoulomb', 'Undrained'}:
            raise ValueError(f'materials[{i}].model phải là MohrCoulomb hoặc Undrained.')
        materials.append({'name': name, 'cohesion': cohesion, 'phi': phi,
                          'unit_weight': uw, 'model': model})

    # --- layers ---
    raw_layers = data.get('layers', [])
    if not isinstance(raw_layers, list) or not 1 <= len(raw_layers) <= 20:
        raise ValueError('layers phải là danh sách 1–20 lớp.')
    layers = []
    for i, lyr in enumerate(raw_layers):
        if not isinstance(lyr, dict):
            raise ValueError(f'layers[{i}] phải là đối tượng JSON.')
        midx = lyr.get('material_index', 0)
        if not isinstance(midx, int) or not 0 <= midx < len(materials):
            raise ValueError(f'layers[{i}].material_index ngoài phạm vi.')
        top_y = _num(lyr.get('top_y', 0), f'layers[{i}].top_y', -1000, 1000)
        bot_y = _num(lyr.get('bottom_y', -5), f'layers[{i}].bottom_y', -1000, 1000)
        if bot_y >= top_y:
            raise ValueError(f'layers[{i}].bottom_y phải nhỏ hơn top_y.')
        layers.append({'material_index': midx, 'top_y': top_y, 'bottom_y': bot_y})

    # --- method ---
    method = data.get('method', 'Bishop')
    if method not in VALID_METHODS:
        raise ValueError(f'method phải là một trong: {", ".join(sorted(VALID_METHODS))}')

    # --- water table ---
    wt = data.get('water_table', None)
    if wt is not None:
        wt = _num(wt, 'water_table', -1000, 1000)

    return {
        'slope': {'height': height, 'angle': angle,
                  'crest_width': crest_width, 'toe_width': toe_width},
        'materials': materials,
        'layers': layers,
        'method': method,
        'water_table': wt,
    }


def _build_geometry(slope_def, layers):
    """
    Build points and lines for a simple layered slope.

    Profile (left to right, bottom to top):
      A (0, bot_y) – B (toe_width, bot_y) – toe point
      slope face from toe to crest
      crest extends crest_width to the right

    For each layer we generate a horizontal boundary at top_y clipped to the
    slope face and the extents.
    """
    h = slope_def['height']
    angle_rad = math.radians(slope_def['angle'])
    crest_w = slope_def['crest_width']
    toe_w = slope_def['toe_width']
    run = h / math.tan(angle_rad)  # horizontal distance of slope face

    # Model extent
    x_left = 0.0
    x_toe = toe_w
    x_crest = toe_w + run
    x_right = x_crest + crest_w

    # Global Y extents from layers
    bottom_y = min(lyr['bottom_y'] for lyr in layers)
    top_y = max(lyr['top_y'] for lyr in layers)
    # top_y should equal h (slope height) or close
    top_y_model = max(top_y, h)

    # Helper: x on slope face for a given y (0 at toe base, h at crest)
    def slope_x_at_y(y):
        return x_toe + (y / h) * run if h > 0 else x_toe

    # --- Build point list ---
    pts = []  # list of (x, y)
    pt_id = {}  # (x,y) -> 1-based id

    def add_pt(x, y):
        x = round(x, 6)
        y = round(y, 6)
        key = (x, y)
        if key not in pt_id:
            pts.append(key)
            pt_id[key] = len(pts)
        return pt_id[key]

    # Outer boundary (counter-clockwise):
    # bottom-left → bottom-right → slope toe → slope crest → top-right → top-left
    p_bl = add_pt(x_left, bottom_y)
    p_br = add_pt(x_right, bottom_y)
    p_toe = add_pt(x_toe, bottom_y)   # toe at base level
    # slope toe at ground level (y=0 if layers start at 0)
    ground_y = 0.0
    p_toe_ground = add_pt(x_toe, ground_y)
    p_crest = add_pt(x_crest, top_y_model)
    p_tr = add_pt(x_right, top_y_model)
    p_tl = add_pt(x_left, top_y_model)

    # Layer boundary points
    layer_pts = {}  # layer_i -> list of point ids for top boundary
    for i, lyr in enumerate(layers):
        ty = lyr['top_y']
        by = lyr['bottom_y']
        # For each layer, top boundary is a horizontal line (or slope-intersected)
        # intersect with slope face
        if ty <= 0 or ty >= top_y_model:
            # fully below or above slope; horizontal line
            p_l = add_pt(x_left, ty)
            p_r = add_pt(x_right, ty)
            layer_pts[i] = {'top': (p_l, p_r), 'top_y': ty}
        else:
            # slope face intersects this level
            sx = slope_x_at_y(ty)
            p_l = add_pt(x_left, ty)
            p_s = add_pt(sx, ty)
            p_r = add_pt(x_right, ty)
            layer_pts[i] = {'top': (p_l, p_s, p_r), 'top_y': ty, 'slope_x': sx}

    # --- Build lines ---
    lines = []  # list of (pt1_id, pt2_id)
    line_id = {}

    def add_line(a, b):
        key = (min(a, b), max(a, b))
        if key not in line_id:
            lines.append((a, b))
            line_id[key] = len(lines)
        return line_id[key]

    # Outer boundary lines
    add_line(p_bl, p_toe)
    add_line(p_toe, p_toe_ground)
    add_line(p_toe_ground, p_crest)   # slope face
    add_line(p_crest, p_tr)
    add_line(p_tr, p_br)
    add_line(p_br, p_bl)
    add_line(p_tl, p_tr)
    add_line(p_bl, p_tl)

    # Layer horizontal boundaries
    for i, lyr in enumerate(layers):
        ldata = layer_pts[i]
        tp = ldata['top']
        for j in range(len(tp) - 1):
            add_line(tp[j], tp[j + 1])

    # --- Build regions ---
    regions = []
    for i, lyr in enumerate(layers):
        # Determine bounding line IDs for this region (simplified: record all line ids)
        mat_idx = lyr['material_index']
        # Region defined by enclosing boundary – collect relevant line ids
        # (GeoSlope uses LineIDs list; we just list all line ids for now)
        region_lines = list(range(1, len(lines) + 1))
        regions.append({'material_index': mat_idx, 'line_ids': region_lines})

    return pts, lines, regions


def _build_gsz_xml(problem, pts, lines, regions):
    root = ET.Element('SLOPE_MODEL', Version='10')

    # General
    ET.SubElement(root, 'General', Units='Metric', LengthUnits='Meters',
                  StressUnits='kPa', WeightUnits='kN')

    # Materials
    mats_el = ET.SubElement(root, 'Materials')
    for i, mat in enumerate(problem['materials'], start=1):
        ET.SubElement(mats_el, 'Material',
                      ID=str(i),
                      Name=mat['name'],
                      Model=mat['model'],
                      Cohesion=str(mat['cohesion']),
                      Phi=str(mat['phi']),
                      UnitWeight=str(mat['unit_weight']))

    # Geometry
    geo_el = ET.SubElement(root, 'Geometry')

    pts_el = ET.SubElement(geo_el, 'Points')
    for pid, (x, y) in enumerate(pts, start=1):
        ET.SubElement(pts_el, 'Point', ID=str(pid), X=str(x), Y=str(y))

    lines_el = ET.SubElement(geo_el, 'Lines')
    for lid, (p1, p2) in enumerate(lines, start=1):
        ET.SubElement(lines_el, 'Line', ID=str(lid), Pt1=str(p1), Pt2=str(p2))

    regions_el = ET.SubElement(geo_el, 'Regions')
    for rid, reg in enumerate(regions, start=1):
        mat_id = reg['material_index'] + 1  # 1-based
        reg_el = ET.SubElement(regions_el, 'Region', ID=str(rid), MaterialID=str(mat_id))
        line_ids_el = ET.SubElement(reg_el, 'LineIDs')
        line_ids_el.text = ' '.join(str(lid) for lid in reg['line_ids'])

    # Analysis
    ET.SubElement(root, 'Analysis',
                  Method=problem['method'],
                  SlipSurfaceType='Circular',
                  NumberOfSlices='30',
                  Tolerance='0.001',
                  MaxIterations='200')

    # Slip Surface (auto range)
    slope = problem['slope']
    ET.SubElement(root, 'SlipSurface',
                  Type='Circular',
                  MinRadius=str(round(slope['height'] * 0.5, 2)),
                  MaxRadius=str(round(slope['height'] * 3.0, 2)))

    # Water table
    if problem['water_table'] is not None:
        ET.SubElement(root, 'WaterTable', PiezometricLevel=str(problem['water_table']))

    return root


def _to_xml_bytes(root):
    ET.indent(root, space='  ')
    tree = ET.ElementTree(root)
    import io
    buf = io.BytesIO()
    tree.write(buf, encoding='utf-8', xml_declaration=True)
    return buf.getvalue()


class GeoslopeApp:
    def __init__(self, files, audit):
        self.files = files
        self.audit = audit

    def prepare(self, name, args):
        project_name = args.get('project_name', '')
        if not isinstance(project_name, str) or not 1 <= len(project_name) <= 100:
            raise ValueError('project_name phải là chuỗi 1–100 ký tự.')
        # Strip dangerous characters
        safe_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_- áàảãạăắặằẳẵâấầẩẫậđéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵÁÀẢÃẠĂẮẶẰẲẴÂẤẦẨẪẬĐÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴ')
        if any(c in project_name for c in '<>/\\:;?*|="\''):
            raise ValueError('project_name chứa ký tự không hợp lệ.')

        problem = _parse_problem(args.get('problem', ''))

        if not self.files.roots:
            raise PermissionError('Thêm thư mục lưu file được phép trong Cài đặt.')

        safe_name = project_name.replace(' ', '_')
        filename = f'GeoSlope-{safe_name}-{uuid.uuid4().hex[:8]}.gsz'
        path = self.files.path(str(self.files.roots[0] / filename), exists=False)

        return {
            'action': 'geoslope_create',
            'path': str(path),
            'project_name': project_name,
            'problem': problem,
        }

    def commit(self, plan):
        problem = plan['problem']
        slope_def = problem['slope']
        layers = problem['layers']

        pts, lines, regions = _build_geometry(slope_def, layers)
        xml_root = _build_gsz_xml(problem, pts, lines, regions)
        xml_bytes = _to_xml_bytes(xml_root)

        path = self.files.path(plan['path'], exists=False)
        if path.exists():
            raise FileExistsError('Không ghi đè file GeoSlope đã có.')

        with path.open('xb') as f:
            f.write(xml_bytes)

        self.audit('geoslope_file_created', {
            'path': str(path),
            'method': problem['method'],
            'materials': len(problem['materials']),
        })

        return {
            'ok': True,
            'path': str(path),
            'method': problem['method'],
            'materials': len(problem['materials']),
            'note': 'Mở file .gsz bằng GeoStudio/GeoSlope để chạy phân tích.',
        }

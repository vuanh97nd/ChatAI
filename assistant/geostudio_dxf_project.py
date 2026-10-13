"""Build a new GSZ from explicit DXF regions, never an old cross-section."""
import json
import math
import uuid
import zipfile
from types import SimpleNamespace
from xml.etree import ElementTree as ET

from .files import digest


def finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name + ' phải là số hữu hạn.')
    return value


def build_project(dxf_path, spec):
    import ezdxf
    from shapely.geometry import Polygon
    from .geoslope_xldy_writer import _build_xml
    if spec.get('units') != 'm' or not spec.get('coordinate_source'):
        raise ValueError('Cần units=m và coordinate_source xác nhận tỷ lệ/mốc cao độ.')
    name = spec.get('analysis')
    if not isinstance(name, str) or not name.strip():
        raise ValueError('Cần tên analysis mới.')
    method = spec.get('method')
    if method not in {'Bishop', 'Morgenstern-Price', 'Spencer', 'Janbu', 'Ordinary'}:
        raise ValueError('Cần phương pháp tính được chọn rõ.')
    materials = spec.get('materials')
    regions = spec.get('regions')
    if not isinstance(materials, list) or not 1 <= len(materials) <= 100 or not isinstance(regions, list) or not 1 <= len(regions) <= 500:
        raise ValueError('Cần materials (1–100) và regions (1–500).')
    names = {}
    mats = []
    for item in materials:
        if not isinstance(item, dict) or not isinstance(item.get('name'), str) or not item['name'] or item['name'] in names:
            raise ValueError('Tên vật liệu phải duy nhất.')
        if item.get('model') not in ('MohrCoulomb', 'UndrainedPhiZero') or not item.get('source'):
            raise ValueError('Cần model và nguồn thông số; không dùng vật liệu mẫu.')
        fields = ['gamma', 'cohesion'] if item['model'] == 'UndrainedPhiZero' else ['gamma', 'c_prime', 'phi_prime']
        for field in fields:
            v = finite(item.get(field), field)
            if v < 0 or field == 'gamma' and v == 0 or field == 'phi_prime' and v >= 90:
                raise ValueError('Thông số vật liệu ngoài miền hợp lệ.')
        names[item['name']] = len(mats) + 1
        mats.append(dict(item, id=len(mats) + 1))
    document = ezdxf.readfile(dxf_path)
    points = []
    point_ids = {}
    polygons = []
    rings = []
    assignments = []
    handles = set()
    for region in regions:
        if not isinstance(region, dict) or region.get('material') not in names or not isinstance(region.get('handle'), str):
            raise ValueError('Mỗi vùng cần handle DXF và tên material đã cung cấp.')
        handle = region['handle'].upper()
        if handle in handles:
            raise ValueError('Không dùng cùng handle cho hai vùng.')
        handles.add(handle)
        entity = document.entitydb.get(handle)
        if entity is None or entity.dxftype() != 'LWPOLYLINE' or not entity.closed or entity.dxf.elevation != 0:
            raise ValueError('Vùng phải là LWPOLYLINE khép kín 2D; không chọn đường mặt đất hở.')
        vertices = list(entity.get_points('xyb'))
        if len(vertices) > 5000 or any(b != 0 for x, y, b in vertices):
            raise ValueError('Không tự làm thẳng bulge hoặc xử lý quá 5000 đỉnh/vùng.')
        xy = [(finite(x, 'x'), finite(y, 'y')) for x, y, b in vertices]
        if len(xy) > 1 and xy[-1] == xy[0]:
            xy.pop()
        polygon = Polygon(xy)
        if not polygon.is_valid or polygon.area <= 1e-10 or any(polygon.intersection(p).area > 1e-8 for p in polygons):
            raise ValueError('Vùng tự cắt, mất diện tích hoặc chồng lấn.')
        polygons.append(polygon)
        ring = []
        for pair in xy:
            if pair not in point_ids:
                point_ids[pair] = len(points) + 1
                points.append(pair)
            ring.append(point_ids[pair])
        rings.append(ring)
        assignments.append(names[region['material']])
    # Reuse only the known file-format scaffold; remove its entire geometry,
    # material and slip-search content before inserting explicit project input.
    scaffold = SimpleNamespace(HALF_W=1, hdy=1, htk=1, BOTTOM=1, x_right=1,
        build_geometry_xml=lambda: ('', []), build_slip_surface_xml=lambda: '')
    root = ET.fromstring(_build_xml('New CAD project', 'New analysis', method, scaffold, [], []))
    root.find('./Analyses/Analysis/Name').text = name
    geometry = root.find('./Geometries/Geometry')
    geometry.clear()
    ET.SubElement(geometry, 'Name').text = 'DXF geometry'
    pts = ET.SubElement(geometry, 'Points', Len=str(len(points)))
    for i, (x, y) in enumerate(points, 1):
        ET.SubElement(pts, 'Point', ID=str(i), X=str(x), Y=str(y))
    edges = {}
    for ring in rings:
        for a, b in zip(ring, ring[1:] + ring[:1]):
            edges.setdefault(tuple(sorted((a, b))), (a, b))
    lines = ET.SubElement(geometry, 'Lines', Len=str(len(edges)))
    for i, (a, b) in enumerate(edges.values(), 1):
        line = ET.SubElement(lines, 'Line')
        for tag, value in [('ID', i), ('PointID1', a), ('PointID2', b)]:
            ET.SubElement(line, tag).text = str(value)
    region_node = ET.SubElement(geometry, 'Regions', Len=str(len(rings)))
    for i, ring in enumerate(rings, 1):
        region = ET.SubElement(region_node, 'Region')
        ET.SubElement(region, 'ID').text = str(i)
        ET.SubElement(region, 'PointIDs').text = ','.join(map(str, ring))
    material_node = root.find('Materials')
    material_node.clear()
    material_node.set('Len', str(len(mats)))
    for mat in mats:
        node = ET.SubElement(material_node, 'Material')
        ET.SubElement(node, 'ID').text = str(mat['id'])
        ET.SubElement(node, 'Name').text = mat['name']
        ET.SubElement(node, 'SlopeModel').text = mat['model']
        ET.SubElement(node, 'Color').text = 'RGB=(200,200,200)'
        ss = ET.SubElement(node, 'StressStrain')
        fields = [('UnitWeight', 'gamma')]
        fields += [('Cohesion', 'cohesion')] if mat['model'] == 'UndrainedPhiZero' else [('CohesionPrime', 'c_prime'), ('PhiPrime', 'phi_prime')]
        for tag, field in fields:
            ET.SubElement(ss, tag).text = str(mat[field])
    distribution = root.find('./Contexts/Context/GeometryUsesMaterials')
    distribution.clear()
    distribution.set('Len', str(len(assignments)))
    for i, material in enumerate(assignments, 1):
        ET.SubElement(distribution, 'GeometryUsesMaterial', ID=f'Regions-{i}', Entry=str(material))
    xmin, ymin, xmax, ymax = polygons[0].bounds
    for p in polygons[1:]:
        x1, y1, x2, y2 = p.bounds
        xmin, ymin, xmax, ymax = min(xmin, x1), min(ymin, y1), max(xmax, x2), max(ymax, y2)
    view = root.find('./Coordinates/EngCoords')
    view.set('XPageLeft', str(xmin)); view.set('XPageRight', str(xmax))
    view.set('YPageBottom', str(ymin)); view.set('YPageTop', str(ymax))
    stability = root.find('./StabilityItems/StabilityItem/Entry')
    stability.clear()  # Never inherit an unrelated template's search region.
    context = root.find('./Contexts/Context/IsDefined')
    context.text = 'false'
    root.find('./WaterItems/WaterItem/Entry').clear()
    return root, {'analysis': name, 'points': len(points), 'regions': len(rings),
                  'materials': len(mats), 'pending': ['water', 'loads', 'slip_search', 'native_project_validation'],
                  'solved': False, 'ready_to_solve': False}


class GeoStudioDxfProject:
    def __init__(self, files):
        self.files = files

    def prepare(self, name, args):
        path = self.files.path(args['path'])
        if path.suffix.lower() != '.dxf':
            raise ValueError('Cần DXF nguồn trong whitelist.')
        spec = json.loads(args['spec']) if isinstance(args['spec'], str) else args['spec']
        if not isinstance(spec, dict):
            raise ValueError('spec phải là đối tượng JSON.')
        root, info = build_project(str(path), spec)
        output = self.files.path(str(path.parent / ('ChatAI-NewSlope-' + uuid.uuid4().hex[:12] + '.gsz')), exists=False)
        return {'action': name, 'path': str(path), 'sha256': digest(path), 'output': str(output),
                'xml': ET.tostring(root, encoding='unicode'), 'spec': spec, 'info': info}

    def commit(self, plan):
        source = self.files.path(plan['path'])
        if digest(source) != plan['sha256']:
            raise ValueError('DXF đã đổi; không dùng dữ liệu cũ.')
        output = self.files.path(plan['output'], exists=False)
        with output.open('xb') as stream:
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(output.stem + '.xml', plan['xml'].encode('utf-8'))
        sidecar = self.files.path(str(output.with_suffix('.inputs.json')), exists=False)
        with sidecar.open('x', encoding='utf-8') as stream:
            json.dump({'source_dxf': str(source), 'sha256': plan['sha256'], 'spec': plan['spec'], **plan['info']}, stream, ensure_ascii=False, indent=2)
        return {'ok': True, 'output': str(output), 'inputs': str(sidecar), **plan['info'],
                'note': 'Dự án MỚI dạng nháp: hình học/vật liệu từ DXF và số liệu, không lấy mặt cắt cũ. '
                        'Chưa cấu hình nước/tải/miền trượt hoặc xác minh GeoStudio; không chạy Solve/báo Fs.'}

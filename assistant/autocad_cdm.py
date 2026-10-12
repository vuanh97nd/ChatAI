"""Bounded local JSON adapter for the AutoCAD palette; no COM, shell or LLM code."""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys
from typing import Any

from .cdm_layout import build_cdm_dxf
from .cdm_boundary import layout_in_boundary, add_piles
from .cad_tracdoc import build_tracdoc_dxf


def number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name}: cần số hữu hạn.')
    if abs(value) > 1e6 or (positive and value <= 0):
        raise ValueError(f'{name}: ngoài giới hạn.')
    return float(value)


def build(plan: dict[str, Any]):
    if not isinstance(plan, dict) or set(plan) != {'action', 'parameters'}:
        raise ValueError('Cần action và parameters; không nhận đường dẫn/lệnh từ AI.')
    action, p = plan['action'], plan['parameters']
    if not isinstance(p, dict):
        raise ValueError('parameters phải là object.')
    if action == 'cdm_boundary':
        import ezdxf
        keys={'units','boundary','d_pile','spacing_x','spacing_y','edge_clearance','angle_deg'}
        if set(p)!=keys or p['units'] not in {'m','mm','cm','inch'}:
            raise ValueError('Cần vùng đã chọn, đơn vị và D/sx/sy/khoảng lùi/góc lưới.')
        pts=p['boundary']
        if not isinstance(pts,list) or not 3<=len(pts)<=500:
            raise ValueError('Vùng phải có 3–500 đỉnh.')
        vertices=[]
        for pt in pts:
            if not isinstance(pt,list) or len(pt)!=2:raise ValueError('Đỉnh phải là [x,y].')
            vertices.append(tuple(number(v,'tọa độ') for v in pt))
        doc=ezdxf.new('R2010')
        doc.units={'m':6,'mm':4,'cm':5,'inch':1}[p['units']]
        boundary=doc.modelspace().add_lwpolyline(vertices,close=True)
        layout=layout_in_boundary(doc,boundary.dxf.handle,p['d_pile'],p['spacing_x'],p['spacing_y'],
                                  p['units'],p['edge_clearance'],p['angle_deg'])
        add_piles(doc,layout)
        return doc, {'pile_count':len(layout['centers']),
                     'note':'Mặt bằng cọc trong polyline đã chọn; tọa độ WCS và đơn vị vùng được giữ nguyên. DXF mới, không sửa DWG nguồn.'}
    if action in {'cdm_layout', 'cdm_section'}:
        keys = {'b_road', 'l_treatment', 'd_pile', 'pile_depth', 'spacing_x', 'spacing_y'}
        if set(p) != keys | {'units'} or p['units'] != 'm':
            raise ValueError('Cần đủ B/L/D/H/sx/sy và units=m; tất cả kích thước tính bằng mét.')
        values = {k: number(p[k], k, positive=True) for k in keys}
        if values['d_pile'] > min(values['spacing_x'], values['spacing_y']):
            raise ValueError('Chưa hỗ trợ cọc chồng lấn.')
        if values['d_pile'] > min(values['b_road'], values['l_treatment']):
            raise ValueError('Đường kính lớn hơn vùng xử lý.')
        count = max(1, round(values['b_road']/values['spacing_x'])) * max(1, round(values['l_treatment']/values['spacing_y']))
        if count > 10000 or values['b_road']/values['spacing_x'] > 10000:
            raise ValueError('Vượt 10000 cọc; chia vùng xử lý.')
        doc = build_cdm_dxf(**values, units='m')
        # Reuse the section generator, but replace its rounded rectangular grid
        # with the existing containment-aware grid so full piles stay inside.
        msp = doc.modelspace()
        for entity in list(msp.query('CIRCLE[layer=="CDM-PILE"]')):
            msp.delete_entity(entity)
        boundary = next(e for e in msp.query('LWPOLYLINE[layer=="ROAD"]')
                        if min(v[0] for v in e.get_points()) > values['b_road']/2)
        layout = layout_in_boundary(doc, boundary.dxf.handle, values['d_pile'],
                                    values['spacing_y'], values['spacing_x'], 'm')
        add_piles(doc, layout)
        for entity in msp.query('TEXT'):
            if entity.dxf.text.startswith('Tổng số cọc:'):
                entity.dxf.text = f'Tổng số cọc: {len(layout["centers"])} cọc'
        return doc, {'pile_count': len(layout['centers']),
                     'note': 'Mặt bằng và mặt cắt sơ đồ CDM trong cùng DXF, đơn vị m. ROAD là ký hiệu, không phải kết cấu đường thiết kế.'}
    if action == 'cdm_profile':
        if set(p) != {'units', 'points', 'vertical_scale'} or p['units'] != 'm':
            raise ValueError('Cần units=m, points và vertical_scale.')
        points = p['points']
        if not isinstance(points, list) or not 2 <= len(points) <= 500:
            raise ValueError('Cần 2–500 điểm trắc dọc.')
        scale = number(p['vertical_scale'], 'vertical_scale', positive=True)
        if scale > 100:
            raise ValueError('Hệ số phóng đứng tối đa 100.')
        required = {'station', 'ground_elev', 'design_elev', 'pile_top_elev', 'pile_depth'}
        for point in points:
            if not isinstance(point, dict) or not required <= set(point) or set(point) - required - {'pile_name'}:
                raise ValueError('Mỗi điểm cần lý trình, cao độ TN/TK/đầu cọc và chiều sâu cọc.')
            for k in required:
                number(point[k], k, positive=k == 'pile_depth')
        if any(b['station'] <= a['station'] for a, b in zip(points, points[1:])):
            raise ValueError('Lý trình phải tăng nghiêm ngặt; không tự sắp xếp dữ liệu.')
        doc = build_tracdoc_dxf(points, title='TRẮC DỌC CDM', units='m', v_scale=scale)
        msp = doc.modelspace()
        ground = next(iter(msp.query('LWPOLYLINE[layer=="KS-TUY-2401-Trắc dọc tự nhiên"]')))
        ground_xy = list(ground.get_points('xy'))
        doc.layers.new('CDM-TOP', dxfattribs={'color': 5})
        doc.layers.new('CDM-TOE', dxfattribs={'color': 6})
        tops, toes = [], []
        for point, (x, y) in zip(points, ground_xy):
            top = y + (point['pile_top_elev']-point['ground_elev']) * scale
            toe = top - point['pile_depth'] * scale
            tops.append((x, top)); toes.append((x, toe))
            msp.add_line((x, top), (x, toe), dxfattribs={'layer': 'CDM-TOE'})
            msp.add_text(f'H={point["pile_depth"]:g}m', dxfattribs={
                'insert': (x, toe-2), 'height': 1.5, 'layer': 'CDM-TOE'})
        msp.add_lwpolyline(tops, dxfattribs={'layer': 'CDM-TOP'})
        msp.add_lwpolyline(toes, dxfattribs={'layer': 'CDM-TOE'})
        return doc, {'point_count': len(points), 'vertical_scale': scale,
                     'note': 'Cao độ đầu/mũi cọc lấy từ số liệu; trắc dọc phóng đứng theo vertical_scale.'}
    raise ValueError('Chỉ hỗ trợ cdm_boundary, cdm_layout, cdm_section, cdm_profile.')


def render(plan: dict[str, Any], output: str) -> dict[str, Any]:
    path = Path(output).resolve()
    if path.suffix.lower() != '.dxf' or not path.parent.is_dir():
        raise ValueError('Chọn file DXF trong thư mục tồn tại.')
    doc, result = build(plan)
    # Exclusive create: never overwrite a drawing selected by mistake.
    with path.open('x', encoding=doc.output_encoding, errors='dxfreplace') as stream:
        doc.write(stream)
    return {'ok': True, 'path': str(path), **result}


def main() -> None:
    try:
        raw = sys.stdin.buffer.read(262145)
        if len(raw) > 262144:
            raise ValueError('Yêu cầu vượt 256 KiB.')
        request = json.loads(raw)
        if set(request) != {'plan', 'output'}:
            raise ValueError('Sai cấu trúc yêu cầu.')
        result = render(request['plan'], request['output'])
    except Exception as error:
        result = {'ok': False, 'error': str(error)[:1000]}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode('utf-8'))


if __name__ == '__main__':
    main()

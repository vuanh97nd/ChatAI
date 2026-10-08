"""Add CDM circles inside an explicitly selected DXF boundary, on a new layer."""
import math
from pathlib import Path

MM_PER_UNIT={'mm':1,'cm':10,'m':1000,'inch':25.4}
MAX_PILES=10000
MAX_CANDIDATES=100000


def _points(entity):
    if entity.dxftype()!='LWPOLYLINE' or not entity.closed:
        raise ValueError('Chọn LWPOLYLINE khép kín trong Model.')
    if any(p[4] for p in entity.get_points()):
        raise ValueError('Vùng có cung tròn (bulge); cần polyline cạnh thẳng để bảo đảm khoảng cách mép.')
    if abs(entity.dxf.elevation)>1e-8 or tuple(entity.dxf.extrusion)!=(0,0,1):
        raise ValueError('Chỉ hỗ trợ vùng 2D phẳng XY ở cao độ 0.')
    pts=[tuple(map(float,p)) for p in entity.get_points('xy')]
    if pts and pts[-1]==pts[0]:pts.pop()
    if len(pts)<3 or len(pts)>1000 or any(not all(math.isfinite(v) for v in p) for p in pts):
        raise ValueError('Biên vùng không hợp lệ hoặc vượt 1000 đỉnh.')
    # Work near the origin: civil drawings often use very large coordinates.
    x0,y0=pts[0]
    local=[(x-x0,y-y0) for x,y in pts]
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def intersects(a,b,c,d):
        def side(v):return (v>1e-9)-(v< -1e-9)
        if side(cross(a,b,c))*side(cross(a,b,d))<0 and side(cross(c,d,a))*side(cross(c,d,b))<0:return True
        def on(p,a,b):return abs(cross(a,b,p))<=1e-9 and min(a[0],b[0])-1e-9<=p[0]<=max(a[0],b[0])+1e-9 and min(a[1],b[1])-1e-9<=p[1]<=max(a[1],b[1])+1e-9
        return any((on(c,a,b),on(d,a,b),on(a,c,d),on(b,c,d)))
    n=len(local)
    for i in range(n):
        a,b=local[i],local[(i+1)%n]
        if math.dist(a,b)<1e-9:raise ValueError('Polyline có cạnh dài 0.')
        for j in range(i+1,n):
            if j==i+1 or (i==0 and j==n-1):continue
            if intersects(a,b,local[j],local[(j+1)%n]):raise ValueError('Polyline tự giao; cần sửa biên vùng trước.')
    area=abs(sum(local[i][0]*local[(i+1)%n][1]-local[(i+1)%n][0]*local[i][1] for i in range(n)))/2
    if area<=1e-9:raise ValueError('Vùng có diện tích bằng 0.')
    return pts,area


def list_regions(doc, start=0, limit=40):
    rows=[]
    for entity in doc.modelspace().query('LWPOLYLINE'):
        if not entity.closed:continue
        row={'handle':entity.dxf.handle,'layer':entity.dxf.layer}
        try:
            pts,area=_points(entity)
            row.update(area_drawing_units_squared=area,bounds=[min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)],supported=True)
        except ValueError as error:row.update(supported=False,reason=str(error))
        rows.append(row)
    return {'regions':rows[start:start+limit],'total':len(rows),'next_start':start+limit if start+limit<len(rows) else None,
            'units_header':doc.units,'note':'Chọn handle theo vùng người dùng chỉ định; không tự chọn polyline lớn nhất hoặc khung Defpoints. Xác nhận đơn vị hình học, header DXF có thể sai.'}


def layout_in_boundary(doc, handle, diameter_m, spacing_x_m, spacing_y_m, drawing_units, edge_clearance_m=0, angle_deg=0):
    if drawing_units not in MM_PER_UNIT:raise ValueError('Xác nhận drawing_units: mm/cm/m/inch; không suy đoán từ header.')
    for name,v in [('D',diameter_m),('sx',spacing_x_m),('sy',spacing_y_m),('mép',edge_clearance_m),('góc',angle_deg)]:
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or (name not in ('mép','góc') and v<=0) or (name=='mép' and v<0):raise ValueError('Thông số cọc không hợp lệ: '+name)
    if diameter_m>min(spacing_x_m,spacing_y_m):raise ValueError('Công cụ bố trí này không hỗ trợ cọc chồng lấn.')
    entity=doc.entitydb.get(str(handle).upper())
    if entity is None or entity not in doc.modelspace():raise ValueError('Không tìm thấy polyline handle trong Model.')
    pts,area=_points(entity)
    factor=1000/MM_PER_UNIT[drawing_units]
    radius=diameter_m*factor/2;sx=spacing_x_m*factor;sy=spacing_y_m*factor;clearance=radius+edge_clearance_m*factor
    origin=pts[0];ang=math.radians(angle_deg);c,s=math.cos(ang),math.sin(ang)
    def local(p):
        x,y=p[0]-origin[0],p[1]-origin[1]
        return (c*x+s*y,-s*x+c*y)
    polygon=[local(p) for p in pts];edges=list(zip(polygon,polygon[1:]+polygon[:1]))
    minx=min(p[0] for p in polygon);maxx=max(p[0] for p in polygon);miny=min(p[1] for p in polygon);maxy=max(p[1] for p in polygon)
    nx=max(0,math.floor((maxx-minx-2*clearance)/sx+1e-9)+1);ny=max(0,math.floor((maxy-miny-2*clearance)/sy+1e-9)+1)
    if nx*ny>MAX_CANDIDATES or nx*ny*len(edges)>5_000_000:raise ValueError('Lưới vượt 100000 vị trí thử; kiểm tra đơn vị hoặc chia vùng.')
    # Center the grid in the bounding box; spacing and phase stay deterministic.
    x0=(minx+maxx-(nx-1)*sx)/2;y0=(miny+maxy-(ny-1)*sy)/2
    def inside(x,y):
        hit=False
        for (ax,ay),(bx,by) in edges:
            if (ay>y)!=(by>y) and x<(bx-ax)*(y-ay)/(by-ay)+ax:hit=not hit
        return hit
    def distance(x,y,a,b):
        dx,dy=b[0]-a[0],b[1]-a[1]
        t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
        return math.hypot(x-a[0]-t*dx,y-a[1]-t*dy)
    centers=[]
    for i in range(nx):
        for j in range(ny):
            x,y=x0+i*sx,y0+j*sy
            if inside(x,y) and min(distance(x,y,a,b) for a,b in edges)>=clearance-1e-8:
                centers.append((origin[0]+c*x-s*y,origin[1]+s*x+c*y))
                if len(centers)>MAX_PILES:raise ValueError('Vùng vượt 10000 cọc; chia vùng trước.')
    if not centers:raise ValueError('Không có cọc nằm trọn trong vùng với thông số đã chọn.')
    return {'centers':centers,'radius':radius,'boundary_area':area,'boundary_handle':entity.dxf.handle,'drawing_units':drawing_units}


def add_piles(doc, layout):
    name='CDM-BO-TRI';suffix=1
    while name in doc.layers:
        suffix+=1;name='CDM-BO-TRI-'+str(suffix)
    doc.layers.new(name,dxfattribs={'color':4,'lineweight':25})
    for center in layout['centers']:
        doc.modelspace().add_circle(center,layout['radius'],dxfattribs={'layer':name})
    return name

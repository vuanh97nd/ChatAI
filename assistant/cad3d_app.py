"""Closed 3D meshes in DXF; no arbitrary CAD scripts or native solid claims."""
import json
import math
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from .cad_app import UNITS
from .windows_apps import fingerprint


def shape_from_json(raw):
    if not isinstance(raw,str) or len(raw)>10000:raise ValueError('shape phải là chuỗi JSON tối đa 10000 ký tự.')
    row=json.loads(raw)
    if not isinstance(row,dict):raise ValueError('shape phải là đối tượng.')
    kind=row.get('type')
    keys={'box':{'type','origin','width','depth','height'},'cylinder':{'type','origin','radius','height'},
          'flange':{'type','origin','outer_radius','inner_radius','height','hole_radius','hole_count','bolt_radius'}}.get(kind)
    if keys is None or set(row)!=keys:raise ValueError('Chỉ hỗ trợ box/cylinder/flange với đúng tham số; chưa hỗ trợ bo cạnh.')
    def scalar(value,positive=False):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or abs(value)>1e6:
            raise ValueError('Tọa độ/kích thước phải hữu hạn và không vượt 1e6.')
        if positive and value<1e-6:raise ValueError('Kích thước phải dương, tối thiểu 1e-6.')
        return float(value)
    origin=row['origin']
    if not isinstance(origin,list) or len(origin)!=3:raise ValueError('origin phải là [x,y,z].')
    result={'type':kind,'origin':[scalar(v) for v in origin]}
    for key in keys-{'type','origin','hole_count'}:result[key]=scalar(row[key],key not in {'inner_radius'})
    if kind=='flange':
        count=row['hole_count']
        if type(count) is not int or not 1<=count<=32:raise ValueError('Số lỗ bu-lông phải từ 1 đến 32.')
        result['hole_count']=count
        outer,inner,hole,bolt=(result[k] for k in ('outer_radius','inner_radius','hole_radius','bolt_radius'))
        if inner<0 or inner>=outer or bolt-hole<=inner or bolt+hole>=outer:
            raise ValueError('Lỗ phải nằm hoàn toàn trong mặt bích, không chạm lỗ tâm hoặc biên ngoài.')
        if count>1 and 2*bolt*math.sin(math.pi/count)<=2*hole:
            raise ValueError('Các lỗ bu-lông chạm hoặc chồng lên nhau.')
    return result


def build_mesh(shape):
    def circle(radius,cx=0,cy=0,clockwise=False,segments=64):
        sign=-1 if clockwise else 1
        return [(cx+radius*math.cos(sign*2*math.pi*i/segments),cy+radius*math.sin(sign*2*math.pi*i/segments)) for i in range(segments)]
    if shape['type']=='box':
        w,d=shape['width'],shape['depth'];rings=[[(0,0),(w,0),(w,d),(0,d)]]
    elif shape['type']=='cylinder':rings=[circle(shape['radius'])]
    else:
        rings=[circle(shape['outer_radius'])]
        if shape['inner_radius']>0:rings.append(circle(shape['inner_radius'],clockwise=True))
        for i in range(shape['hole_count']):
            angle=2*math.pi*i/shape['hole_count'];r=shape['bolt_radius']
            rings.append(circle(shape['hole_radius'],r*math.cos(angle),r*math.sin(angle),True))
    import numpy as np
    import mapbox_earcut
    points=[point for ring in rings for point in ring]
    ends=[];total=0
    for ring in rings:total+=len(ring);ends.append(total)
    indices=mapbox_earcut.triangulate_float64(np.array(points,dtype=np.float64),np.array(ends,dtype=np.uint32))
    ox,oy,oz=shape['origin'];h=shape['height'];n=len(points)
    vertices=[(ox+x,oy+y,oz+z) for z in (0,h) for x,y in points]
    faces=[]
    for start in range(0,len(indices),3):
        a,b,c=(int(v) for v in indices[start:start+3])
        x,y=points[a];bx,by=points[b];cx,cy=points[c]
        if (bx-x)*(cy-y)-(by-y)*(cx-x)<0:b,c=c,b
        faces.extend([(c,b,a),(a+n,b+n,c+n)])
    start=0
    for end in ends:
        for a in range(start,end):
            b=start if a==end-1 else a+1;faces.append((a,b,b+n,a+n))
        start=end
    # Check closed manifold before writing: each edge appears twice, in opposite directions.
    edges={}
    for face in faces:
        for a,b in zip(face,face[1:]+face[:1]):
            key=tuple(sorted((a,b)));count,orientation=edges.get(key,(0,0))
            edges[key]=(count+1,orientation+(1 if a<b else -1))
    if any(value!=(2,0) for value in edges.values()):raise ValueError('Không tạo được lưới 3D kín hợp lệ.')
    return vertices,faces


class Cad3DApp:
    def __init__(self,windows,files,audit):self.windows,self.files,self.audit=windows,files,audit

    def prepare(self,name,args):
        self.windows.check();app=self.windows.allowed_path(args['app'])
        if app.name.lower()!='acad.exe':raise ValueError('Chọn acad.exe; công cụ 3D chưa hỗ trợ AutoCAD LT.')
        if args['units'] not in UNITS:raise ValueError('Đơn vị phải là mm/cm/m/inch.')
        shape=shape_from_json(args['shape'])
        if not self.files.roots:raise PermissionError('Thêm thư mục lưu được phép.')
        path=self.files.path(str(self.files.roots[0]/('ChatAI-3D-'+uuid.uuid4().hex+'.dxf')),exists=False)
        return {'action':'cad3d_create_open','app':str(app),'sha256':fingerprint(app),'path':str(path),'units':args['units'],'shape':shape}

    def commit(self,plan):
        self.windows.check();app=self.windows.allowed_path(plan['app'])
        if fingerprint(app)!=plan['sha256']:raise PermissionError('EXE AutoCAD đã thay đổi.')
        shape=shape_from_json(json.dumps(plan['shape']));vertices,faces=build_mesh(shape)
        import ezdxf
        doc=ezdxf.new('R2010');doc.units=UNITS[plan['units']]
        mesh=doc.modelspace().add_mesh()
        with mesh.edit_data() as data:data.vertices=vertices;data.faces=faces
        low=[min(v[i] for v in vertices) for i in range(3)];high=[max(v[i] for v in vertices) for i in range(3)]
        view=doc.viewports.get_config('*Active')[0]
        view.dxf.direction=(1,-1,1);view.dxf.target=tuple((a+b)/2 for a,b in zip(low,high))
        view.dxf.height=max(b-a for a,b in zip(low,high))*2;view.dxf.center=(0,0)
        path=self.files.path(plan['path'],exists=False)
        if path.exists():raise FileExistsError('Không ghi đè tệp đã có.')
        with tempfile.TemporaryDirectory(prefix='.cad3d-',dir=path.parent) as folder:
            temporary=Path(folder)/'model.dxf';doc.saveas(temporary)
            self.windows.check();self.files.path(str(path),exists=False)
            with path.open('xb') as out,temporary.open('rb') as src:shutil.copyfileobj(src,out)
        self.audit('cad3d_created',{'path':str(path),'vertices':len(vertices),'faces':len(faces),'units':plan['units']})
        self.windows.check();app=self.windows.allowed_path(plan['app'])
        if fingerprint(app)!=plan['sha256']:raise PermissionError('Đã tạo DXF nhưng EXE đã đổi; chưa mở.')
        subprocess.Popen([str(app),str(path)],shell=False)
        return {'ok':True,'path':str(path),'document_created':True,'cad_launch_requested':True,'representation':'closed_mesh',
                'vertices':len(vertices),'faces':len(faces),'units':plan['units'],'bounds':[low,high],
                'note':'Mô hình 3D là lưới kín, đường tròn xấp xỉ bằng 64 cạnh; không phải khối ACIS solid, chưa bo cạnh. Đã gửi lệnh mở, chưa xác minh cửa sổ AutoCAD.'}

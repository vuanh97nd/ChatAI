"""Create a fresh, validated DXF and open the authorized CAD executable."""
import json
import math
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from .windows_apps import fingerprint

UNITS={'mm':4,'cm':5,'m':6,'inch':1}


def entities_from_json(raw):
    if not isinstance(raw,str) or len(raw)>100000:raise ValueError('entities phải là chuỗi JSON tối đa 100000 ký tự.')
    rows=json.loads(raw)
    if not isinstance(rows,list) or not 1<=len(rows)<=200:raise ValueError('Cần 1–200 hình.')
    def number(value):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or abs(value)>1e9:
            raise ValueError('Tọa độ/kích thước phải là số hữu hạn, tối đa 1e9.')
        return float(value)
    def point(value):
        if not isinstance(value,list) or len(value)!=2:raise ValueError('Điểm phải là [x,y].')
        return [number(v) for v in value]
    result=[]
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Hình phải là đối tượng JSON.')
        kind=row.get('type')
        keys={'circle':{'type','center','radius'},'line':{'type','start','end'},'rectangle':{'type','origin','width','height'}}.get(kind)
        if keys is None or set(row)!=keys:raise ValueError('Chỉ hỗ trợ circle, line, rectangle với đúng tham số.')
        if kind=='circle':
            shape={'type':kind,'center':point(row['center']),'radius':number(row['radius'])}
            if shape['radius']<=0:raise ValueError('Bán kính phải dương.')
        elif kind=='line':
            shape={'type':kind,'start':point(row['start']),'end':point(row['end'])}
            if shape['start']==shape['end']:raise ValueError('Hai đầu đoạn thẳng phải khác nhau.')
        else:
            shape={'type':kind,'origin':point(row['origin']),'width':number(row['width']),'height':number(row['height'])}
            if shape['width']<=0 or shape['height']<=0:raise ValueError('Chiều rộng/cao phải dương.')
        result.append(shape)
    return result


class CadApp:
    def __init__(self,windows,files,audit):self.windows,self.files,self.audit=windows,files,audit

    def prepare(self,name,args):
        self.windows.check()
        app=self.windows.allowed_path(args['app'])
        if app.name.lower() not in {'acad.exe','acadlt.exe'}:raise ValueError('Chọn acad.exe hoặc acadlt.exe đã được phép.')
        units=args['units']
        if units not in UNITS:raise ValueError('Đơn vị phải là mm, cm, m hoặc inch.')
        shapes=entities_from_json(args['entities'])
        if not self.files.roots:raise PermissionError('Thêm thư mục lưu bản vẽ được phép trong Cài đặt.')
        path=self.files.path(str(self.files.roots[0]/('ChatAI-'+uuid.uuid4().hex+'.dxf')),exists=False)
        return {'action':'cad_create_open','app':str(app),'sha256':fingerprint(app),'path':str(path),'units':units,'entities':shapes}

    def commit(self,plan):
        self.windows.check()
        app=self.windows.allowed_path(plan['app'])
        if fingerprint(app)!=plan['sha256']:raise PermissionError('EXE AutoCAD đã thay đổi.')
        shapes=entities_from_json(json.dumps(plan['entities']))
        import ezdxf
        doc=ezdxf.new('R2010');doc.units=UNITS[plan['units']]
        model=doc.modelspace()
        for row in shapes:
            if row['type']=='circle':model.add_circle(row['center'],row['radius'])
            elif row['type']=='line':model.add_line(row['start'],row['end'])
            else:
                x,y=row['origin'];w,h=row['width'],row['height']
                model.add_lwpolyline([(x,y),(x+w,y),(x+w,y+h),(x,y+h)],close=True)
        path=self.files.path(plan['path'],exists=False)
        if path.exists():raise FileExistsError('Không ghi đè bản vẽ đã có.')
        with tempfile.TemporaryDirectory(prefix='.cad-',dir=path.parent) as folder:
            temporary=Path(folder)/'drawing.dxf';doc.saveas(temporary)
            self.windows.check();self.files.path(str(path),exists=False)
            with path.open('xb') as out,temporary.open('rb') as source:shutil.copyfileobj(source,out)
        self.audit('cad_document_created',{'path':str(path),'units':plan['units'],'entities':len(shapes)})
        self.windows.check();app=self.windows.allowed_path(plan['app'])
        if fingerprint(app)!=plan['sha256']:raise PermissionError('Đã tạo DXF nhưng EXE AutoCAD đã thay đổi; chưa mở.')
        subprocess.Popen([str(app),str(path)],shell=False)
        return {'ok':True,'path':str(path),'units':plan['units'],'entities':len(shapes),'document_created':True,'cad_launch_requested':True,
                'note':'Đã tạo DXF mới và gửi lệnh mở AutoCAD; chưa xác minh cửa sổ. Không sửa bản vẽ đang mở, không tạo DWG.'}

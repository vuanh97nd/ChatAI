"""Fail-closed staging changes for explicitly bounded rectangular excavation regions.
Curved tunnels need a geometry-specific verifier; a bounding box is not that proof.
"""
import json
import math
import re

COLLECTIONS={'soil':'Soils','displacement':'LineDisplacements','plate':'Plates',
             'line_load':'LineLoads','point_load':'PointLoads','point_displacement':'PointDisplacements',
             'anchor':'NodeToNodeAnchors','interface':'Interfaces','embedded_beam':'EmbeddedBeams'}

class StageGuardError(RuntimeError):
    pass


def value(obj):
    try:return obj.value
    except AttributeError:return obj


def name(obj):
    result=value(obj.Name)
    if not isinstance(result,str) or not result:
        raise StageGuardError('Không đọc được tên đối tượng/phase.')
    return result


def active(obj,phase,g=None):
    try:result=value(obj.Active[phase])
    except Exception:result=None
    attempts=1
    if result is None:
        # A second read is safe; a missing/inherited value is never activation=false.
        from .windows_apps import wait_automation,_STOP
        wait_automation()
        if _STOP.is_set():raise StageGuardError('Đã dừng đọc Active.')
        try:result=value(obj.Active[phase])
        except Exception:result=None
        attempts=2
    diagnostic=''
    if result is None and g is not None:
        from .plaxis_active import tabulated_active
        try:return tabulated_active(g,obj,phase,name(obj),name(phase))
        except ValueError as error:diagnostic=' '+str(error)
    if type(result) is not bool:
        raw=repr(result)[:100] if type(result) in (str,int,float,type(None)) else '<proxy>'
        raise StageGuardError(f'Active của {name(obj)} tại {name(phase)} chưa là boolean: '
                              f'kiểu={type(result).__name__}, giá trị={raw}, đã đọc {attempts} lần. Không ép chuỗi/số; '
                              +diagnostic+' Đọc lại g.Soils/g.Phases; không tạo lại/xóa hoặc đổi Active khi chưa đọc chắc chắn.')
    return result


def textual_bounds(box):
    """Decode the native CutObject min/max string without guessing tuple order."""
    match=re.fullmatch(r'\s*min:\s*\(([^()]*)\)\s*max:\s*\(([^()]*)\)\s*',box)
    if not match:raise StageGuardError('BoundingBox văn bản không đúng dạng min: (...) max: (...).')
    groups=[part.split(';') for part in match.groups()]
    if len(groups[0]) not in (2,3) or len(groups[0])!=len(groups[1]):
        raise StageGuardError('BoundingBox phải có cùng 2 hoặc 3 tọa độ min/max.')
    numeric=r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
    if any(not re.fullmatch(numeric,token.strip()) for group in groups for token in group):
        raise StageGuardError('BoundingBox chứa tọa độ không hợp lệ.')
    lows,highs=[[float(token.strip()) for token in group] for group in groups]
    if any(not math.isfinite(n) for n in lows+highs) or any(lo>hi for lo,hi in zip(lows,highs)):
        raise StageGuardError('BoundingBox không hữu hạn hoặc min > max; không xác minh vùng.')
    return {axis:[lo,hi] for axis,lo,hi in zip(('x','y','z'),lows,highs)}


def bounds(obj,g=None):
    def read(target,attribute):
        try:return value(getattr(target,attribute))
        except Exception:return None
    def number(n):return type(n) in (int,float) and math.isfinite(n)
    def coordinate(point,axis):
        for key in (axis,axis.upper()):
            n=read(point,key)
            if number(n):return n
        return None
    geometry=read(obj,'Parent')
    original_geometry=geometry
    seen=set();diagnostics=[]
    for _ in range(4):
        if geometry is None or str(geometry) in seen:break
        seen.add(str(geometry))
        box=read(geometry,'BoundingBox');result={}
        if isinstance(box,str):return textual_bounds(box)
        for axis in ('x','y','z'):
            interval=None
            for prefix in (axis,axis.upper()):
                low,high=read(box,prefix+'Min'),read(box,prefix+'Max')
                if number(low) and number(high) and low<=high:
                    interval=[low,high];break
            if interval is not None:result[axis]=interval
        if 'x' in result and 'y' in result:return result
        # Only linked vertices/endpoints, never the project's global Points.
        points=read(geometry,'Points')
        if points is not None:
            try:points=list(points)
            except Exception:points=None
        if points is None:
            endpoints=[read(geometry,'First'),read(geometry,'Second')]
            points=endpoints if all(p is not None for p in endpoints) else []
        if points and len(points)<=10000:
            coordinates={axis:[coordinate(point,axis) for point in points] for axis in ('x','y','z')}
            if all(all(number(n) for n in coordinates[axis]) for axis in ('x','y')):
                if any(n is not None for n in coordinates['z']) and not all(number(n) for n in coordinates['z']):
                    raise StageGuardError('Tọa độ z của hình học chưa đọc đủ; không xác minh vùng 3D bằng vùng 2D.')
                return {axis:[min(ns),max(ns)] for axis,ns in coordinates.items() if all(number(n) for n in ns)}
        diagnostics.append(str(geometry)[:80])
        geometry=read(geometry,'Parent')
    evidence={}
    if g is not None and original_geometry is not None:
        # Read the actual linked CutObject's schema; never infer endpoints from
        # point order or use a project's overall bounds for one excavation cell.
        for command in ('info','commands'):
            try:evidence[command]=str(getattr(g,command)(original_geometry))[:1800]
            except Exception as error:evidence[command]='Không đọc được: '+str(error)[:180]
    raise StageGuardError('Chưa đọc được vùng hình học gốc: '+', '.join(diagnostics)+
                          '. Cần info/commands của Parent, BoundingBox và các điểm liên kết; không đoán thứ tự tọa độ hoặc bỏ verify_stage. '
                          +'Dữ liệu Parent (có thể bị cắt): '+json.dumps(evidence,ensure_ascii=False))


def check_spec(raw):
    try:spec=json.loads(raw)
    except (ValueError,TypeError):raise StageGuardError('verify_stage cần một chuỗi JSON.') from None
    required={'target','phase','parent_phase','before','parent_active','after','region','shape','source'}
    if not isinstance(spec,dict) or set(spec) not in (required,required|{'kind'}):
        raise StageGuardError('verify_stage cần target, phase, parent_phase, before, parent_active, after, region, shape, source.')
    if spec.get('kind','soil') not in COLLECTIONS:
        raise StageGuardError('kind phải là '+', '.join(COLLECTIONS)+'.')
    for key in ('target','phase','parent_phase'):
        if key=='parent_phase' and spec[key] is None:continue
        if not isinstance(spec[key],str) or not re.fullmatch(r'(?:g\.)?[A-Za-z][A-Za-z0-9_]*',spec[key]):
            raise StageGuardError('Dùng tên đối tượng và phase tường minh; không dùng chỉ số collection.')
    if any(type(spec[key]) is not bool for key in ('before','after')) or (
            spec['parent_active'] is not None and type(spec['parent_active']) is not bool):
        raise StageGuardError('before, parent_active và after phải là boolean.')
    if (spec['parent_phase'] is None)!=(spec['parent_active'] is None):
        raise StageGuardError('Phase gốc dùng parent_phase=null và parent_active=null cùng nhau.')
    if spec['shape']!='box':
        raise StageGuardError('Chưa có bộ xác minh biên cong/tunnel; bounding box không chứng minh vùng nằm trong hầm. Chỉ đọc/highlight, không đổi Active.')
    if not isinstance(spec['source'],str) or not spec['source'].strip() or len(spec['source'])>1000:
        raise StageGuardError('Ghi nguồn manual/mục/trang của phạm vi và trình tự phase, không tự đặt số liệu.')
    region=spec['region']
    if not isinstance(region,dict) or set(region) not in ({'x','y'},{'x','y','z'}):
        raise StageGuardError('region cần x/y cho 2D, x/y/z cho 3D; mỗi trục là [min,max].')
    for interval in region.values():
        if not isinstance(interval,list) or len(interval)!=2 or any(type(n) not in (int,float) or not math.isfinite(n) for n in interval) or interval[0]>interval[1] or (spec.get('kind','soil')=='soil' and interval[0]==interval[1]):
            raise StageGuardError('Phạm vi đào phải có giới hạn hữu hạn, min < max.')
    return spec


def snapshot(g,obj,phase,include_soils=True,kind='soil'):
    from .windows_apps import _STOP,wait_automation
    wait_automation()
    if _STOP.is_set():raise StageGuardError('Đã dừng xác minh vùng đào.')
    initial=name(phase)==name(g.InitialPhase) and str(phase)==str(g.InitialPhase)
    parent=None if initial else value(phase.PreviousPhase)
    if not initial and parent is None:
        raise StageGuardError('Phase thi công chưa có phase cha; kiểm tra PreviousPhase trước khi đổi Active.')
    soil_states={}
    for soil in (g.Soils if include_soils else []):
        wait_automation()
        if _STOP.is_set():raise StageGuardError('Đã dừng xác minh vùng đào.')
        soil_states[name(soil)]=active(soil,phase,g)
    if include_soils and kind=='soil' and name(obj) not in soil_states:
        raise StageGuardError('Đối tượng không thuộc g.Soils; khai đúng kind cho tải/kết cấu/chuyển vị.')
    other_states={}
    if kind!='soil':
        members=list(getattr(g,COLLECTIONS[kind]))
        if not any(str(member)==str(obj) and name(member)==name(obj) for member in members):
            raise StageGuardError('Đối tượng không thuộc collection '+COLLECTIONS[kind]+'. Không dùng quy trình đất đào để bật tải/chuyển vị.')
        other_states={name(member):active(member,phase,g) for member in members}
    return {'kind':kind,'other_states':other_states,'target':name(obj),'identity':str(obj),'geometry_identity':str(obj.Parent),
            'phase':name(phase),'phase_identity':str(phase),'parent_phase':name(parent) if parent is not None else None,
            'parent_identity':str(parent) if parent is not None else None,'before':active(obj,phase,g),
            'parent_active':active(obj,parent,g) if parent is not None else None,
            'bounds':bounds(obj,g),'soil_states':soil_states}


def verify(g,resolve,spec,session):
    session.pop('stage_permit',None)
    obj=resolve({'ref':spec['target']});phase=resolve({'ref':spec['phase']})
    parent=resolve({'ref':spec['parent_phase']}) if spec['parent_phase'] is not None else None
    observed=snapshot(g,obj,phase,kind=spec.get('kind','soil'))
    if name(phase)==name(g.InitialPhase):
        if (str(phase)!=str(g.InitialPhase) or spec.get('kind','soil')!='soil' or spec['after'] is not True
                or parent is not None or spec['parent_active'] is not None):
            raise StageGuardError('InitialPhase chỉ cho phép bật đất đã xác minh: kind=soil, after=true, parent_phase=null, parent_active=null. Không đào hoặc bật kết cấu/tải bằng nhánh này.')
    elif parent is None:
        raise StageGuardError('Phase thi công phải có parent_phase và parent_active boolean; không dùng quy trình phase gốc.')
    if observed['parent_phase']!=(name(parent) if parent is not None else None) or observed['parent_identity']!=(str(parent) if parent is not None else None):
        raise StageGuardError('Phase cha không khớp manual; chưa đổi Active.')
    if observed['before']!=spec['before'] or observed['parent_active']!=spec['parent_active']:
        raise StageGuardError('Active hiện tại/phase cha khác dự kiến. Đọc lại trước khi sửa, không bật/tắt hàng loạt.')
    actual=observed['bounds'];region=spec['region']
    if set(region)-set(actual) or ('z' in actual and actual['z'][0]!=actual['z'][1] and 'z' not in region):
        raise StageGuardError('Thiếu trục không gian; không dùng vùng 2D để xác nhận một khối 3D.')
    for axis,(lo,hi) in region.items():
        if actual[axis][0]<lo or actual[axis][1]>hi:
            raise StageGuardError('Đối tượng nằm ngoài hoặc cắt qua ranh giới vùng đào ở trục '+axis+'. Chưa đổi Active; kiểm tra chia vùng hình học.')
    session['stage_permit']={'spec':spec,'snapshot':observed}
    return {'verified':True,'target':observed['target'],'phase':observed['phase'],
            'parent_phase':observed['parent_phase'],'bounds':actual,'before':observed['before'],
            'parent_active':observed['parent_active'],'after':spec['after'],'source':spec['source'],
            'scope':'Chỉ chứng minh đối tượng nằm trọn trong vùng hộp được cung cấp và trạng thái phase khớp. Chưa xác thực nguồn manual hoặc chọn đủ mọi khối đào. Giấy phép chỉ dùng một lần cho đúng đối tượng/phase/trạng thái.'}


def initial_soil_spec(raw):
    try:spec=json.loads(raw)
    except (ValueError,TypeError):raise StageGuardError('initialize_soils cần JSON source, region, objects.') from None
    if not isinstance(spec,dict) or set(spec)!={'source','region','objects'}:
        raise StageGuardError('initialize_soils chỉ nhận source, region, objects (tên đất → Active đã đọc).')
    objects=spec['objects']
    if not isinstance(objects,dict) or not 1<=len(objects)<=10000 or any(
            not isinstance(k,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',k) or type(v) is not bool
            for k,v in objects.items()):
        raise StageGuardError('objects phải liệt kê đúng tên đất và Active boolean; không đoán False/ép None.')
    check_spec(json.dumps({'target':next(iter(objects)),'phase':'InitialPhase','parent_phase':None,
        'before':True,'parent_active':None,'after':True,'kind':'soil','shape':'box',
        'region':spec['region'],'source':spec['source']}))
    return spec


def initialize_soils(g,spec):
    """Verified initial-soil activation: two complete reads, no nested group scans."""
    from .windows_apps import _STOP,wait_automation
    phase=g.InitialPhase
    soils=list(g.Soils)
    identities={name(obj):str(obj) for obj in soils}
    if len(identities)!=len(soils) or set(identities)!=set(spec['objects']):
        raise StageGuardError('Danh sách đất khác dữ liệu đã đọc; chưa bật đất. Đọc lại đúng g.Soils một lần.')
    before={}
    for obj in soils:
        wait_automation()
        if _STOP.is_set():raise StageGuardError('Đã dừng trước khi bật đất.')
        actual=bounds(obj,g)
        extra=set(actual)-set(spec['region'])
        if (set(spec['region'])-set(actual) or
                (extra and not (extra=={'z'} and actual['z'][0]==actual['z'][1])) or
                any(actual[k][0]<v[0] or actual[k][1]>v[1] for k,v in spec['region'].items() if k in actual)):
            raise StageGuardError('Đất nằm ngoài vùng khởi tạo đã xác minh; chưa bật: '+name(obj))
        before[name(obj)]=active(obj,phase,g)
    if before!=spec['objects']:
        raise StageGuardError('Active thực tế khác bảng đã đọc; chưa ghi. Không lặp lệnh dựa trên trạng thái cũ.')
    changed=[]
    for obj in soils:
        wait_automation()
        if _STOP.is_set():raise StageGuardError('Đã dừng; có thể đã bật một phần đất. Đọc lại, không phát lại cả nhóm.')
        if str(g.InitialPhase)!=str(phase):raise StageGuardError('Phiên/model đã đổi; dừng bật đất.')
        if not before[name(obj)]:
            response=g.set(obj.Active,phase,True)
            if isinstance(response,str) and response.startswith('Unsuccessful command'):
                raise StageGuardError(response+' Có thể đã bật một phần; không phát lại cả nhóm.')
            changed.append(name(obj))
    current=list(g.Soils)
    if {name(obj):str(obj) for obj in current}!=identities:
        raise StageGuardError('Danh sách/GUID đất đã đổi trong thao tác; cần kiểm tra, không chạy lại cả nhóm.')
    after={name(obj):active(obj,phase,g) for obj in current}
    if not all(after.values()):
        raise StageGuardError('Đã gửi lệnh nhưng có đất chưa Active=True; đọc đúng khối sai, không chạy lại cả nhóm.')
    return {'verified':True,'phase':name(phase),'activated':changed,
        'already_active':[k for k,v in before.items() if v],'before':before,'after':after,
        'source':spec['source'],'scope':'Chỉ bật đất trong InitialPhase, không ghi vào neo/tường/tải hoặc phase đào.'}


def request(row):
    cmd=row['command'].lower();args=row.get('args',[])
    def has_active(v):
        if isinstance(v,dict):return any(p.lower()=='active' for p in str(v.get('ref','')).split('.'))
        if isinstance(v,list):return any(has_active(x) for x in v)
        return isinstance(v,str) and v.lower().split('.')[-1]=='active'
    if cmd in {'activate','deactivate'} or (cmd=='setproperties' and has_active(args)):
        raise StageGuardError('Đổi Active phải xác minh bằng verify_stage rồi set một thuộc tính Tên.Active, một phase, một boolean; không dùng lệnh hàng loạt.')
    alias_set=(cmd=='set' and args and isinstance(args[0],dict) and 'ref' in args[0] and '.' not in args[0]['ref'])
    named_property=(args and isinstance(args[0],dict) and set(args[0])=={'ref'}
                    and '.' in args[0]['ref'])
    # A phase-dependent boolean is not necessarily Active (e.g. AdjustPrestress).
    # Keep alias/list protection but allow explicitly named non-Active properties.
    if cmd=='set' and (has_active(args) or alias_set or
                      (len(args)==3 and type(args[-1]) is bool and not named_property)):
        if len(args)!=3 or not isinstance(args[0],dict) or set(args[0])!={'ref'} or not args[0]['ref'].endswith('.Active') or not isinstance(args[1],dict) or set(args[1])!={'ref'} or type(args[2]) is not bool:
            raise StageGuardError('Active cần set [{"ref":"Tên.Active"},{"ref":"Phase_x"},true/false], không dùng alias thuộc tính hoặc danh sách.')
        return args[0]['ref'][:-7],args[1]['ref'],args[2]
    return None


def before_change(g,resolve,row,session):
    wanted=request(row)
    if wanted is None:return None
    permit=session.pop('stage_permit',None)
    if not permit:
        raise StageGuardError('Chưa xác minh vùng và phase: inspect_stage để đọc ứng viên, verify_stage đối chiếu manual, rồi mới set Active. Không dùng UI để vượt chốt kiểm tra.')
    target,phase_ref,after=wanted
    obj=resolve({'ref':target});phase=resolve({'ref':phase_ref})
    current=snapshot(g,obj,phase,kind=permit['spec'].get('kind','soil'))
    if current!=permit['snapshot'] or after!=permit['spec']['after']:
        raise StageGuardError('Đối tượng, hình học, phase hoặc Active đã khác lần xác minh. Chưa gửi lệnh; verify_stage lại.')
    return obj,phase,after,current


def after_change(g,checked):
    obj,phase,expected,before=checked
    after=snapshot(g,obj,phase,kind=before['kind'])
    if after['before']!=expected:
        raise StageGuardError('Lệnh đã gửi nhưng Active đọc lại không khớp. Dừng, không tự gửi lại hoặc hoàn tác hàng loạt.')
    expected_states=dict(before['soil_states'])
    if before['target'] in expected_states:expected_states[before['target']]=expected
    if after['soil_states']!=expected_states:
        raise StageGuardError('Lệnh đã gửi nhưng vùng đất khác cũng đổi Active. Dừng để kiểm tra, không tự hoàn tác.')
    expected_other=dict(before['other_states'])
    if before['target'] in expected_other:expected_other[before['target']]=expected
    if after['other_states']!=expected_other:
        raise StageGuardError('Đối tượng tải/kết cấu/chuyển vị khác cũng đổi Active; dừng xác minh.')
    for key in ('geometry_identity','bounds','phase_identity','parent_identity','parent_active'):
        if after[key]!=before[key]:raise StageGuardError('Trạng thái/hình học đổi trong khi thao tác; dừng xác minh.')
    return {'verified':True,'target':after['target'],'phase':after['phase'],'active':after['before'],
            'other_soils_unchanged':True,'other_objects_unchanged':True,'kind':before['kind']}


def inspect(g,phase,objects):
    from .windows_apps import _STOP,wait_automation
    rows=[]
    truncated=False
    for obj in objects:
        wait_automation()
        if _STOP.is_set():raise StageGuardError('Đã dừng đọc vùng đào.')
        if len(rows)>=100:
            truncated=True;break
        try:
            state=snapshot(g,obj,phase,include_soils=False)
            state.pop('soil_states',None)
            rows.append(state)
        except Exception as exc:
            rows.append({'target':str(obj)[:200],'error':str(exc)[:4500]})
    return {'phase':name(phase),'objects':rows,'truncated':truncated,'note':'Chỉ là ứng viên, chưa cho phép đổi Active. So sánh vùng manual và phase cha; tên/thứ tự/bounding box không chứng minh vùng thuộc hầm cong.'}


STAGE_INSTRUCTION = (
    '\nKhi đã được yêu cầu bật toàn bộ đất ban đầu, ưu tiên initialize_soils: args [JSON '
    '{source,region:{x:[min,max],y:[min,max]},objects:{Soil_1_1:false,...}}]. '
    'objects phải đúng toàn bộ g.Soils và trạng thái đã đọc, không tự đoán. Wrapper xác minh nhóm, '
    'chỉ bật khối False ở InitialPhase rồi đọc lại một lần; không inspect/tabulate lại cả nhóm từng khối. '
    '\nInitialPhase không có phase cha: inspect_stage vẫn đọc được. Để bật đất ở InitialPhase, '
    'verify_stage dùng kind=soil, after=true, parent_phase=null, parent_active=null; '
    'before là Active thật, region/source đúng vùng đã đọc. Chỉ set khối còn False rồi đọc lại; '
    'không dùng nhánh này để tắt đất hoặc bật neo/tường/tải. '
    '\nActive đọc trực tiếp=None: wrapper tự thử tabulate tối đa hai lần, chỉ chấp nhận bảng có đúng tên đối tượng và cột phase tường minh, không bỏ verify_stage. Interface tường: inspect_progress báo wall_interfaces theo Parent từng đoạn plate; đối chiếu manual để bổ sung positive/negative thiếu, giữ interface đã có. Dùng verify_stage kind=interface hoặc embedded_beam cho đúng collection. Vùng hộp của kết cấu đường cho phép một trục min=max; đất đào vẫn yêu cầu min<max. '
    '\nActive=None/null là chưa đọc được, không chứng minh phase trống hoặc chưa thiết lập staged construction. Nhật ký phiên không có lệnh cũng không chứng minh phase trống; có thể người dùng đã thiết lập trong UI hoặc phiên trước. Thiếu OCR mục staged construction: tự đọc lại đúng trang/ảnh còn thiếu hoặc nguồn chính thức trước khi hỏi người dùng số liệu, không đọc lại toàn bộ manual. '
    '\ninspect_stage, verify_stage, inspect_progress, plan_resume là wrapper của Chat AI trong plaxis_commands, không phải phương thức của g. Gọi bằng trường command; không dùng info/signature/read g.inspect_stage hay g.verify_stage để dò sự tồn tại. '
    '\nNếu tiếp tục bài đang dở: inspect_progress/plan_resume args [chuỗi JSON với source và checks (ref,expected,stage; thêm phase cho Active)] đọc trạng thái thật; expected lấy từ manual, không tự đặt. Với Active thêm phase và expected boolean. Giữ verified, sửa missing_or_wrong, chẩn đoán unreadable trước khi ghi; không dựng lại chỉ vì lỗi đọc. '
    'Schema inspect_progress/plan_resume: stage=project/soil/materials/geometry/mesh/phases/activation/calculate/output; kind chỉ value hoặc count (mặc định value). Không dùng kind=soil/plate/anchor của verify_stage ở đây; không đặt Phase_1 vào stage. Active dùng stage=activation, kind=value, phase=g.Phase_1; đếm g.Plates dùng stage=geometry, kind=count. '
    'phase cũng dùng đọc thuộc tính phụ thuộc phase như Material hoặc tải/chuyển vị: ref là thuộc tính, phase là chuỗi tên phase thực, expected là giá trị scalar đúng kiểu. Active luôn expected boolean JSON true/false; Material đối chiếu tên vật liệu đọc thật. Không thêm phase cho thuộc tính toàn dự án hoặc phép đếm collection. '
    'Trước khi đổi Active: inspect_stage args [ref phase, ref collection như g.Soils] đọc ứng viên; '
    'verify_stage args [chuỗi JSON với target, phase, parent_phase, before, parent_active, after, '
    'kind=soil/displacement/point_displacement/plate/line_load/point_load/anchor/interface/embedded_beam (mặc định soil), shape="box", region={"x":[min,max],"y":[min,max],"z":[min,max] cho 3D}, source="manual mục/trang"]. '
    'Tọa độ, chiều sâu đợt đào, phase cha và trạng thái dự kiến phải lấy từ manual, không sao chép số mô hình '
    'để hợp thức hóa lựa chọn. Box chỉ dùng phạm vi đào hình hộp/chữ nhật; không khai shape=box cho tunnel cong. '
    'Với móng cứng: xác minh đối tượng chuyển vị bằng kind=displacement hoặc point_displacement, không coi là đất đào. Vùng region lấy từ vị trí đối tượng trong manual; box kiểm tra vị trí, không chứng minh mô hình vật lý. verify_stage thành công mới set Tên.Active theo đúng phase và after. Tắt đất đào khác với bật kết cấu chống. '
    'Không tự đoán vùng, không dùng UI hoặc activate/deactivate hàng loạt để vượt kiểm tra. '
    'Sau thay đổi kiểm tra readback; sai thì dừng, không tự sửa hàng loạt. Nếu có nhiều khối trong vùng đào, '
    'đối chiếu đủ các khối theo manual; kiểm tra một khối không chứng minh toàn vùng đã đào.'
)

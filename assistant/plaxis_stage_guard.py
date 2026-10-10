"""Fail-closed staging changes for explicitly bounded rectangular excavation regions.
Curved tunnels need a geometry-specific verifier; a bounding box is not that proof.
"""
import json
import math
import re

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


def active(obj,phase):
    result=value(obj.Active[phase])
    if type(result) is not bool:
        raise StageGuardError('Active chưa được đọc chắc chắn; không ép chuỗi/số thành boolean.')
    return result


def bounds(obj):
    box=obj.Parent.BoundingBox
    result={}
    for axis in ('x','y','z'):
        try:low,high=value(getattr(box,axis+'Min')),value(getattr(box,axis+'Max'))
        except AttributeError:
            if axis=='z':continue
            raise
        if type(low) not in (int,float) or type(high) not in (int,float) or not all(math.isfinite(v) for v in (low,high)) or low>high:
            raise StageGuardError('Bounding box không hợp lệ; chưa xác định được vị trí.')
        result[axis]=[low,high]
    return result


def check_spec(raw):
    try:spec=json.loads(raw)
    except (ValueError,TypeError):raise StageGuardError('verify_stage cần một chuỗi JSON.') from None
    required={'target','phase','parent_phase','before','parent_active','after','region','shape','source'}
    if not isinstance(spec,dict) or set(spec)!=required:
        raise StageGuardError('verify_stage cần target, phase, parent_phase, before, parent_active, after, region, shape, source.')
    for key in ('target','phase','parent_phase'):
        if not isinstance(spec[key],str) or not re.fullmatch(r'(?:g\.)?[A-Za-z][A-Za-z0-9_]*',spec[key]):
            raise StageGuardError('Dùng tên đối tượng và phase tường minh; không dùng chỉ số collection.')
    if any(type(spec[key]) is not bool for key in ('before','parent_active','after')):
        raise StageGuardError('before, parent_active và after phải là boolean.')
    if spec['shape']!='box':
        raise StageGuardError('Chưa có bộ xác minh biên cong/tunnel; bounding box không chứng minh vùng nằm trong hầm. Chỉ đọc/highlight, không đổi Active.')
    if not isinstance(spec['source'],str) or not spec['source'].strip() or len(spec['source'])>1000:
        raise StageGuardError('Ghi nguồn manual/mục/trang của phạm vi và trình tự phase, không tự đặt số liệu.')
    region=spec['region']
    if not isinstance(region,dict) or set(region) not in ({'x','y'},{'x','y','z'}):
        raise StageGuardError('region cần x/y cho 2D, x/y/z cho 3D; mỗi trục là [min,max].')
    for interval in region.values():
        if not isinstance(interval,list) or len(interval)!=2 or any(type(n) not in (int,float) or not math.isfinite(n) for n in interval) or interval[0]>=interval[1]:
            raise StageGuardError('Phạm vi đào phải có giới hạn hữu hạn, min < max.')
    return spec


def snapshot(g,obj,phase,include_soils=True):
    from .windows_apps import _STOP,wait_automation
    wait_automation()
    if _STOP.is_set():raise StageGuardError('Đã dừng xác minh vùng đào.')
    parent=value(phase.PreviousPhase)
    soil_states={}
    for soil in (g.Soils if include_soils else []):
        wait_automation()
        if _STOP.is_set():raise StageGuardError('Đã dừng xác minh vùng đào.')
        soil_states[name(soil)]=active(soil,phase)
    return {'target':name(obj),'identity':str(obj),'geometry_identity':str(obj.Parent),
            'phase':name(phase),'phase_identity':str(phase),'parent_phase':name(parent),
            'parent_identity':str(parent),'before':active(obj,phase),'parent_active':active(obj,parent),
            'bounds':bounds(obj),'soil_states':soil_states}


def verify(g,resolve,spec,session):
    session.pop('stage_permit',None)
    obj=resolve({'ref':spec['target']});phase=resolve({'ref':spec['phase']})
    parent=resolve({'ref':spec['parent_phase']})
    observed=snapshot(g,obj,phase)
    if name(phase)==name(g.InitialPhase):
        raise StageGuardError('Không sửa InitialPhase qua quy trình đào; cần quy trình riêng cho trạng thái ban đầu.')
    if observed['parent_phase']!=name(parent) or observed['parent_identity']!=str(parent):
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


def request(row):
    cmd=row['command'].lower();args=row.get('args',[])
    def has_active(v):
        if isinstance(v,dict):return any(p.lower()=='active' for p in str(v.get('ref','')).split('.'))
        if isinstance(v,list):return any(has_active(x) for x in v)
        return isinstance(v,str) and v.lower().split('.')[-1]=='active'
    if cmd in {'activate','deactivate'} or (cmd=='setproperties' and has_active(args)):
        raise StageGuardError('Đổi Active phải xác minh bằng verify_stage rồi set một thuộc tính Tên.Active, một phase, một boolean; không dùng lệnh hàng loạt.')
    alias_set=(cmd=='set' and args and isinstance(args[0],dict) and 'ref' in args[0] and '.' not in args[0]['ref'])
    if cmd=='set' and (has_active(args) or alias_set or (len(args)==3 and type(args[-1]) is bool)):
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
    current=snapshot(g,obj,phase)
    if current!=permit['snapshot'] or after!=permit['spec']['after']:
        raise StageGuardError('Đối tượng, hình học, phase hoặc Active đã khác lần xác minh. Chưa gửi lệnh; verify_stage lại.')
    return obj,phase,after,current


def after_change(g,checked):
    obj,phase,expected,before=checked
    after=snapshot(g,obj,phase)
    if after['before']!=expected:
        raise StageGuardError('Lệnh đã gửi nhưng Active đọc lại không khớp. Dừng, không tự gửi lại hoặc hoàn tác hàng loạt.')
    expected_states=dict(before['soil_states'])
    if before['target'] in expected_states:expected_states[before['target']]=expected
    if after['soil_states']!=expected_states:
        raise StageGuardError('Lệnh đã gửi nhưng vùng đất khác cũng đổi Active. Dừng để kiểm tra, không tự hoàn tác.')
    for key in ('geometry_identity','bounds','phase_identity','parent_identity','parent_active'):
        if after[key]!=before[key]:raise StageGuardError('Trạng thái/hình học đổi trong khi thao tác; dừng xác minh.')
    return {'verified':True,'target':after['target'],'phase':after['phase'],'active':after['before'],
            'other_soils_unchanged':True}


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
            rows.append({'target':str(obj)[:200],'error':str(exc)[:300]})
    return {'phase':name(phase),'objects':rows,'truncated':truncated,'note':'Chỉ là ứng viên, chưa cho phép đổi Active. So sánh vùng manual và phase cha; tên/thứ tự/bounding box không chứng minh vùng thuộc hầm cong.'}


STAGE_INSTRUCTION = (
    '\nTrước khi đổi Active: inspect_stage args [ref phase, ref collection như g.Soils] đọc ứng viên; '
    'verify_stage args [chuỗi JSON với target, phase, parent_phase, before, parent_active, after, '
    'shape="box", region={"x":[min,max],"y":[min,max],"z":[min,max] cho 3D}, source="manual mục/trang"]. '
    'Tọa độ, chiều sâu đợt đào, phase cha và trạng thái dự kiến phải lấy từ manual, không sao chép số mô hình '
    'để hợp thức hóa lựa chọn. Box chỉ dùng phạm vi đào hình hộp/chữ nhật; không khai shape=box cho tunnel cong. '
    'verify_stage thành công mới set Tên.Active theo đúng phase và after. Tắt đất đào khác với bật kết cấu chống. '
    'Không tự đoán vùng, không dùng UI hoặc activate/deactivate hàng loạt để vượt kiểm tra. '
    'Sau thay đổi kiểm tra readback; sai thì dừng, không tự sửa hàng loạt. Nếu có nhiều khối trong vùng đào, '
    'đối chiếu đủ các khối theo manual; kiểm tra một khối không chứng minh toàn vùng đã đào.'
)

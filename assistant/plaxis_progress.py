"""Read-only progress and repair advice from live PLAXIS state, never cached aliases."""
import json
import math
import re
from .plaxis_stage_guard import active

COLLECTIONS=('Boreholes','Soillayers','Materials','Soils','Plates','Interfaces',
             'NodeToNodeAnchors','FixedEndAnchors','EmbeddedBeams','LineLoads','Phases')
STAGES=('project','soil','materials','geometry','mesh','phases','activation','calculate','output')
REF=re.compile(r'(?:g\.)?[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*\Z')

def specification(raw):
    spec=json.loads(raw)
    if not isinstance(spec,dict) or set(spec)-{'source','checks'}:raise ValueError('Tiến độ cần source và checks.')
    if not isinstance(spec.get('source',''),str) or len(spec.get('source',''))>1000:raise ValueError('source không hợp lệ.')
    checks=spec.get('checks',[])
    if not isinstance(checks,list) or len(checks)>200:raise ValueError('Tối đa 200 phép kiểm tra tiến độ.')
    stage_aliases={'material':'materials','phase':'phases','calculation':'calculate','results':'output',
                   'staged construction':'activation','staged_construction':'activation'}
    for index,check in enumerate(checks,1):
        if not isinstance(check,dict) or set(check)-{'ref','phase','expected','kind','tolerance','stage'}:raise ValueError('Phép kiểm tra tiến độ không hợp lệ.')
        if not isinstance(check.get('ref'),str) or not REF.fullmatch(check['ref']):raise ValueError('ref cần tên đối tượng/property thực tế.')
        stage=check.get('stage','project')
        kind=check.get('kind','value')
        if isinstance(stage,str):stage=stage.strip().casefold();stage=stage_aliases.get(stage,stage)
        if isinstance(kind,str):kind=kind.strip().casefold()
        if stage not in STAGES:
            raise ValueError(f'checks[{index}].stage={stage!r} không hợp lệ. stage chỉ nhận: '+', '.join(STAGES)+
                             '. Tên Phase_1 đặt trong phase, không đặt trong stage.')
        if kind not in ('value','count'):
            raise ValueError(f'checks[{index}].kind={kind!r} không hợp lệ. inspect_progress/plan_resume chỉ nhận kind=value (đọc thuộc tính) hoặc count (đếm collection). '
                             'kind=soil/plate/anchor chỉ dành cho verify_stage. Ví dụ kiểm tra Active: '
                             '{"ref":"g.Soil_1_1.Active","phase":"g.Phase_1","expected":false,"stage":"activation","kind":"value"}; tên và trạng thái phải lấy từ mô hình/manual.')
        check.update(stage=stage,kind=kind)
        if type(check.get('expected')) not in (str,int,float,bool) or isinstance(check['expected'],float) and not math.isfinite(check['expected']):raise ValueError('expected phải là số hữu hạn, chuỗi hoặc boolean.')
        tolerance=check.get('tolerance',1e-6)
        if type(tolerance) not in (int,float) or not math.isfinite(tolerance) or tolerance<0:raise ValueError('tolerance không hợp lệ.')
        if 'phase' in check:
            if not isinstance(check['phase'],str) or not REF.fullmatch(check['phase']):
                raise ValueError(f'checks[{index}].phase cần ref tới phase thực tế, ví dụ g.Phase_1; không dùng số, mảng hoặc đối tượng JSON.')
            if check['kind']!='value':
                raise ValueError(f'checks[{index}]: phase chỉ dùng đọc thuộc tính theo phase với kind=value. Đếm collection dùng kind=count và bỏ phase.')
            if check['ref'].endswith('.Active') and type(check['expected']) is not bool:
                raise ValueError(f'checks[{index}].expected cho Active phải là boolean JSON true/false, không phải chuỗi hoặc số. Không tự ép kiểu.')
    if checks and not spec.get('source','').strip():raise ValueError('Ghi nguồn manual/mục/trang cho các giá trị dự kiến.')
    return spec

def scalar(obj):
    try:return obj.value
    except AttributeError:return obj

def describe(obj):
    result=scalar(obj.Name)
    if not isinstance(result,str) or not result:raise ValueError('Chưa đọc được tên đối tượng.')
    return result

def inspect_progress(g,raw,resolve):
    spec=specification(raw)
    inventory={}
    # Collections are read afresh every call. Unavailable in this mode != absent.
    for collection in COLLECTIONS:
        try:
            members=list(getattr(g,collection))
            names=[];errors=[]
            for obj in members[:50]:
                try:names.append(describe(obj))
                except Exception as error:errors.append(str(error)[:200])
            inventory[collection]={'count':len(members),'names':names,'read_errors':errors,'truncated':len(members)>50}
        except Exception as error:inventory[collection]={'status':'unreadable','error':str(error)[:200]}
    phases=[]
    try:
        for phase in list(g.Phases)[:20]:
            record={}
            try:record['name']=describe(phase)
            except Exception as error:record['name_error']=str(error)[:200]
            for field in ('DeformCalcType','CalculationResult','ShouldCalculate'):
                try:
                    observed=scalar(getattr(phase,field))
                    if type(observed) not in (str,int,float,bool):raise ValueError('Không đọc được giá trị scalar.')
                    record[field]=observed
                except Exception as error:record[field]={'status':'unreadable','error':str(error)[:200]}
            try:record['previous']=describe(scalar(phase.PreviousPhase))
            except Exception:record['previous']={'status':'unreadable'}
            phases.append(record)
    except Exception:pass
    groups={key:[] for key in ('verified','missing_or_wrong','unreadable','unverified')}
    for check in spec['checks']:
        row=dict(check)
        ref=check['ref'] if check['ref'].startswith('g.') else 'g.'+check['ref']
        try:
            obj=resolve({'ref':ref})
            if 'phase' in check:
                phase_ref=check['phase'] if check['phase'].startswith('g.') else 'g.'+check['phase']
                phase=resolve({'ref':phase_ref})
                if ref.endswith('.Active'):
                    target=resolve({'ref':ref[:-7]})
                    # Read the actual per-phase property; None never becomes False.
                    actual=active(target,phase)
                else:
                    actual=scalar(obj[phase])
                    if ref.endswith('.Material') and type(actual) not in (str,int,float,bool,type(None)):
                        actual=describe(actual)
            elif check.get('kind')=='count':actual=len(obj)
            else:actual=scalar(obj)
            if actual is None or type(actual) not in (str,int,float,bool) or isinstance(actual,float) and not math.isfinite(actual):
                raise ValueError('Giá trị chưa đọc chắc chắn: '+type(actual).__name__)
            expected=check['expected']
            match=type(actual)==type(expected) and actual==expected
            if type(actual) in (int,float) and type(expected) in (int,float):match=abs(actual-expected)<=check.get('tolerance',1e-6)
            row.update(actual=actual,status='verified' if match else 'missing_or_wrong')
            groups[row['status']].append(row)
        except Exception as error:
            # A stale name or missing property is not proof that the physical object is absent.
            row.update(status='unreadable',error=str(error)[:500])
            groups['unreadable'].append(row)
    covered={check.get('stage','project') for check in spec['checks']}
    for stage in STAGES:
        if stage not in covered:groups['unverified'].append({'stage':stage,'reason':'Chưa cung cấp điều kiện đối chiếu từ manual.'})
    return {'inventory':inventory,'phases':phases,**groups,'source':spec.get('source',''),
            'model_completion_verified':False,'read_only':True,
            'note':'verified chỉ xác nhận các giá trị đã đọc khớp expected được cung cấp, chưa chứng minh nguồn manual hay toàn bộ mô hình. Không đổi chế độ, không ghi/xóa/tính toán.'}

def plan_resume(g,raw,resolve):
    progress=inspect_progress(g,raw,resolve)
    actions=[]
    for row in progress['unreadable']:
        actions.append({'action':'diagnose_read','ref':row['ref'],'phase':row.get('phase'),
                        'reason':row['error'],'instruction':'Đọc lại tên trong inventory và đúng chế độ; không coi là thiếu, không tạo/xóa/bật tắt đối tượng khi chưa đọc chắc chắn.'})
    for row in sorted(progress['missing_or_wrong'],key=lambda r:STAGES.index(r.get('stage','project'))):
        active_change=row['ref'].endswith('.Active')
        actions.append({'action':'verify_stage_then_set' if active_change else 'repair_after_fresh_inspection',
                        'ref':row['ref'],'phase':row.get('phase'),'actual':row['actual'],'expected':row['expected'],
                        'stage':row.get('stage','project'),'instruction':'Giữ phần đúng; xác minh đối tượng/vùng/phase rồi sửa và đọc lại. Không tự xóa/tạo lại mô hình hoặc đoán số liệu.'})
    return {'progress':progress,'keep':progress['verified'],'actions':actions,
            'next_step':actions[0] if actions else {'action':'supply_manual_checks' if progress['unverified'] else 'verify_model_before_calculate',
                                                'instruction':'Bổ sung điều kiện thiếu từ manual; verify_model trước calculate hoặc báo hoàn tất.'},
            'executable':False,'model_completion_verified':False,'note':'Đây là kế hoạch sửa đọc-only, không cấp quyền ghi. Mọi sửa đổi vẫn qua wrapper và guard hiện có.'}

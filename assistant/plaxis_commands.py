"""Structured PLAXIS API calls, independent of fixed problem templates; no Python evaluation."""
import json
import math
import re

_NAME=re.compile(r'[A-Za-z][A-Za-z0-9_]*\Z')
_INDEXED=re.compile(r'([A-Za-z][A-Za-z0-9_.]*)\[(\d{1,5})\]\Z')
_BLOCKED={'open','save','saveas','import','export','run','exec','execute','system','apply','evaluate','python','runscript','runpython'}


def _read_ref(arg):
    """Accept the shapes models write a read target in, or return None.

    Besides the canonical {'ref': ...}, a bare 'g.Phases' and an inline
    'g.Soils[2]' both name a target unambiguously, so they are translated
    rather than rejected.
    """
    if isinstance(arg,dict):return arg
    if not isinstance(arg,str):return None
    match=_INDEXED.fullmatch(arg)
    if match:
        name,index=match.group(1),int(match.group(2))
        if all(_NAME.fullmatch(p) for p in name.split('.')):return {'ref':name,'index':index}
        return None
    if all(_NAME.fullmatch(p) for p in arg.split('.')):return {'ref':arg}
    return None


def _join_read_args(args):
    """Fold a target and the element beside it into the single ref read takes.

    Models routinely split them, as [{'ref':'g.Materials'},{'index':0}] or
    [{'ref':'g.Materials'},0]. Both name one element unambiguously, so joining
    them beats failing a turn that may carry dozens of model-building steps.
    """
    if not isinstance(args,list) or len(args)!=2:return args
    ref=_read_ref(args[0])
    if ref is None or 'index' in ref:return args
    extra=args[1]
    if isinstance(extra,dict) and set(extra)=={'index'} and type(extra['index']) is int:
        index=extra['index']
    elif type(extra) is int and type(extra) is not bool:
        index=extra
    else:
        return args
    if not 0<=index<100000:return args
    return [dict(ref,index=index)]


def commands_from_json(raw):
    if not isinstance(raw,str):raise ValueError('commands cần là chuỗi JSON.')
    try:rows=json.loads(raw)
    except json.JSONDecodeError as error:
        # '..."mat"}]}]' instead of '..."mat"]}]': only the closing tail is wrong.
        from .online_automation import _rebalanced_tail,fix_mismatched_closers
        rows=fix_mismatched_closers(raw)
        if rows is None:rows=_rebalanced_tail(raw)
        if rows is None:
            # A bare character offset is not something a model can act on; show the spot.
            near=raw[max(0,error.pos-60):error.pos+20]
            raise ValueError(f'commands không phải JSON hợp lệ ({error.msg}) gần: …{near}… '
                             'Kiểm tra cặp ngoặc: mảng args đóng bằng ], lệnh đóng bằng }.') from None
    if not isinstance(rows,list) or not rows:raise ValueError('commands cần ít nhất một lệnh PLAXIS.')  # no batch-size cap
    def value(v,depth=0):
        if depth>12:raise ValueError('Tham số lồng quá sâu.')
        if isinstance(v,dict):
            if set(v)-{'ref','index'} or not isinstance(v.get('ref'),str):raise ValueError(
                'Đối tượng tham số chỉ hỗ trợ {"ref":"..."} hoặc {"ref":"...","index":n}. '
                'Toạ độ và số dùng trực tiếp, không gói vào đối tượng: ví dụ [x1,y1,x2,y2] thay vì [{"x":x1,"y":y1},...].')
            if not all(_NAME.fullmatch(p) for p in v['ref'].split('.')):raise ValueError('ref phải là tên đối tượng/property PLAXIS, không phải biểu thức Python.')
            if 'index' in v and (type(v['index']) is not int or not 0<=v['index']<100000):raise ValueError('index không hợp lệ.')
        elif isinstance(v,list):
            if len(v)>1000:raise ValueError('Mảng tham số quá lớn.')
            for x in v:value(x,depth+1)
        elif type(v) not in (str,int,float,bool,type(None)) or (isinstance(v,float) and not math.isfinite(v)):
            raise ValueError('Tham số PLAXIS không hợp lệ.')
    for row in rows:
        if not isinstance(row,dict) or set(row)-{'command','args','result'}:raise ValueError('Lệnh chỉ nhận command, args và result.')
        cmd=row.get('command','')
        if not isinstance(cmd,str) or not _NAME.fullmatch(cmd) or cmd.casefold() in _BLOCKED:
            raise ValueError('Cần tên lệnh API PLAXIS; không nhận shell/Python hoặc lệnh truy cập tệp.')
        args=row.get('args',[])
        if not isinstance(args,list) or len(args)>1000:raise ValueError('args phải là mảng tham số.')
        if cmd=='read':args=_join_read_args(args);row['args']=args
        for v in args:value(v)
        if 'result' in row and (not isinstance(row['result'],str) or not _NAME.fullmatch(row['result']) or row['result']=='g'):
            raise ValueError('result cần tên tham chiếu hợp lệ, khác g.')
        if cmd=='verify_model':
            if len(args)!=1:raise ValueError('verify_model cần một chuỗi JSON.')
            model_checks(args[0])
        if cmd=='new_project' and args:raise ValueError('new_project không nhận tham số.')
        if cmd=='read':
            ref=_read_ref(args[0]) if len(args)==1 else None
            if ref is None:
                raise ValueError('read cần đúng một ref, ví dụ {"command":"read","args":[{"ref":"g.Phases"}]}.')
            args=[ref];row['args']=args
        if cmd=='summarize' and len(args)!=1:raise ValueError('summarize cần một mảng số hoặc ref tới kết quả getresults.')
        if cmd=='soilcontour':
            if len(args)!=4 or any(type(a) not in (int,float) for a in args):
                raise ValueError('soilcontour cần 4 số: xmin, ymin, xmax, ymax.')
            if args[0]>=args[2] or args[1]>=args[3]:
                raise ValueError('soilcontour cần xmin<xmax và ymin<ymax.')
    return rows


_LIST_LIMIT=60


def _label(obj):
    """A PLAXIS object as 'Name <Type {guid}>', or just its repr.

    The bare repr a proxy prints is only a type and a GUID, so a read of a
    collection tells a model nothing about what the model already holds and it
    creates the same material or layer again. The identification carries that.
    """
    text=str(obj)[:300]
    for attr in ('Name','Identification'):
        try:
            name=getattr(obj,attr).value
        except Exception:
            continue
        if isinstance(name,str) and name:return name[:120]+' '+text
    return text


def _listed(value):
    """Element labels when value is a PLAXIS listable collection, else None."""
    try:
        count=len(value)
    except Exception:
        return None
    if not isinstance(count,int) or count<0:return None
    try:
        items=[_label(value[i]) for i in range(min(count,_LIST_LIMIT))]
    except Exception:
        return None
    listing={'count':count,'items':items}
    if count>_LIST_LIMIT:listing['note']=f'Chỉ liệt kê {_LIST_LIMIT} phần tử đầu trong {count}.'
    return listing


def plain(value,depth=0):
    if depth>3:return str(value)[:1000]
    if value is None or type(value) in (str,int,float,bool):return value if not isinstance(value,str) else value[:6000]
    if isinstance(value,(tuple,list)):return [plain(v,depth+1) for v in value[:100]]
    if isinstance(value,dict):return {str(k):plain(v,depth+1) for k,v in list(value.items())[:100]}
    listing=_listed(value)
    if listing is not None:return listing
    return _label(value)[:6000]


_GEOMETRY={'point','line','plate','polygon','rectangle','lineload','pointload','n2nanchor','fixedendanchor',
           'geogrid','embeddedbeamrow','embeddedbeam','well','drain','linedispl','pointdispl','polycurve','tunnel'}


def _outside_soil(g):
    """Warn when geometry sits off the soil body, or None when it all fits.

    A tutorial gives elevations from its own datum while soillayer stacks
    thicknesses down from y=0. Shifting the soil but not the wall leaves the
    structure hanging in empty space, where the phases simply never converge
    and nothing in the command results says why.
    """
    try:
        borehole=g.Boreholes[0]
        levels=[]
        for i in range(200):
            try:levels.append(float(g.getsoillayerlevel(borehole,i)))
            except Exception:break
        if len(levels)<2:return None
        top,bottom=max(levels),min(levels)
        stray=[]
        for point in g.Points:
            y=float(point.y.value)
            if not bottom-1e-6<=y<=top+1e-6:
                stray.append(f'{point.Name.value} (y={y:g})')
            if len(stray)>=10:break
    except Exception:
        return None
    if not stray:return None
    return (f'Hình học nằm ngoài khối đất (đất từ y={bottom:g} đến y={top:g}): '+', '.join(stray)+
            '. Đất và hình học đang ở hai hệ cao độ khác nhau; sửa cao độ lớp đất bằng setsoillayerlevel '
            'hoặc dời hình học về đúng khối đất trước khi mesh, nếu không các pha sẽ không hội tụ.')


_SEGMENT_COLLECTIONS={'n2nanchor':'NodeToNodeAnchors','lineload':'LineLoads','plate':'Plates',
                      'embeddedbeamrow':'EmbeddedBeamRows','geogrid':'Geogrids'}


def _two_points(args):
    """((x1,y1),(x2,y2)) when args spell a 2D segment by coordinates, else None."""
    if len(args)==4 and all(type(a) in (int,float) for a in args):
        return (tuple(args[:2]),tuple(args[2:]))
    if len(args)==2 and all(isinstance(p,(list,tuple)) and len(p)==2 and
                            all(type(c) in (int,float) for c in p) for p in args):
        return (tuple(args[0]),tuple(args[1]))
    return None


def _existing_segment(g,command,args):
    """The object a creation command would duplicate, or None.

    Models restart a construction sequence after any hiccup and issue the same
    anchors and loads again; PLAXIS accepts them, so the model silently grows
    stacked copies that double the stiffness and load. A segment with the same
    two ends is the same structural member.
    """
    collection=_SEGMENT_COLLECTIONS.get(command)
    target=_two_points(args) if collection else None
    if target is None:return None
    want=sorted(target)
    try:
        for obj in getattr(g,collection):
            line=obj.Parent
            ends=sorted(((float(line.First.x.value),float(line.First.y.value)),
                         (float(line.Second.x.value),float(line.Second.y.value))))
            if all(abs(a-b)<1e-6 for p,q in zip(ends,want) for a,b in zip(p,q)):return obj
    except Exception:
        return None
    return None


# PLAXIS 2D Reference Manual, "Calculation warning and errors in PLAXIS".
# A phase's LogInfo holds only the number, which a model otherwise guesses at.
_CALC_ERRORS={
    0:'Tính thành công, hội tụ.',
    11:'Định thức bằng 0: lưới xấu, thiếu điều kiện biên hoặc có cụm đất trôi nổi.',
    12:'Không tìm thấy bộ vật liệu: kiểm tra mọi đất/kết cấu đã gán vật liệu.',
    13:'Trọng lượng nước bằng 0: kiểm tra WaterWeight của project.',
    15:'Ma trận Jacobi gần 0: phần tử méo hoặc độ cứng chênh lệch quá lớn (>1e6).',
    16:'Định thức bằng 0: lưới xấu, thiếu điều kiện biên hoặc có cụm đất trôi nổi.',
    17:'Ma trận độ cứng gần suy biến: lưới xấu, độ cứng chênh lệch lớn, thiếu biên hoặc cụm trôi nổi.',
    19:'Ma trận độ cứng gần suy biến: lưới xấu, độ cứng chênh lệch lớn, thiếu biên hoặc cụm trôi nổi.',
    20:'Ma trận độ cứng gần suy biến: lưới xấu, độ cứng chênh lệch lớn, thiếu biên hoặc cụm trôi nổi.',
    24:'Có bộ vật liệu hệ số thấm bằng 0: tính dòng thấm/cố kết cần kx, ky > 0 ở mọi vật liệu đất '
       '(PermHorizontalPrimary, PermVertical).',
    25:'Trọng lượng nước ngầm bằng 0: kiểm tra WaterWeight.',
    29:'Lỗi phân rã ma trận: có cụm đất trôi nổi hoặc thiếu điều kiện biên.',
    33:'Lỗi nội bộ, thường do embedded beam row dài 0 trong 2D: mesh lại.',
    34:'Tính dòng thấm không hội tụ: kiểm tra thông số thấm và cài đặt phase.',
    35:'Không có biên thoát nước: kiểm tra điều kiện biên dòng thấm.',
    36:'NaN trong ma trận độ cứng phần tử: phần tử diện tích 0 hoặc thông số vật liệu sai.',
    39:'NaN khi tính, phân kỳ nặng: thông số đầu vào sai.',
    40:'Phân kỳ nặng: thông số đất bất hợp lý, xem vùng lỗi ở bước cuối.',
    47:'Bộ thông số vật liệu không hợp lệ.',
    48:'Lỗi đọc file dòng thấm: giảm chênh lệch hệ số thấm giữa các vật liệu.',
    101:'Khối đất sụp đổ: phá hoại, xem kết quả Output để biết vùng phá hoại.',
    102:'Không đủ bước tải: tăng Max steps.',
    103:'Thủ tục tăng tải thất bại: kiểm tra đầu vào và kết quả Output.',
    104:'Không đạt thời gian cố kết yêu cầu, có thể do phá hoại.',
    107:'Chưa đạt SumMsf yêu cầu: tăng Max steps.',
    110:'Không đạt điều kiện chính xác ở bước cuối: tăng Max steps.',
    111:'Khối đất sụp đổ và không đạt điều kiện chính xác (101 + 110).',
    112:'Không đủ bước tải và không đạt điều kiện chính xác (102 + 110).',
    113:'Tăng tải thất bại và không đạt điều kiện chính xác (103 + 110).',
    117:'Chưa đạt SumMsf và không đạt điều kiện chính xác (107 + 110).',
    248:'Tham chiếu bộ vật liệu không tồn tại: định nghĩa lại staged construction của phase.',
    250:'Thiếu dữ liệu lưới: mesh lại.',
}


def _explain_log(ref,value):
    """Append the manual's meaning to a numeric phase LogInfo, else return it unchanged."""
    if not ref.endswith('.LogInfo'):return value
    try:code=int(str(value).strip())
    except (TypeError,ValueError):return value
    meaning=_CALC_ERRORS.get(code)
    return f'{code}: {meaning}' if meaning else value


def _arity(line):
    """Number of top-level parameters in one signature line ('Borehole NumberWithUnitLength'' -> 2)."""
    depth=0;count=0;inside=False
    for char in line.strip():
        if char=='<':depth+=1
        elif char=='>':depth-=1
        if char==' ' and depth==0:inside=False
        elif not inside:count+=1;inside=True
    return count


def _signature(listing,name):
    """The parameter pattern PLAXIS prints for one command in g.commands().

    Each entry is a header line 'name (alias)' followed by indented pattern
    lines; return that block, or a short note when the command is unknown.
    """
    lines=listing.replace('\r','').split('\n')
    wanted=name.strip().casefold()
    for i,line in enumerate(lines):
        head=line.strip().split(' ')[0].casefold()
        if line[:1].strip() and head==wanted:
            block=[line]
            for follow in lines[i+1:]:
                if follow[:1].strip():break
                block.append(follow)
            return '\n'.join(block)[:3000]
    return f'Không có lệnh {name} trên đối tượng gốc g; tra bằng commands trên đối tượng con.'


def model_checks(raw):
    if not isinstance(raw,str):raise ValueError('verify_model cần chuỗi JSON các phép kiểm tra.')
    checks=json.loads(raw)
    if not isinstance(checks,list) or not checks:raise ValueError('verify_model cần ít nhất một phép kiểm tra.')
    for check in checks:
        if not isinstance(check,dict) or set(check)-{'ref','expected','kind','tolerance'}:raise ValueError('Phép kiểm tra chỉ có ref, expected, kind, tolerance.')
        if _read_ref(check.get('ref')) is None:raise ValueError('ref kiểm tra không hợp lệ.')
        expected=check.get('expected')
        if type(expected) not in (str,int,float,bool) or isinstance(expected,float) and not math.isfinite(expected):raise ValueError('expected phải là số, chuỗi hoặc boolean.')
        if check.get('kind','value') not in ('value','count'):raise ValueError('kind chỉ nhận value hoặc count.')
        tolerance=check.get('tolerance',1e-6)
        if type(tolerance) not in (int,float) or not math.isfinite(tolerance) or tolerance<0:raise ValueError('tolerance phải là số hữu hạn không âm.')
    return checks


_STAGED=('Soils','Plates','NodeToNodeAnchors','FixedEndAnchors','LineLoads','PointLoads','LineDisplacements',
         'PointDisplacements','Interfaces','EmbeddedBeams','Geogrids')


def _value(item):
    try:return item.value
    except Exception:return item


def phase_changes(g):
    """Per calculation phase: what it switches on/off or re-assigns relative to its
    previous phase. Empty for objects whose per-phase state cannot be read."""
    try:phases=list(g.Phases)
    except Exception:return []
    objects=[]
    for collection in _STAGED:
        try:objects+=[(str(_value(o.Name)),o,collection=='Soils') for o in getattr(g,collection)]
        except Exception:continue
    def state(phase):
        current={}
        for name,obj,soil in objects:
            try:active=bool(_value(obj.Active[phase]))
            except Exception:continue
            material=None
            if soil:
                try:material=str(_value(_value(obj.Material[phase]).Identification))
                except Exception:pass
            current[name]=(active,material)
        return current
    states={str(_value(p.Name)):state(p) for p in phases}
    rows=[]
    for phase in phases[1:]:
        name=str(_value(phase.Name))
        try:previous=str(_value(_value(phase.PreviousPhase).Name))
        except Exception:continue
        before,after=states.get(previous,{}),states.get(name,{})
        on=[k for k,(a,_) in after.items() if a and not before.get(k,(False,None))[0]]
        off=[k for k,(a,_) in after.items() if not a and before.get(k,(False,None))[0]]
        mats=[k for k,(_,m) in after.items() if m and before.get(k,(None,None))[1] not in (None,m)]
        try:kind=_value(phase.DeformCalcType)
        except Exception:kind=None
        try:pending=bool(_value(phase.ShouldCalculate))
        except Exception:pending=True
        rows.append({'phase':name,'previous':previous,'kind':kind,'pending':pending,'on':on,'off':off,'materials':mats,
                     'state':tuple(sorted(after.items()))})
    return rows


def _empty_phases(g):
    """Problems in Plastic phases about to be calculated: a phase that changes nothing,
    phases whose whole activation state is identical (tutorial 3, second attempt: five
    phases all started from InitialPhase and switching on the same wall and load)."""
    rows=[r for r in phase_changes(g) if r['kind']==4]
    pending=[r for r in rows if r['pending']]
    problems=[f"{r['phase']} không thay đổi gì so với {r['previous']}" for r in pending if not (r['on'] or r['off'] or r['materials'])]
    groups={}
    for r in pending:groups.setdefault(r['state'],[]).append(r['phase'])
    problems+=['các phase '+', '.join(names)+' có trạng thái bật/tắt giống hệt nhau' for names in groups.values() if len(names)>1]
    starts={}
    for r in pending:starts.setdefault(r['previous'],[]).append(r['phase'])
    problems+=[', '.join(names)+f' đều bắt đầu từ {start}; thi công theo giai đoạn cần phase sau nối tiếp phase trước '
               '(tạo bằng phase [{"ref":"Phase_trước"}])' for start,names in starts.items() if len(names)>2]
    return problems


# Manual labels and common guesses -> PLAXIS 2D API property names (seen in real runs).
_PROPERTY_ALIASES={
    'weight':'w','w':'w','drainagetype':'DrainageType','drainage':'DrainageType','type':'DrainageType',
    'unsaturatedunitweight':'gammaUnsat','gammaunsat':'gammaUnsat','saturatedunitweight':'gammaSat','gammasat':'gammaSat',
    'axialstiffness':'EA1','axialstiffnessea1':'EA1','ea':'EA1','bendingstiffness':'EI','ei':'EI',
    'm':'PowerM','power':'PowerM','powerm':'PowerM','c':'cRef','cref':'cRef','cohesion':'cRef',
    'phi':'phi','frictionangle':'phi','psi':'psi','dilatancyangle':'psi','nu':'nu','poissonsratio':'nu',
    'nuur':'nuUR','e50ref':'E50Ref','e50':'E50Ref','eoedref':'EoedRef','eoed':'EoedRef','eurref':'EURRef','eur':'EURRef',
    'lspacing':'Lspacing','outofplanespacing':'Lspacing','rinter':'Rinter','strengthreductionfactor':'Rinter',
    'k0determination':'K0Determination','ocr':'OCR','pop':'POP','kx':'PermHorizontalPrimary','ky':'PermVertical',
}


def _property_hint(g,target,name,exc):
    """Explain a failed setproperties: the real property name, or the order a
    read-only property needs (Rinter after manual strength, K0NC is computed)."""
    text=str(exc)
    if re.search(r'read-only property Rinter',text):
        return 'Rinter chỉ đặt được sau InterfaceStrengthDetermination="Manual"; đặt thuộc tính đó trước rồi đặt lại Rinter.'
    if re.search(r'read-only property K0NC',text):
        return 'K0NC do PLAXIS tự tính khi K0Determination="Automatic". Giữ Automatic như manual, không đổi sang Manual để né lỗi này.'
    if 'Unknown property' not in text:return ''
    key=re.sub(r'[^a-z0-9]','',str(name).lower())
    guess=_PROPERTY_ALIASES.get(key)
    columns=[]
    try:columns=str(g.tabulate(target)).replace('\r','').split('\n')[0].split('\t')[1:]
    except Exception:pass
    if columns and guess not in columns:
        if guess and guess.lower() in {c.lower() for c in columns}:guess=next(c for c in columns if c.lower()==guess.lower())
        elif guess and guess.rstrip('0123456789') in columns:guess=guess.rstrip('0123456789')  # anchors use EA, plates EA1
        elif key in {re.sub(r'[^a-z0-9]','',c.lower()) for c in columns}:guess=None
    if (not guess or guess not in columns) and columns:
        import difflib
        lowered={re.sub(r'[^a-z0-9]','',c.lower()):c for c in columns}
        match=difflib.get_close_matches(key,list(lowered),n=1,cutoff=0.5)
        guess=lowered[match[0]] if match else None
    hint=f'Thuộc tính "{name}" không tồn tại'+(f'; dùng "{guess}"' if guess else '')+'.'
    if columns:hint+=' Tên hợp lệ của đối tượng này: '+', '.join(columns[:60])
    return hint


def _soils_without_material(g):
    """Names of soil regions whose material is positively read as unassigned. Anything
    that cannot be read is skipped, so this never blocks meshing on a guess."""
    missing=[]
    try:soils=list(g.Soils)
    except Exception:return missing
    for soil in soils:
        try:
            value=soil.Material.value
        except Exception:
            continue
        if value is None or 'not assigned' in str(value).lower():
            try:missing.append(str(soil.Name.value))
            except Exception:missing.append(str(soil)[:60])
    return missing


def _has(obj,name):
    """PLAXIS proxies raise their own error (not AttributeError) for a missing member."""
    try:
        getattr(obj,name)
        return True
    except Exception:
        return False


def execute_commands(server,g,rows,on_status=None,session=None):
    """session keeps result names ('bh', 'sand') across separate tool calls on the same
    PLAXIS project, so a later call can refer to objects created earlier."""
    from .windows_apps import _STOP,wait_automation
    session=session if session is not None else {'aliases':{},'created':{}}
    aliases={**session['aliases'],'g':g};results=[];started=False;failed_properties=[]
    def resolve(v):
        if isinstance(v,dict):
            parts=v['ref'].split('.')
            root=aliases.get(parts[0])
            if root is None and parts[0][:1].islower():
                # A lowercase root is a result name, not a PLAXIS object (those are
                # capitalised: Borehole_1, Soil_1). Sending it to PLAXIS only yields
                # 'Unrecognized token', which the model cannot diagnose.
                known=', '.join(sorted(k for k in aliases if k!='g')) or 'chưa có'
                raise NameError(f"Tên '{parts[0]}' chưa được định nghĩa trong dự án PLAXIS này (tên đã có: {known}). "
                                "Dùng tên đối tượng PLAXIS như Borehole_1 hoặc g.Boreholes[0], hoặc tạo lại với result.")
            if root is None:
                root=getattr(g,parts.pop(0))
            else:parts=parts[1:]
            for part in parts:root=getattr(root,part)
            return root[v['index']] if 'index' in v else root
        if isinstance(v,list):return [resolve(x) for x in v]
        return v
    for index,row in enumerate(rows):
        started=False;method_on_object=False
        try:
            wait_automation()
            if _STOP.is_set():raise RuntimeError('Đã dừng điều khiển PLAXIS.')
            if on_status:on_status(f'PLAXIS: bước {index+1}/{len(rows)} · {row["command"]}')
            args=[resolve(v) for v in row.get('args',[])]
            if row['command']=='read':
                result=args[0]
                ref=row['args'][0].get('ref','')
                try:raw=result.value
                except Exception:raw=result
                explained=_explain_log(ref,raw)
                if explained is not raw:result=explained
            elif row['command']=='verify_model':
                checks=model_checks(args[0]);verified=[]
                for check in checks:
                    observed=resolve(_read_ref(check['ref']))
                    if check.get('kind')=='count':actual=len(observed)
                    else:
                        try:actual=observed.value
                        except Exception:actual=observed
                        actual=plain(actual)
                    expected=check['expected']
                    match=(type(actual) in (int,float) and type(expected) in (int,float) and math.isfinite(actual) and abs(actual-expected)<=check.get('tolerance',1e-6)) or (type(actual)==type(expected) and actual==expected)
                    verified.append({'ref':check['ref'],'expected':expected,'actual':actual,'match':match})
                result={'verified':all(c['match'] for c in verified),'checks':verified,'scope':'Chỉ kiểm tra các thuộc tính liệt kê; không xác nhận toàn bộ mô hình.'}
                if not result['verified']:
                    return {'ok':False,'results':results,'failed_step':index+1,'failed_command':'verify_model','not_executed':not results,
                            'error':'Mô hình chưa khớp điều kiện kiểm tra: '+json.dumps(verified,ensure_ascii=False)[:2000]}
            elif row['command']=='summarize':
                numbers=[]
                for v in args[0]:
                    if len(numbers)>=1000000:raise ValueError('Mảng kết quả vượt giới hạn 1000000 giá trị.')
                    number=float(v)
                    if not math.isfinite(number):raise ValueError('Kết quả chứa số không hữu hạn.')
                    numbers.append(number)
                if not numbers:raise ValueError('Chưa có giá trị số để tổng hợp.')
                result={'count':len(numbers),'min':min(numbers),'max':max(numbers),'max_abs':max(abs(x) for x in numbers)}
            elif row['command']=='signature':
                # g.commands() lists every command with its parameter pattern,
                # but it runs to tens of thousands of characters and a read is
                # cut at 6000, so the command a model needs is usually lost.
                result=_signature(str(g.commands()),args[0])
            elif row['command']=='soilcontour':
                # initializerectangular lives on g.SoilContour, and command names may
                # not contain dots; without this the soil stays at its 12x8 default
                # and any geometry beyond it is detached from the soil body.
                started=True
                result=g.SoilContour.initializerectangular(*args)
            else:
                existing=_existing_segment(g,row['command'],args)
                if existing is not None:
                    if row.get('result'):aliases[row['result']]=existing
                    results.append({'step':index+1,'command':row['command'],'value':plain(existing),'truncated':False,
                                    'skipped':'Đã có đối tượng cùng hai đầu mút; không tạo lại. Dùng đối tượng này cho bước sau.'})
                    continue
                signature=json.dumps([row['command'],row.get('args',[])],sort_keys=True,ensure_ascii=False)
                name=row.get('result')
                if name and session['created'].get(name)==signature and name in aliases:
                    # Retrying a batch must not create a second borehole/point/material.
                    results.append({'step':index+1,'command':row['command'],'value':plain(aliases[name]),'truncated':False,
                                    'skipped':f"Đã tạo '{name}' bằng đúng lệnh này ở lần trước; dùng lại, không tạo trùng."})
                    continue
                if row['command']=='calculate':
                    empty=_empty_phases(g)
                    # Warn once per identical set; a deliberate repeat (e.g. a water-level-only
                    # phase this check cannot see) is then allowed.
                    if empty and session.get('empty_warned')!=empty:
                        session['empty_warned']=empty
                        raise RuntimeError('Chưa tính, các phase có vấn đề: '+'; '.join(empty)+
                            '. Theo manual, mỗi phase phải kích hoạt tải/tường/neo hoặc tắt khối đất đào, và nối tiếp phase trước. Dùng set [{"ref":"Tên.Active"},{"ref":"Phase_x"},true/false] '
                            'rồi đọc lại model_state. Nếu phase chỉ đổi mực nước (kiểm tra này không thấy), gọi calculate lần nữa.')
                if row['command'] in ('mesh','gotomesh'):
                    missing=_soils_without_material(g)
                    if missing:
                        raise RuntimeError('Chưa sang chế độ lưới/chia lưới: các vùng đất sau chưa có vật liệu: '+', '.join(missing[:10])+
                            '. Ở chế độ soil/structures, gán: lớp đất setmaterial [{"ref":"g.Soillayers","index":i},mat]; '
                            'polygon setmaterial [{"ref":"g.Polygon_x.Soil"},mat]. Nếu đã lỡ sang mesh/stages, gọi gotostructures trước khi gán.')
                if row['command']=='new_project':method=server.new
                elif row['command']=='initializerectangular' and not (args and _has(args[0],'initializerectangular')):
                    method=g.SoilContour.initializerectangular
                elif args and not isinstance(args[0],(int,float,str,bool,list)) and not _has(g,row['command']) and _has(args[0],row['command']):
                    # Object method: {"command":"initializerectangular","args":[{"ref":"g.SoilContour"},0,0,5,4]}
                    method=getattr(args[0],row['command']);args=args[1:];method_on_object=True
                elif not _has(g,row['command']):
                    raise AttributeError(f"Lệnh '{row['command']}' không có ở cấp g. Nếu đây là lệnh của một đối tượng, "
                                         "đặt đối tượng làm tham số đầu tiên, ví dụ {\"command\":\"initializerectangular\",\"args\":[{\"ref\":\"g.SoilContour\"},0,0,5,4]}; "
                                         "dùng command 'signature' với tên lệnh để xem đúng cú pháp.")
                else:method=getattr(g,row['command'])
                started=True
                result=method(*args)
            if row['command']=='new_project':
                session['aliases'].clear();session['created'].clear()
                aliases={'g':g}
            if row.get('result'):
                aliases[row['result']]=result
                if row['command'] not in ('read','info','signature','summarize','verify_model'):
                    session['aliases'][row['result']]=result
                    session['created'][row['result']]=json.dumps([row['command'],row.get('args',[])],sort_keys=True,ensure_ascii=False)
            truncated=isinstance(result,(tuple,list,str)) and len(result)>(6000 if isinstance(result,str) else 100)
            results.append({'step':index+1,'command':row['command'],'value':plain(result),'truncated':truncated})
        except Exception as exc:
            if row['command']=='read':
                # Reads observe state without changing it, so a bad one must not
                # discard the model-building steps batched alongside it.
                results.append({'step':index+1,'command':'read','value':None,'error':str(exc)[:500],
                                'note':'Bước đọc lỗi, không ảnh hưởng mô hình; các bước sau vẫn chạy.'})
                continue
            if row['command']=='setproperties':
                # Property writes are independent: one bad name must not silently drop the
                # rest of a material (seen: Sand kept phi=0 after an unknown "m").
                args=row.get('args',[])
                try:target=resolve(args[0])
                except Exception:target=None
                names=[args[i] for i in range(1,len(args),2) if isinstance(args[i],str)]
                hint=_property_hint(g,target,names[0] if names else '',exc) if target is not None else ''
                failed_properties.append({'step':index+1,'properties':names[:6],'error':str(exc)[:300],**({'hint':hint} if hint else {})})
                results.append({'step':index+1,'command':'setproperties','value':None,'error':str(exc)[:300],**({'hint':hint} if hint else {})})
                continue
            remaining=[r.get('command','?')+json.dumps(r.get('args',[]),ensure_ascii=False)[:70] for r in rows[index+1:]]
            failure={'ok':False,'results':results,'failed_step':index+1,'failed_command':row['command'],
                    'error':str(exc)[:2000],'command_started':started,'uncertain':started,
                    'not_executed':not results and not started,
                    'note':'Đã dừng tại bước lỗi. Không chạy lại những bước đã thực hiện; đọc trạng thái hiện tại trước khi sửa.'}
            if remaining:
                # The model treated a stopped batch as done and skipped the wall interfaces,
                # excavation lines and strut; name what never ran.
                failure['not_run']=remaining[:40]
                failure['note']+=f' {len(remaining)} lệnh sau bước lỗi CHƯA chạy (xem not_run); gửi lại các lệnh đó sau khi sửa.'
            if row['command']=='set' and len(row.get('args',[]))==3 and isinstance(row['args'][2],bool):
                ref=row['args'][0].get('ref','') if isinstance(row['args'][0],dict) else ''
                if not ref.endswith('.Active'):
                    failure['activation_hint']=('Kích hoạt theo phase phải đặt thuộc tính Active của đối tượng, dùng tên đối tượng: '
                        'set [{"ref":"Plate_1_1.Active"},{"ref":"p1"},true]. Đọc tên ở g.Plates/g.LineLoads/g.Interfaces trong model_state.')
            if row['command'] in ('posinterface','neginterface'):
                try:target=_label(resolve(row.get('args',[None])[0]))
                except Exception:target=''
                if re.search(r'<Plate\b',target):
                    failure['object_hint']=('Mặt phân cách tạo trên ĐƯỜNG hình học của tường, không trên tấm: '
                        'posinterface [{"ref":"Line_1"}] (đọc g.Lines để biết tên đường của tường).')
            if row['command'] in ('setmaterial','set','activate','deactivate') and re.search(
                    r'Tried executing, but failed|Cannot apply the properties|Requested attribute .(?:Soil|Active|Material). is not present',str(exc)):
                # The model guessed for 20 rounds here: in staged construction these
                # properties are per phase and the objects are the split soil clusters.
                failure['phase_hint']=('Nếu đang ở chế độ phase (sau gotostages): thuộc tính phụ thuộc phase, phải kèm phase, '
                    'ví dụ setmaterial [{"ref":"Soil_1_1"},{"ref":"g.InitialPhase"},{"ref":"clay"}] hoặc '
                    'set [{"ref":"Soil_1_1.Material"},{"ref":"g.InitialPhase"},{"ref":"clay"}]; tên khối đất đọc từ g.Soils, '
                    'không dùng Polygon_x. Nếu đang dựng hình: gán qua thuộc tính .Soil của polygon. Cách chắc nhất: '
                    'gotosoil/gotostructures, gán vật liệu cho mọi vùng rồi mới chia lưới lại.')
            if row['command']=='setmaterial' and 'Invalid parameters' in str(exc):
                try:target=_label(resolve(row.get('args',[None])[0]))
                except Exception:target=''
                if re.search(r'<(?:Line|Point|Polygon)\b',target):
                    # Seen: the wall material was assigned to the geometry line 'wall_line'.
                    failure['object_hint']=('Đối tượng nhận vật liệu là hình học ('+target.split(' <')[0]+'), không phải phần tử. '
                        'Gán cho phần tử nằm trên đó: tấm {"ref":"g.Plates","index":i}, neo {"ref":"g.FixedEndAnchors","index":i} '
                        'hoặc {"ref":"g.NodeToNodeAnchors","index":i}, đất của polygon {"ref":"g.Polygon_x.Soil"}. Đọc model_state để biết chỉ số.')
            if 'Invalid parameters' in str(exc):
                # PLAXIS validates arguments before acting, so nothing changed; give the
                # accepted forms right away instead of letting the model guess for 8 rounds.
                failure.update(uncertain=False,command_started=False,not_executed=not results)
                try:
                    listing=_signature(str(g.commands()),row['command'])
                    counts=sorted({_arity(line) for line in listing.splitlines()[1:] if line.strip() and 'no parameters' not in line}|
                                  ({0} if 'no parameters' in listing else set()))
                    given=len(row.get('args',[]))-(1 if method_on_object else 0)
                    if counts and given not in counts:
                        failure['arguments_hint']=(f"Đã truyền {given} tham số cho {row['command']}; các dạng hợp lệ nhận "
                                                   +' hoặc '.join(str(c) for c in counts)+' tham số. Bỏ tham số thừa, không thử lại cùng số lượng.')
                except Exception:pass
                try:failure['signature']=_signature(str(g.commands()),row['command'])+(
                    '\nMỗi dòng là một dạng tham số hợp lệ; truyền đúng số lượng. Đối tượng dùng {"ref":"Tên_đối_tượng"}, '
                    'không dùng chuỗi "Borehole_1".')
                except Exception:pass
            return failure
    if failed_properties:
        return {'ok':False,'results':results,'failed_command':'setproperties','command_started':True,'uncertain':False,
                'not_executed':False,'failed_properties':failed_properties,
                'error':f'{len(failed_properties)} lệnh setproperties lỗi; các lệnh khác trong nhóm đã chạy.',
                'note':'Chỉ sửa và gửi lại các thuộc tính trong failed_properties (xem hint), không gửi lại cả nhóm.'}
    answer={'ok':True,'results':results,
            'note':'Các lệnh đã trả kết quả. Hãy chạy tiếp bước kế tiếp của bài; chỉ kết luận mô hình đúng tài liệu '
                   'hoặc tính toán hội tụ sau khi đọc trạng thái pha và kết quả Output. Kết quả lệnh chưa phải bằng chứng hội tụ.'}
    answer['model_verified']=any(r['command']=='verify_model' and r['value'].get('verified') for r in results)
    if any(row['command'] in _GEOMETRY for row in rows):
        detached=_outside_soil(g)
        if detached:answer['warning']=detached
    return answer


_SNAPSHOT=('Boreholes','Soillayers','Soils','Materials','Points','Lines','Polygons','Plates','Interfaces',
           'LineLoads','PointLoads','LineDisplacements','PointDisplacements','NodeToNodeAnchors','FixedEndAnchors','EmbeddedBeams','Phases')
_MODEL_TYPES={0:'Plane strain',1:'Axisymmetric'}
_CHANGES_READONLY={'read','info','signature','summarize','verify_model'}


def model_snapshot(g,limit=2400):
    """Compact view of what the open PLAXIS model already holds, so the model can see
    duplicates and what a failed batch left behind without guessing."""
    lines=[]
    try:
        kind=g.Project.ModelType.value
        lines.append(f"Project: ModelType={_MODEL_TYPES.get(kind,kind)} ({kind})")
    except Exception:pass
    for attr in _SNAPSHOT:
        try:items=list(getattr(g,attr))
        except Exception:continue
        if not items:continue
        names=[]
        for item in items[:8]:
            label=_label(item).split(' <')[0]
            names.append(label[:40])
        lines.append(f"{attr}: {len(items)} ({', '.join(names)}{', …' if len(items)>8 else ''})")
    changes=phase_changes(g) if any(l.startswith('Phases:') and not l.startswith('Phases: 1 ') for l in lines) else []
    for row in changes:
        parts=[]
        if row['on']:parts.append('bật '+', '.join(row['on'][:6]))
        if row['off']:parts.append('tắt '+', '.join(row['off'][:6]))
        if row['materials']:parts.append('đổi vật liệu '+', '.join(row['materials'][:4]))
        lines.append(f"{row['phase']} (từ {row['previous']}): "+('; '.join(parts) if parts else 'KHÔNG THAY ĐỔI GÌ'))
    missing=_soils_without_material(g)
    if missing:
        lines.append('CHƯA CÓ VẬT LIỆU: '+', '.join(missing[:10])+' (chỉ các khối này cần gán; khối khác đã có vật liệu)')
    text='; '.join(lines) if len(lines)>1 or not lines or not lines[0].startswith('Project:') else ''
    text=text or ((lines[0]+'; ') if lines else '')+'Mô hình trống (chưa có borehole, lớp đất, vật liệu, hình học hay phase).'
    return text[:limit]


_SESSIONS={}


def run_batch(server,g,rows,on_status=None,port=None):
    """Execute one tool call with per-project names, then attach the model state when the
    batch failed or changed the model."""
    try:project=str(g.Project)
    except Exception:project='unknown'
    session=_SESSIONS.setdefault((port,project),{'aliases':{},'created':{}})
    assigns=any(r.get('command')=='setmaterial' for r in rows)
    before=set(_soils_without_material(g)) if assigns else set()
    result=execute_commands(server,g,rows,on_status,session)
    if assigns and before:
        still=before&set(_soils_without_material(g))
        if still:
            result['material_warning']=('setmaterial trả OK nhưng các vùng sau VẪN chưa có vật liệu: '+', '.join(sorted(still))+
                '. Đối tượng vừa gán là vùng khác (thứ tự g.Soils không theo thứ tự vẽ). Gán theo tên vùng hoặc qua Polygon_x.Soil, rồi đọc lại model_state.')
    if any(r['command']=='new_project' for r in rows):
        try:project=str(g.Project)
        except Exception:pass
        _SESSIONS[(port,project)]={'aliases':{},'created':{}}
    first=not session.get('seen');session['seen']=True
    # First contact with this project: show what is already there before anything is built.
    if first or not result.get('ok') or any(r['command'] not in _CHANGES_READONLY for r in rows):
        try:
            result['model_state']=model_snapshot(g)
            result['model_state_note']=('model_state là trạng thái thật của PLAXIS sau lệnh này. Trước khi tạo borehole, lớp đất, '
                                        'vật liệu hay hình học, kiểm tra ở đây và dùng lại đối tượng đã có; không tạo trùng.')
        except Exception as exc:result['model_state']='Chưa đọc được trạng thái mô hình: '+str(exc)[:200]
    names=sorted(session['aliases'])
    if names:result['names']=('Tên dùng lại được ở lệnh sau: '+', '.join(names))[:600]
    return result

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
    if not isinstance(raw,str) or len(raw)>50000:raise ValueError('commands cần là chuỗi JSON tối đa 50000 ký tự.')
    rows=json.loads(raw)
    if not isinstance(rows,list) or not 1<=len(rows)<=40:raise ValueError('Mỗi lượt cần 1–40 lệnh PLAXIS.')
    def value(v,depth=0):
        if depth>12:raise ValueError('Tham số lồng quá sâu.')
        if isinstance(v,dict):
            if set(v)-{'ref','index'} or not isinstance(v.get('ref'),str):raise ValueError('Đối tượng tham số chỉ hỗ trợ ref và index.')
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


def execute_commands(server,g,rows,on_status=None):
    from .windows_apps import _STOP,wait_automation
    aliases={'g':g};results=[];started=False
    def resolve(v):
        if isinstance(v,dict):
            parts=v['ref'].split('.')
            root=aliases.get(parts[0])
            if root is None:
                root=getattr(g,parts.pop(0))
            else:parts=parts[1:]
            for part in parts:root=getattr(root,part)
            return root[v['index']] if 'index' in v else root
        if isinstance(v,list):return [resolve(x) for x in v]
        return v
    for index,row in enumerate(rows):
        started=False
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
                method=server.new if row['command']=='new_project' else getattr(g,row['command'])
                started=True
                result=method(*args)
            if row.get('result'):aliases[row['result']]=result
            truncated=isinstance(result,(tuple,list,str)) and len(result)>(6000 if isinstance(result,str) else 100)
            results.append({'step':index+1,'command':row['command'],'value':plain(result),'truncated':truncated})
        except Exception as exc:
            if row['command']=='read':
                # Reads observe state without changing it, so a bad one must not
                # discard the model-building steps batched alongside it.
                results.append({'step':index+1,'command':'read','value':None,'error':str(exc)[:500],
                                'note':'Bước đọc lỗi, không ảnh hưởng mô hình; các bước sau vẫn chạy.'})
                continue
            return {'ok':False,'results':results,'failed_step':index+1,'failed_command':row['command'],
                    'error':str(exc)[:2000],'command_started':started,'uncertain':started,
                    'not_executed':not results and not started,
                    'note':'Đã dừng tại bước lỗi. Không chạy lại những bước đã thực hiện; đọc trạng thái hiện tại trước khi sửa.'}
    answer={'ok':True,'results':results,
            'note':'Các lệnh đã trả kết quả. Hãy chạy tiếp bước kế tiếp của bài; chỉ kết luận mô hình đúng tài liệu '
                   'hoặc tính toán hội tụ sau khi đọc trạng thái pha và kết quả Output. Kết quả lệnh chưa phải bằng chứng hội tụ.'}
    if any(row['command'] in _GEOMETRY for row in rows):
        detached=_outside_soil(g)
        if detached:answer['warning']=detached
    return answer

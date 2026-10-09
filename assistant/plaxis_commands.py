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


def plain(value,depth=0):
    if depth>3:return str(value)[:1000]
    if value is None or type(value) in (str,int,float,bool):return value if not isinstance(value,str) else value[:6000]
    if isinstance(value,(tuple,list)):return [plain(v,depth+1) for v in value[:100]]
    if isinstance(value,dict):return {str(k):plain(v,depth+1) for k,v in list(value.items())[:100]}
    return str(value)[:6000]


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
            if row['command']=='read':result=args[0]
            elif row['command']=='summarize':
                numbers=[]
                for v in args[0]:
                    if len(numbers)>=1000000:raise ValueError('Mảng kết quả vượt giới hạn 1000000 giá trị.')
                    number=float(v)
                    if not math.isfinite(number):raise ValueError('Kết quả chứa số không hữu hạn.')
                    numbers.append(number)
                if not numbers:raise ValueError('Chưa có giá trị số để tổng hợp.')
                result={'count':len(numbers),'min':min(numbers),'max':max(numbers),'max_abs':max(abs(x) for x in numbers)}
            elif row['command']=='soilcontour':
                # initializerectangular lives on g.SoilContour, and command names may
                # not contain dots; without this the soil stays at its 12x8 default
                # and any geometry beyond it is detached from the soil body.
                started=True
                result=g.SoilContour.initializerectangular(*args)
            else:
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
    return {'ok':True,'results':results,
            'note':'Các lệnh đã trả kết quả. Chưa tự xác nhận mô hình đúng tài liệu hoặc tính toán hội tụ; cần đọc trạng thái pha và kết quả Output.'}

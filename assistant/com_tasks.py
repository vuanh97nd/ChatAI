"""Windows COM worker. Attach by full document path, never by ActiveDocument alone."""
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from .excel import digest,scalar
from .tools import schema,TEXT
from .office_batch import operations
from .task_tools import run_child

SCHEMAS=[
 schema('excel_com','Excel COM: đọc/sửa workbook đang mở bằng đường dẫn đầy đủ, gom operations JSON: read{sheet,range}, write{sheet,range,values:ma trận}, formula{sheet,range,value}, format{sheet,range,bold,font,size,number_format,color}, filter{sheet,range,field,criteria}, chart{sheet,range,anchor,title}, calculate{}, save{}. Backup workbook trước ghi; trả readback từng vùng. Không chọn ActiveWorkbook ngẫu nhiên.',{'path':TEXT,'operations':TEXT},['path','operations']),
 schema('cad_com','AutoCAD COM: chọn DWG theo đường dẫn, operations JSON: inspect{limit}, entity{handle}, layer{name,color}, set_entity{handle,layer,color,text}, line{start:[x,y,z],end:[x,y,z],layer}, circle{center:[x,y,z],radius,layer}, lisp{code}, script{path}. LISP/.scr cần duyệt code; chờ marker hoàn tất rồi đọc lại bản vẽ và lưu. Backup trước ghi.',{'path':TEXT,'operations':TEXT},['path','operations']),
 schema('vba_project','VBA đã duyệt: compose xuất .bas từ code; export/import module; run macro có verify JSON. import_run gom nhập và chạy sau một lần duyệt source code. application=excel/word/autocad, path là đúng workbook/document/drawing. source là .bas/.cls/.frm hoặc .dvb trong thư mục cho phép. Excel verify={sheet,range,expected:ma trận}; Word verify={contains:text}; CAD verify={entity_count:số}. Không bật Trust access hay bỏ bảo mật macro. AutoCAD cần VBA Enabler.',
        {'application':{'type':'string','enum':['excel','word','autocad']},'path':TEXT,'operation':{'type':'string','enum':['compose','export','import','run','import_run']},'module':TEXT,'source':TEXT,'code':TEXT,'macro':TEXT,'verify':TEXT},['application','path','operation'])]

ALLOWED={'excel_com':{'read','write','formula','format','filter','chart','calculate','save'},
         'cad_com':{'inspect','entity','layer','set_entity','line','circle','lisp','script'}}


def canonical(value):
    if isinstance(value,(tuple,list)):return [canonical(v) for v in value]
    return scalar(value)


def check_identity(document,path):
    if Path(str(document.FullName)).resolve()!=Path(path).resolve():raise RuntimeError('Tài liệu COM không khớp đường dẫn đã cấp quyền.')


def find_document(app,kind,path):
    collection=app.Workbooks if kind=='excel' else app.Documents
    for index in range(1,int(collection.Count)+1):
        doc=collection.Item(index)
        if Path(str(doc.FullName)).resolve()==Path(path).resolve():return doc
    security=getattr(app,'AutomationSecurity',None)
    try:
        if kind in ('excel','word') and security is not None:app.AutomationSecurity=3
        return collection.Open(str(path))
    finally:
        if security is not None:app.AutomationSecurity=security


def cad_entity(entity):
    result={'handle':str(entity.Handle),'type':str(entity.ObjectName),'layer':str(entity.Layer),'color':int(entity.Color)}
    if hasattr(entity,'TextString'):result['text']=str(entity.TextString)
    for name in ('StartPoint','EndPoint','Center','Radius'):
        try:result[name]=canonical(getattr(entity,name))
        except Exception:pass
    return result


def run_cad_command(doc,code,timeout=60):
    marker=int(uuid.uuid4().hex[:7],16);old=doc.GetVariable('USERI1')
    doc.SendCommand(code.rstrip()+'\n(setvar "USERI1" '+str(marker)+')\n')
    deadline=time.monotonic()+timeout
    try:
        while time.monotonic()<deadline:
            try:
                if int(doc.GetVariable('USERI1'))==marker:return
            except Exception:pass
            time.sleep(.1)
        raise TimeoutError('Chưa xác minh lệnh AutoCAD đã hoàn tất.')
    finally:
        try:doc.SetVariable('USERI1',old)
        except Exception:pass


def execute(plan,app=None,on_status=None):
    args=plan['arguments'];name=plan['action'];kind=args.get('application') or ('excel' if name=='excel_com' else 'autocad')
    if app is None:
        import win32com.client
        prog={'excel':'Excel.Application','word':'Word.Application','autocad':'AutoCAD.Application'}[kind]
        try:app=win32com.client.GetActiveObject(prog)
        except Exception:app=win32com.client.Dispatch(prog)
    doc=find_document(app,kind,args['path']);check_identity(doc,args['path'])
    rows=plan.get('operations',[])
    writing=name=='vba_project' and args['operation'] in ('import','run','import_run') or any(o['action'] not in ('read','inspect','entity') for o in rows)
    backup=None
    if writing:
        backup=plan['backup']
        if kind=='excel':doc.SaveCopyAs(backup)
        elif kind=='autocad':
            doc.SaveAs(backup);doc.SaveAs(args['path'])
        else:
            doc.SaveAs2(backup,FileFormat=doc.SaveFormat);doc.SaveAs2(args['path'],FileFormat=doc.SaveFormat)
        if not Path(backup).is_file():raise RuntimeError('Chưa tạo được backup; hủy thao tác.')
    results=[];readbacks=[]
    for index,op in enumerate(rows,1):
        check_identity(doc,args['path']);action=op['action']
        if on_status:on_status(('Excel' if kind=='excel' else 'AutoCAD')+' · bước '+str(index)+'/'+str(len(rows))+' · '+{'read':'đọc','write':'ghi dữ liệu','formula':'ghi công thức','format':'định dạng','filter':'lọc','chart':'tạo biểu đồ','calculate':'tính lại','save':'lưu','inspect':'đọc bản vẽ','entity':'đọc đối tượng','set_entity':'sửa đối tượng','line':'tạo đoạn thẳng','circle':'tạo đường tròn','layer':'tạo layer','lisp':'chạy AutoLISP','script':'chạy script'}[action]+' '+str(op.get('range') or op.get('handle') or ''))
        if kind=='excel':
            sheet=doc.Worksheets.Item(op['sheet']) if 'sheet' in op else None
            target=sheet.Range(op['range']) if 'range' in op else None
            if action=='read':results.append({'sheet':op['sheet'],'range':op['range'],'values':canonical(target.Value2),'formulas':canonical(target.Formula)})
            elif action=='write':
                before=canonical(target.Value2);target.Value2=tuple(tuple(v for v in r) for r in op['values'])
                actual=canonical(target.Value2);expected=op['values']
                if len(expected)==1 and len(expected[0])==1:expected=expected[0][0]
                if actual!=expected:raise RuntimeError('Excel COM đọc lại giá trị không khớp.')
                readbacks.append({'sheet':op['sheet'],'range':op['range'],'before':before,'values':actual})
            elif action=='formula':
                target.Formula=op['value'];app.Calculate()
                actual_formula=canonical(target.Formula)
                if not (actual_formula==op['value'] or isinstance(actual_formula,list) and all(v==op['value'] for row in actual_formula for v in row)):raise RuntimeError('Công thức COM đọc lại không khớp.')
                readbacks.append({'sheet':op['sheet'],'range':op['range'],'formula':canonical(target.Formula),'values':canonical(target.Value2)})
            elif action=='format':
                for key,prop in [('bold','Bold'),('font','Name'),('size','Size'),('color','Color')]:
                    if key in op:
                        setattr(target.Font,prop,op[key])
                        if getattr(target.Font,prop)!=op[key]:raise RuntimeError('Định dạng đọc lại không khớp.')
                if 'number_format' in op:
                    target.NumberFormat=op['number_format']
                    if target.NumberFormat!=op['number_format']:raise RuntimeError('Định dạng số đọc lại không khớp.')
                readbacks.append({'range':op['range'],'number_format':canonical(target.NumberFormat)})
            elif action=='filter':
                target.AutoFilter(Field=int(op['field']),Criteria1=op['criteria'])
                if not sheet.AutoFilterMode:raise RuntimeError('Excel chưa xác nhận bộ lọc.')
                readbacks.append({'sheet':op['sheet'],'filter_active':True})
            elif action=='chart':
                anchor=sheet.Range(op.get('anchor','F2'));chart=sheet.ChartObjects().Add(anchor.Left,anchor.Top,400,250).Chart
                chart.SetSourceData(target);chart.ChartType=51
                if op.get('title'):chart.HasTitle=True;chart.ChartTitle.Text=op['title']
                readbacks.append({'sheet':op['sheet'],'charts':int(sheet.ChartObjects().Count)})
            elif action=='calculate':app.CalculateFull()
            elif action=='save':doc.Save()
        else:
            if action=='inspect':results.append({'path':str(doc.FullName),'entity_count':int(doc.ModelSpace.Count),'layers':[str(doc.Layers.Item(i).Name) for i in range(min(int(doc.Layers.Count),100))],'entities':[cad_entity(doc.ModelSpace.Item(i)) for i in range(min(int(doc.ModelSpace.Count),int(op.get('limit',30))))]})
            elif action=='entity':results.append(cad_entity(doc.HandleToObject(op['handle'])))
            elif action=='layer':
                try:layer=doc.Layers.Item(op['name'])
                except Exception:layer=doc.Layers.Add(op['name'])
                if 'color' in op:layer.Color=int(op['color'])
                readbacks.append({'layer':str(layer.Name),'color':int(layer.Color)})
            elif action=='set_entity':
                entity=doc.HandleToObject(op['handle'])
                for key,prop in [('layer','Layer'),('color','Color'),('text','TextString')]:
                    if key in op:
                        setattr(entity,prop,op[key])
                        if getattr(entity,prop)!=op[key]:raise RuntimeError('Thuộc tính CAD đọc lại không khớp.')
                readbacks.append(cad_entity(entity))
            elif action in ('line','circle'):
                import pythoncom
                from win32com.client import VARIANT
                point=lambda v:VARIANT(pythoncom.VT_ARRAY|pythoncom.VT_R8,v)
                entity=doc.ModelSpace.AddLine(point(op['start']),point(op['end'])) if action=='line' else doc.ModelSpace.AddCircle(point(op['center']),float(op['radius']))
                if 'layer' in op:entity.Layer=op['layer']
                readbacks.append(cad_entity(doc.HandleToObject(str(entity.Handle))))
            elif action=='lisp':run_cad_command(doc,op['code']);readbacks.append({'command_completed':True,'entity_count':int(doc.ModelSpace.Count)})
            elif action=='script':run_cad_command(doc,'_.-SCRIPT\n"'+op['path'].replace('\\','/')+'"');readbacks.append({'command_completed':True,'entity_count':int(doc.ModelSpace.Count)})
    if name=='vba_project':
        operation=args['operation']
        if on_status:on_status('VBA · '+operation+' · '+str(args.get('macro') or args.get('module') or ''))
        if operation=='import_run':
            if kind=='autocad':app.LoadDVB(args['source'])
            else:
                imported=doc.VBProject.VBComponents.Import(args['source'])
                if int(imported.CodeModule.CountOfLines)<1:raise RuntimeError('Module VBA chưa có code để chạy.')
            operation='run'
        if kind=='autocad':
            if operation=='import':app.LoadDVB(args['source'])
            elif operation=='run':app.RunMacro(args['macro'])
            else:raise ValueError('AutoCAD VBA hỗ trợ import DVB và chạy macro; cần VBA Enabler.')
        else:
            if operation=='export':doc.VBProject.VBComponents.Item(args['module']).Export(args['source'])
            elif operation=='import':
                imported=doc.VBProject.VBComponents.Import(args['source'])
                if not imported.Name or int(imported.CodeModule.CountOfLines)<1:raise RuntimeError('Chưa xác minh module VBA đã nhập.')
            elif operation=='run':
                macro="'"+str(doc.Name).replace("'","''")+"'!"+args['macro'] if kind=='excel' else args['macro']
                if kind=='word':doc.Activate();check_identity(app.ActiveDocument,args['path'])
                app.Run(macro)
        check_identity(doc,args['path'])
        if operation=='run':
            verify=plan['verify']
            if kind=='excel':
                app.Calculate();actual=canonical(doc.Worksheets.Item(verify['sheet']).Range(verify['range']).Value2)
                expected=verify['expected']
                if isinstance(expected,list) and len(expected)==1 and isinstance(expected[0],list) and len(expected[0])==1:expected=expected[0][0]
                if actual!=expected:raise RuntimeError('Macro chạy nhưng kết quả Excel không khớp.')
                readbacks.append({'values':actual,'macro_result_verified':True})
            elif kind=='word':
                if verify['contains'] not in str(doc.Content.Text):raise RuntimeError('Kết quả Word sau macro không khớp.')
                readbacks.append({'macro_result_verified':True})
            elif int(doc.ModelSpace.Count)!=int(verify['entity_count']):raise RuntimeError('Số đối tượng CAD sau macro không khớp.')
        if operation=='export' and not Path(args['source']).is_file():raise RuntimeError('Chưa xuất được module VBA.')
    if writing:check_identity(doc,args['path']);doc.Save()
    return {'ok':True,'path':args['path'],'backup':backup,'verified':True,'results':results,'readback':readbacks}


class ComTools:
    def __init__(self,files):self.files=files;self.on_status=None
    def prepare(self,name,args):
        p=self.files.path(args['path']);kind=args.get('application') or ('excel' if name=='excel_com' else 'autocad')
        suffixes={'excel':{'.xlsx','.xlsm','.xlsb','.xls'},'word':{'.docx','.docm'},'autocad':{'.dwg'}}
        if kind not in suffixes or p.suffix.lower() not in suffixes[kind]:raise ValueError('Chọn đúng định dạng tài liệu COM.')
        plan={'action':name,'arguments':dict(args,path=str(p)),'sha256':digest(p),'backup':str(self.files.backups/(uuid.uuid4().hex+p.suffix))}
        if name!='vba_project':
            plan['operations']=operations(args['operations'])
            for op in plan['operations']:
                if op.get('action') not in ALLOWED[name]:raise ValueError('Thao tác COM không hợp lệ.')
                if name=='excel_com' and 'range' in op:
                    from openpyxl.utils.cell import range_boundaries
                    left,top,right,bottom=range_boundaries(op['range'])
                    if None in (left,top,right,bottom) or min(left,top)<1 or right<left or bottom<top or (right-left+1)*(bottom-top+1)>10000:raise ValueError('Vùng COM tối đa 10000 ô.')
                    if op['action']=='write' and (len(op['values'])!=bottom-top+1 or any(len(r)!=right-left+1 for r in op['values'])):raise ValueError('Ma trận không khớp vùng ghi.')
                if op['action'] in ('line','circle'):
                    for key in ('start','end') if op['action']=='line' else ('center',):
                        v=op[key]
                        if not isinstance(v,list) or len(v)!=3 or any(not isinstance(x,(float,int)) or not __import__('math').isfinite(x) for x in v):raise ValueError('Điểm cần 3 số hữu hạn.')
                    if op['action']=='circle' and (not isinstance(op['radius'],(int,float)) or op['radius']<=0):raise ValueError('Bán kính cần dương.')
                if op['action']=='script':
                    source=self.files.path(op['path'])
                    if source.suffix.lower()!='.scr':raise ValueError('Script AutoCAD cần .scr.')
                    op['path']=str(source);op['code']=source.read_text(encoding='utf-8-sig');op['source_sha256']=digest(source)
                if op['action'] in ('lisp','script'):plan['requires_code_approval']=True
                if op['action']=='lisp' and (not isinstance(op.get('code'),str) or not 1<=len(op['code'])<=32000):raise ValueError('AutoLISP tối đa 32000 ký tự.')
        else:
            operation=args['operation']
            if operation not in ('compose','export','import','run','import_run'):raise ValueError('Thao tác VBA không hợp lệ.')
            if kind=='autocad' and operation in ('compose','export'):raise ValueError('AutoCAD cần dự án DVB đã biên dịch bằng VBA Enabler; dùng import/run hoặc import_run.')
            if operation in ('import','import_run') and ((kind=='excel' and p.suffix.lower() not in ('.xlsm','.xlsb','.xls')) or (kind=='word' and p.suffix.lower()!='.docm')):raise ValueError('Nhập VBA cần workbook/document hỗ trợ macro (.xlsm/.docm).')
            if operation in ('compose','export','import','import_run'):
                source=self.files.path(args['source'],exists=operation in ('import','import_run'))
                if source.suffix.lower() not in ({'.dvb'} if kind=='autocad' else {'.bas','.cls','.frm'}):raise ValueError('Định dạng module VBA không hợp lệ.')
                if operation not in ('import','import_run') and source.exists():raise FileExistsError('Module đích đã có; dùng tên mới.')
                plan['arguments']['source']=str(source)
                if operation in ('import','import_run'):plan['source_sha256']=digest(source)
            if operation in ('import','run','import_run'):plan['requires_code_approval']=True
            if operation in ('import','import_run') and kind!='autocad':plan['preview_code']=source.read_text(encoding='utf-8-sig',errors='replace')
            if operation in ('run','import_run'):
                if not re.fullmatch(r'[\w.]{1,150}',args.get('macro','')):raise ValueError('Tên macro không hợp lệ.')
                plan['verify']=json.loads(args.get('verify','{}'))
                required={'excel':{'sheet','range','expected'},'word':{'contains'},'autocad':{'entity_count'}}[kind]
                if not required<=plan['verify'].keys():raise ValueError('Chạy macro cần khai báo kết quả mong đợi để kiểm tra.')
        return plan

    def commit(self,plan):
        if os.name!='nt':raise RuntimeError('COM cần Windows và ứng dụng được cài.')
        p=self.files.path(plan['arguments']['path'])
        if digest(p)!=plan['sha256']:raise RuntimeError('File đã đổi sau preview.')
        if plan['action']=='vba_project' and plan['arguments']['operation']=='compose':
            source=self.files.path(plan['arguments']['source'],exists=False)
            with source.open('x',encoding='utf-8-sig') as output:output.write(plan['arguments']['code'])
            return {'ok':True,'path':str(source),'verified':source.read_text(encoding='utf-8-sig')==plan['arguments']['code']}
        if plan['action']=='vba_project' and plan['arguments']['operation']=='export' and self.files.path(plan['arguments']['source'],exists=False).exists():raise FileExistsError('Module đích xuất hiện sau preview; không ghi đè.')
        if plan.get('source_sha256') and digest(self.files.path(plan['arguments']['source']))!=plan['source_sha256']:raise RuntimeError('Module VBA đã đổi sau preview.')
        for op in plan.get('operations',[]):
            if op.get('source_sha256') and digest(self.files.path(op['path']))!=op['source_sha256']:raise RuntimeError('Script đã đổi sau preview.')
        python=Path(sys.executable).with_name('python.exe')
        self.files.audit('com_task_started',plan)
        result=run_child([str(python),'-B','-m','assistant.com_tasks'],json.dumps(plan).encode('utf-8'),cwd=Path(__file__).resolve().parents[1],timeout=120,on_status=self.on_status)
        if result['ok']:
            try:result=json.loads(result['stdout'].strip().splitlines()[-1])
            except (ValueError,IndexError):result={'ok':False,'uncertain':True,'error':'COM chưa trả bằng chứng kiểm tra.'}
        if not result.get('ok'):result.update(uncertain=True,backup=plan['backup'] if Path(plan['backup']).exists() else None)
        self.files.audit('com_task_result',result);return result


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');plan=json.loads(sys.stdin.buffer.read())
    try:
        import pythoncom
        pythoncom.CoInitialize()
        try:result=execute(plan,on_status=lambda text:print(json.dumps({'progress':text},ensure_ascii=False),flush=True))
        finally:pythoncom.CoUninitialize()
    except Exception as error:result={'ok':False,'error':str(error),'uncertain':True,'backup':plan.get('backup') if Path(plan.get('backup','')).is_file() else None}
    print(json.dumps(result,ensure_ascii=False,default=str),flush=True)

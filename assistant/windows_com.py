"""Typed COM adapters; no arbitrary COM paths, properties, or method execution."""
import json
import math
import re
from contextlib import contextmanager
from array import array

APPS={'excel':('Excel.Application','excel.exe'),
      'word':('Word.Application','winword.exe'),
      'powerpoint':('PowerPoint.Application','powerpnt.exe'),
      'autocad':('AutoCAD.Application','acad.exe')}


def table_rows(raw):
    rows=json.loads(raw) if isinstance(raw,str) else raw
    if not isinstance(rows,list) or not rows or len(rows)>1000:
        raise ValueError('Bảng cần 1–1000 hàng.')
    width=len(rows[0]) if isinstance(rows[0],list) else 0
    if not 1<=width<=100 or width*len(rows)>20000:
        raise ValueError('Bảng tối đa 100 cột và 20000 ô.')
    for row in rows:
        if not isinstance(row,list) or len(row)!=width:
            raise ValueError('Các hàng phải có cùng số cột.')
        for value in row:
            if value is not None and type(value) not in (str,int,float,bool):
                raise ValueError('Ô chỉ nhận chữ, số, boolean hoặc null.')
            if isinstance(value,str) and (len(value)>32767 or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',value)):
                raise ValueError('Nội dung ô không hợp lệ.')
            if type(value) in (int,float) and not math.isfinite(value):
                raise ValueError('Số trong ô phải hữu hạn.')
    return rows


class COMBackend:
    @contextmanager
    def connect(self,progid,create=False):
        import sys
        sys.coinit_flags=0  # Match WindowsBackend's worker-thread COM apartment.
        import comtypes
        from comtypes.client import GetActiveObject,CreateObject
        comtypes.CoInitializeEx(0)
        try:
            try:app=GetActiveObject(progid,dynamic=True)
            except (OSError,comtypes.COMError):
                if not create:raise RuntimeError('Ứng dụng chưa mở; mở ứng dụng trước hoặc chọn workbook/tài liệu mới.')
                app=CreateObject(progid,dynamic=True)
            yield app
        finally:comtypes.CoUninitialize()

    def process_path(self,app):
        import ctypes
        from ctypes import wintypes
        import psutil
        pid=ctypes.c_ulong()
        hwnd=int(app.HWND)
        if not hwnd:raise RuntimeError('Chưa xác minh được cửa sổ COM.')
        get_pid=ctypes.windll.user32.GetWindowThreadProcessId
        get_pid.argtypes=[wintypes.HWND,ctypes.POINTER(ctypes.c_ulong)]
        get_pid.restype=wintypes.DWORD
        get_pid(hwnd,ctypes.byref(pid))
        if not pid.value:raise RuntimeError('Chưa xác minh được tiến trình COM.')
        return psutil.Process(pid.value).exe()


class WindowsCOM:
    def __init__(self,windows,files,audit,backend=None):
        self.windows,self.files,self.audit=windows,files,audit
        self.backend=backend or COMBackend()

    def check(self,name):
        from .communication import require_method
        require_method(self.windows.check(),name)

    def prepare(self,name,args):
        from .communication import require_method
        require_method(self.windows.check(),name)
        kind=name.removesuffix('_com')
        if kind not in APPS:raise ValueError('Ứng dụng COM chưa hỗ trợ.')
        app=self.windows.allowed_path(args['app'])
        if app.name.lower()!=APPS[kind][1]:raise ValueError('Chọn đúng EXE từ windows_list_apps.')
        from .windows_apps import fingerprint
        plan={'action':name,'app':str(app),'sha256':fingerprint(app)}
        if kind=='excel':
            operation=args.get('operation','write')
            if operation not in ('read','write'):raise ValueError('operation phải là read hoặc write.')
            mode=args.get('mode','new')
            if mode not in ('new','active'):raise ValueError('mode phải là new hoặc active.')
            cell=args.get('cell','A1')
            if not isinstance(cell,str) or not re.fullmatch(r'[A-Z]{1,3}[1-9][0-9]{0,6}',cell):raise ValueError('Ô bắt đầu không hợp lệ.')
            column=0
            for letter in re.match(r'[A-Z]+',cell)[0]:column=column*26+ord(letter)-64
            row=int(re.search(r'[0-9]+',cell)[0])
            rows=table_rows(args.get('rows','[]')) if operation=='write' else None
            height=len(rows) if rows else args.get('height',20)
            width=len(rows[0]) if rows else args.get('width',10)
            if type(height) is not int or type(width) is not int or not 1<=height<=1000 or not 1<=width<=100 or height*width>20000 or row+height-1>1048576 or column+width-1>16384:
                raise ValueError('Vùng ô vượt giới hạn.')
            sheet=args.get('sheet','')
            if not isinstance(sheet,str) or len(sheet)>31 or re.search(r'[\\/?*\[\]:\x00]',sheet):raise ValueError('Tên sheet không hợp lệ.')
            plan.update(operation=operation,mode=mode,cell=cell,rows=rows,height=height,width=width,sheet=sheet)
        elif kind=='word':
            content=args['content']
            if not isinstance(content,str) or not content.strip() or len(content)>100000:raise ValueError('Nội dung Word cần 1–100000 ký tự.')
            plan['content']=content
        elif kind=='powerpoint':
            slides=json.loads(args['slides'])
            if not isinstance(slides,list) or not 1<=len(slides)<=100:raise ValueError('Cần 1–100 slide.')
            if any(not isinstance(s,dict) or set(s)!={'title','content'} or any(not isinstance(v,str) or len(v)>10000 for v in s.values()) for s in slides):raise ValueError('Mỗi slide cần title và content dạng chữ.')
            plan['slides']=slides
        else:
            points=json.loads(args['points'])
            if not isinstance(points,list) or not 2<=len(points)<=1000 or any(not isinstance(p,list) or len(p)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) for p in points):raise ValueError('Cần 2–1000 điểm [x,y,z] hữu hạn.')
            plan['points']=points
        path=args.get('path','').strip()
        if path:
            require_method(self.windows.check(),'file_write')
            if kind not in ('excel','word','powerpoint'):raise ValueError('Chưa hỗ trợ lưu CAD trong công cụ này.')
            if kind=='excel' and (plan['mode']!='new' or plan['operation']=='read'):raise ValueError('Chỉ lưu workbook mới; workbook đang mở để chưa lưu.')
            dest=self.files.path(path,exists=False)
            if dest.suffix.lower()!= {'excel':'.xlsx','word':'.docx','powerpoint':'.pptx'}[kind] or dest.exists() or not dest.parent.is_dir():raise ValueError('Đích cần đúng định dạng, chưa tồn tại và có thư mục cha.')
            plan['path']=str(dest)
        return plan

    def commit(self,plan):
        from .windows_apps import fingerprint
        kind=plan['action'].removesuffix('_com')
        from .communication import require_method
        require_method(self.windows.check(),plan['action'])
        app_path=self.windows.allowed_path(plan['app'])
        if fingerprint(app_path)!=plan['sha256']:raise PermissionError('Ứng dụng đã thay đổi; lập kế hoạch lại.')
        with self.backend.connect(APPS[kind][0],create=kind!='excel' or (plan['mode']=='new' and plan['operation']=='write')) as app:
            actual=self.windows.allowed_path(self.backend.process_path(app))
            if actual!=app_path:raise PermissionError('COM kết nối sang EXE khác với ứng dụng được chọn.')
            self.check(plan['action'])
            self.audit('com_started',{'action':plan['action'],'app':str(actual)})
            app.Visible=True
            result={'ok':True,'method':'COM','verified':False,'saved':False}
            if kind=='excel':
                workbook=app.Workbooks.Add() if plan['mode']=='new' and plan['operation']=='write' else app.ActiveWorkbook
                if workbook is None:raise RuntimeError('Excel chưa có workbook đang mở.')
                sheet=workbook.ActiveSheet
                if plan['sheet']:
                    try:sheet=workbook.Worksheets.Item(plan['sheet'])
                    except Exception:
                        if plan['operation']=='read':raise ValueError('Không tìm thấy sheet.')
                        sheet=workbook.Worksheets.Add();sheet.Name=plan['sheet']
                area=sheet.Range(plan['cell']).Resize(plan['height'],plan['width'])
                if plan['operation']=='write':
                    self.check(plan['action'])
                    # Literal text: prevent Excel treating generated text as formulas.
                    area.NumberFormat='@'
                    area.Value2=tuple(tuple(v for v in row) for row in plan['rows'])
                raw=area.Value2
                if plan['height']==plan['width']==1 and not isinstance(raw,(list,tuple)):values=[[raw]]
                else:values=[list(row) for row in raw]
                if plan['operation']=='write':
                    equal=lambda a,b:a==b or (a is None and b=='') or (b is None and a=='') or (type(a) in (int,float,bool) and str(a)==str(b))
                    if len(values)!=len(plan['rows']) or any(len(a)!=len(b) or any(not equal(x,y) for x,y in zip(a,b)) for a,b in zip(plan['rows'],values)):
                        raise RuntimeError('Đã ghi nhưng đọc lại không khớp; không tự ghi lại.')
                    area.Rows.Item(1).Font.Bold=True
                    area.Columns.AutoFit()
                result.update(verified=True,workbook=str(workbook.Name),sheet=str(sheet.Name),values=values,table_created=plan['operation']=='write')
                document=workbook
            elif kind=='word':
                document=app.Documents.Add()
                document.Content.Text=plan['content']
                if str(document.Content.Text).rstrip('\r\n')!=plan['content'].rstrip('\r\n'):raise RuntimeError('Nội dung Word đọc lại không khớp.')
                result.update(verified=True,document_created=True)
            elif kind=='powerpoint':
                document=app.Presentations.Add()
                for data in plan['slides']:
                    self.check(plan['action'])
                    slide=document.Slides.Add(document.Slides.Count+1,2)
                    slide.Shapes.Title.TextFrame.TextRange.Text=data['title']
                    slide.Shapes.Placeholders.Item(2).TextFrame.TextRange.Text=data['content']
                    if str(slide.Shapes.Title.TextFrame.TextRange.Text)!=data['title'] or str(slide.Shapes.Placeholders.Item(2).TextFrame.TextRange.Text)!=data['content']:
                        raise RuntimeError('Slide đọc lại không khớp.')
                result.update(verified=True,slides_created=int(document.Slides.Count))
            else:
                document=app.ActiveDocument
                if document is None:raise RuntimeError('Mở bản vẽ AutoCAD trước.')
                handles=[]
                for start,end in zip(plan['points'],plan['points'][1:]):
                    self.check(plan['action'])
                    line=document.ModelSpace.AddLine(array('d',start),array('d',end))
                    if tuple(line.StartPoint)!=tuple(start) or tuple(line.EndPoint)!=tuple(end):raise RuntimeError('Đường CAD đọc lại không khớp.')
                    handles.append(str(line.Handle))
                result.update(verified=True,entities_created=len(handles),handles=handles)
            if plan.get('path'):
                self.check(plan['action'])
                require_method(self.windows.check(),'file_write')
                dest=self.files.path(plan['path'],exists=False)
                if dest.exists():raise RuntimeError('File đích đã xuất hiện; không ghi đè.')
                if kind=='excel':document.SaveAs(str(dest),51)
                elif kind=='word':document.SaveAs2(str(dest),16)
                else:document.SaveAs(str(dest),24)
                if not dest.is_file():raise RuntimeError('Chưa xác minh được file đã lưu.')
                result.update(saved=True,path=str(dest))
            self.audit('com_success',result)
            return result

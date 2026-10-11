"""Explicit native macro/add-in operations; respect host Trust Center settings."""
import json
import re
import time
import uuid
from pathlib import Path
from .communication import require_method,MethodRequired
from .windows_com import APPS,COMBackend
from .windows_apps import fingerprint

TOOL_NAMES={'vba_execute','autolisp_execute','office_addin','windows_clipboard'}

class ClipboardBackend:
    def perform(self,operation,text=''):
        try:import win32clipboard,win32gui
        except ImportError:raise MethodRequired('Clipboard cần pywin32: cài requirements-windows-automation.txt bằng Python đang chạy Chat AI.')
        owner=win32gui.CreateWindowEx(0,'STATIC','ChatAI clipboard',0,0,0,0,0,-3,0,0,None)
        opened=False
        try:
            win32clipboard.OpenClipboard(owner);opened=True
            if operation=='write':
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT,text)
            value=win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT) if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT) else ''
            if not isinstance(value,str) or len(value)>65536:raise ValueError('Clipboard văn bản tối đa 65536 ký tự.')
            if operation=='write' and value!=text:raise RuntimeError('Clipboard đọc lại không khớp; không tự dán.')
            return {'ok':True,'operation':operation,'verified':True,'text':value,
                    'note':'Đã đọc/ghi clipboard. Dán bằng windows_input với CTRL+V vào cửa sổ đã chọn và quan sát mới.'}
        finally:
            if opened:win32clipboard.CloseClipboard()
            win32gui.DestroyWindow(owner)

class ApplicationMacros:
    def __init__(self,windows,files,audit,backend=None,clipboard_backend=None):
        self.windows,self.files,self.audit=windows,files,audit
        self.backend=backend or COMBackend()
        self.clipboard_backend=clipboard_backend or ClipboardBackend()

    def check(self,name):
        policy=self.windows.check();require_method(policy,name);require_method(policy,'excel_com')
        return policy

    def prepare(self,name,args):
        if name=='windows_clipboard':
            require_method(self.windows.check(),name)
            operation=args.get('operation','read');text=args.get('text','')
            if operation not in ('read','write') or not isinstance(text,str) or len(text)>65536 or '\x00' in text:raise ValueError('Clipboard cần read/write và văn bản tối đa 65536 ký tự, không chứa NUL.')
            return {'action':name,'operation':operation,'text':text}
        self.check(name)
        kind=args.get('application','autocad' if name=='autolisp_execute' else 'excel')
        if kind not in APPS:raise ValueError('application cần excel, word, powerpoint hoặc autocad.')
        app=self.windows.allowed_path(args['app'])
        if app.name.lower()!=APPS[kind][1]:raise ValueError('Chọn đúng EXE từ windows_list_apps.')
        plan={'action':name,'application':kind,'app':str(app),'sha256':fingerprint(app)}
        if name=='office_addin':
            if kind=='autocad':raise ValueError('Office COM add-in chỉ dùng Excel, Word, PowerPoint; CAD dùng plugin bridge hoặc AutoLISP.')
            operation=args.get('operation','list')
            if operation not in ('list','enable','disable'):raise ValueError('operation cần list, enable hoặc disable.')
            progid=args.get('progid','')
            if operation!='list' and (not isinstance(progid,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,150}',progid)):raise ValueError('Cần ProgID của add-in đã cài, lấy từ danh sách.')
            plan.update(operation=operation,progid=progid)
        elif name=='vba_execute':
            entry=args['entrypoint']
            if not isinstance(entry,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,80}',entry):raise ValueError('entrypoint cần tên Sub/Function trong module.')
            source=args.get('code','')
            if not isinstance(source,str) or len(source)>65536 or '\x00' in source:raise ValueError('Mã VBA tối đa 64 KiB, không chứa NUL.')
            module=args.get('module','')
            if source:
                module='ChatAI_'+uuid.uuid4().hex[:16]
            elif not isinstance(module,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,80}',module):raise ValueError('Cần code mới hoặc tên module VBA hiện có.')
            params=json.loads(args.get('parameters','[]'))
            if not isinstance(params,list) or len(params)>20 or any(type(p) not in (str,int,float,bool,type(None)) for p in params):raise ValueError('parameters cần JSON mảng tối đa 20 giá trị đơn.')
            json.dumps(params,allow_nan=False)
            plan.update(entrypoint=entry,code=source,module=module,parameters=params)
            if kind=='autocad':
                if source or params:raise ValueError('AutoCAD VBA dùng file DVB có sẵn, không nhận code mới hoặc parameters; mã mới dùng AutoLISP.')
                require_method(self.windows.check(),'file_read')
                project=self.files.path(args.get('project_path',''))
                if not project.is_file() or project.suffix.lower()!='.dvb':raise ValueError('AutoCAD VBA cần file .dvb trong thư mục được phép.')
                plan.update(project_path=str(project),project_sha256=fingerprint(project))
        elif name=='autolisp_execute':
            if kind!='autocad':raise ValueError('AutoLISP cần AutoCAD.')
            require_method(self.windows.check(),'file_write')
            code=args['code']
            if not isinstance(code,str) or not code.strip() or len(code)>65536 or '\x00' in code:raise ValueError('Mã AutoLISP cần 1–65536 ký tự.')
            timeout=args.get('timeout',30)
            if type(timeout) is not int or not 1<=timeout<=60:raise ValueError('Thời gian chờ AutoLISP từ 1 đến 60 giây.')
            ident=uuid.uuid4().hex
            script=self.files.path(str(self.files.roots[0]/('ChatAI-'+ident+'.lsp')),exists=False)
            output=self.files.path(str(self.files.roots[0]/('ChatAI-'+ident+'.result')),exists=False)
            plan.update(code=code,timeout=timeout,script=str(script),output=str(output),request_id=ident)
        else:raise ValueError('Công cụ macro/add-in chưa hỗ trợ.')
        return plan

    def commit(self,plan):
        if plan['action']=='windows_clipboard':
            require_method(self.windows.check(),plan['action'])
            result=self.clipboard_backend.perform(plan['operation'],plan['text'])
            self.audit('clipboard_completed',{'operation':plan['operation']});return result
        self.check(plan['action'])
        app_path=self.windows.allowed_path(plan['app'])
        if fingerprint(app_path)!=plan['sha256']:raise PermissionError('Ứng dụng đã thay đổi; lập kế hoạch lại.')
        with self.backend.connect(APPS[plan['application']][0],create=False) as app:
            if self.windows.allowed_path(self.backend.process_path(app))!=app_path:raise PermissionError('COM kết nối sang ứng dụng khác.')
            self.check(plan['action'])
            self.audit('native_task_started',{'tool':plan['action'],'application':plan['application']})
            if plan['action']=='office_addin':result=self.addin(app,plan)
            elif plan['action']=='autolisp_execute':result=self.lisp(app,plan)
            else:result=self.vba(app,plan)
            self.audit('native_task_completed',{'tool':plan['action'],'ok':result.get('ok',False)})
            return result

    def addin(self,app,plan):
        addons=app.COMAddIns
        if plan['operation']=='list':
            rows=[]
            for i in range(1,min(int(addons.Count),200)+1):
                self.check(plan['action']);item=addons.Item(i)
                rows.append({'progid':str(item.ProgId),'description':str(item.Description),'connected':bool(item.Connect)})
            return {'ok':True,'addins':rows,'truncated':int(addons.Count)>200}
        item=addons.Item(plan['progid']);wanted=plan['operation']=='enable'
        item.Connect=wanted
        actual=bool(item.Connect)
        if actual!=wanted:raise RuntimeError('Add-in chưa chuyển sang trạng thái yêu cầu; kiểm tra Office Disabled Items.')
        return {'ok':True,'progid':plan['progid'],'connected':actual,'verified':True}

    def vba(self,app,plan):
        kind=plan['application']
        if kind=='autocad':
            require_method(self.windows.check(),'file_read')
            project=self.files.path(plan['project_path'])
            if fingerprint(project)!=plan['project_sha256']:raise PermissionError('Dự án VBA đã thay đổi; lập kế hoạch lại.')
            try:app.LoadDVB(str(project))
            except Exception:raise MethodRequired('AutoCAD chưa nạp được DVB. Cần VBA Enabler đúng phiên bản và quyền nạp dự án VBA trong AutoCAD.')
            self.check(plan['action'])
            try:app.RunMacro(str(project)+'!'+plan['module']+'.'+plan['entrypoint'])
            except Exception:return {'ok':False,'macro_started':True,'uncertain':True,'error':'VBA AutoCAD báo lỗi; có thể đã thực hiện một phần, không tự chạy lại.'}
            return {'ok':True,'macro_completed':True,'saved':False,'note':'RunMacro đã trả về; đọc lại đối tượng bản vẽ để xác minh tác động.'}
        document=(app.ActiveWorkbook if kind=='excel' else app.ActiveDocument if kind in ('word','autocad') else app.ActivePresentation)
        if document is None:raise RuntimeError('Mở workbook/tài liệu/bản vẽ trước khi chạy VBA.')
        try:project=document.VBProject;components=project.VBComponents
        except Exception:
            raise MethodRequired('Ứng dụng chưa cho truy cập VBA Project. Trong Office bật Trust access to the VBA project object model tại Trust Center. AutoCAD cần cài VBA Enabler phù hợp phiên bản. Chat AI không tự thay đổi thiết lập này.')
        created=None
        if plan['code']:
            try:
                created=components.Add(1);created.Name=plan['module']
                created.CodeModule.AddFromString(plan['code'])
                read=str(created.CodeModule.Lines(1,created.CodeModule.CountOfLines))
                # VBE changes keyword/identifier case and whitespace. Preserve string
                # literals when verifying executable tokens, rather than rejecting normal formatting.
                def normal(text):
                    tokens=re.findall(r'"(?:[^"]|"")*"|\x27[^\r\n]*|[A-Za-z_][A-Za-z0-9_]*|\S',text)
                    return [token if token.startswith('"') else token.casefold() for token in tokens if not token.startswith("'")]
                if normal(read)!=normal(plan['code']):raise RuntimeError('Mã VBA đọc lại không khớp; chưa chạy.')
            except Exception:
                if created is not None:components.Remove(created)
                raise
        else:
            # Verify the requested module is in the active document, not an unrelated macro library.
            components.Item(plan['module'])
        try:self.check(plan['action'])
        except Exception:
            if created is not None:components.Remove(created)
            raise
        routine=plan['module']+'.'+plan['entrypoint']
        if kind in ('excel','powerpoint'):routine="'"+str(document.Name).replace("'","''")+"'!"+routine
        elif kind=='word':routine=str(project.Name)+'.'+routine
        try:value=app.Run(routine,*plan['parameters'])
        except Exception:
            # A macro may have modified the document before raising. Never retry automatically.
            return {'ok':False,'macro_started':True,'uncertain':True,'module':plan['module'],'error':'Macro báo lỗi hoặc bị ứng dụng chặn. Có thể đã thay đổi một phần; kiểm tra tài liệu, không tự chạy lại.'}
        try:json.dumps(value,allow_nan=False);result=value
        except (TypeError,ValueError):result=str(value)[:4000]
        return {'ok':True,'macro_completed':True,'module':plan['module'],'entrypoint':plan['entrypoint'],'result':result,'saved':False,
                'note':'Application.Run đã trả về; đọc lại ô/tài liệu để xác minh tác động. Chưa tự lưu tài liệu.'}

    def lisp(self,app,plan):
        require_method(self.windows.check(),'file_write')
        script=self.files.path(plan['script'],exists=False);output=self.files.path(plan['output'],exists=False)
        if script.exists() or output.exists():raise RuntimeError('File tác vụ đã tồn tại; không gửi lại AutoLISP.')
        quote=lambda value:json.dumps(str(value).replace('\\','/'),ensure_ascii=False)
        ident=plan['request_id'];variable='_chatai_'+ident
        source=('(vl-load-com)\n(setq '+variable+' (vl-catch-all-apply (function (lambda ()\n'+plan['code']+'\n)) nil))\n'+
                '(setq '+variable+'_f (open '+quote(output)+' "w"))\n'+
                '(if '+variable+'_f (progn (write-line "'+ident+'" '+variable+'_f)\n'+
                '(if (vl-catch-all-error-p '+variable+') (progn (write-line "ERROR" '+variable+'_f) (write-line (vl-catch-all-error-message '+variable+') '+variable+'_f))\n'+
                '(progn (write-line "OK" '+variable+'_f) (write-line (vl-princ-to-string '+variable+') '+variable+'_f)))\n'+
                '(write-line "DONE '+ident+'" '+variable+'_f) (close '+variable+'_f)))\n(princ)\n')
        with script.open('x',encoding='utf-8',newline='\n') as stream:stream.write(source)
        self.check(plan['action'])
        # AutoCAD SendCommand queues work. Only the correlated completion file confirms execution.
        app.ActiveDocument.SendCommand('(load '+quote(script)+')\n')
        deadline=time.monotonic()+plan['timeout']
        while time.monotonic()<deadline:
            self.check(plan['action'])
            if output.exists():
                checked=self.files.path(str(output))
                if checked.stat().st_size>1024*1024:raise RuntimeError('Kết quả AutoLISP quá lớn.')
                text=checked.read_text(encoding='utf-8',errors='replace');lines=text.splitlines()
                if text.endswith('\n') and len(lines)>=4 and lines[0]==ident and lines[1] in ('OK','ERROR') and lines[-1]=='DONE '+ident:
                    return {'ok':lines[1]=='OK','command_sent':True,'execution_completed':True,'result':'\n'.join(lines[2:-1])[:8000],
                            'script':str(script),'completion_file':str(output),'saved':False,
                            'note':'Đã nhận kết quả từ AutoCAD. Đọc lại đối tượng bản vẽ để xác minh tác động; không tự lưu.'}
            time.sleep(.1)
        return {'ok':False,'command_sent':True,'uncertain':True,'script':str(script),'error':'AutoCAD chưa gửi kết quả trong thời gian chờ. Có thể đang chờ lệnh/SECURELOAD hoặc đã thực hiện một phần; không tự gửi lại.'}

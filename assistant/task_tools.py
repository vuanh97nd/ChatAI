"""File, calculation and script tools for one explicitly authorized online task."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from .excel import digest
from .tools import schema,TEXT,DOCUMENT_READ_SCHEMA,EXTRA_TOOLS
from .calculator import CALCULATOR_SCHEMA,calculate
from .runner import Runner
from .windows_apps import _STOP,wait_automation

SCHEMAS=[CALCULATOR_SCHEMA,DOCUMENT_READ_SCHEMA]
SCHEMAS.extend(s for module,s in EXTRA_TOOLS if module=='files' or s['function']['name'] in ('python_run','run_command'))
SCHEMAS.append(schema('task_script','Chạy Python hoặc PowerShell trên máy trong nhiệm vụ đã cấp quyền. Xem code trước khi duyệt. Khai báo mọi file có thể sửa trong files để backup; cwd thuộc thư mục cho phép. Không phải sandbox Docker. In JSON kết quả và kiểm tra file đầu ra bằng tool đọc trước khi báo hoàn tất.',
    {'language':{'type':'string','enum':['python','powershell']},'code':TEXT,'path':TEXT,
     'files':{'type':'array','items':TEXT},'timeout':{'type':'integer','minimum':1,'maximum':120}},['language','code','path','files']))


def run_child(command, payload=None, cwd=None, timeout=120,on_status=None):
    """Poll the same stop signal as mouse/keyboard automation; capture bounded output."""
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    if _STOP.is_set():raise PermissionError('Đã dừng nhiệm vụ; chưa chạy process.')
    with tempfile.TemporaryDirectory(prefix='chatai-process-') as logs:
      out_path=Path(logs)/'stdout.log';err_path=Path(logs)/'stderr.log'
      with out_path.open('wb') as out,err_path.open('wb') as err:
        child=subprocess.Popen(command,stdin=subprocess.PIPE if payload is not None else subprocess.DEVNULL,
                               stdout=out,stderr=err,cwd=cwd,creationflags=flags)
        if payload is not None:
            child.stdin.write(payload);child.stdin.close()
        started=time.monotonic();reason=None;offset=0;pending=b''
        try:
            while child.poll() is None:
                wait_automation()
                if on_status:
                    with out_path.open('rb') as reader:
                        reader.seek(offset);chunk=reader.read(64000);offset+=len(chunk)
                    pending+=chunk
                    while b'\n' in pending:
                        line,pending=pending.split(b'\n',1)
                        try:event=json.loads(line)
                        except (ValueError,UnicodeError):continue
                        if isinstance(event,dict) and isinstance(event.get('progress'),str):on_status(event['progress'][:300])
                if _STOP.is_set():reason='Đã dừng nhiệm vụ.';break
                if time.monotonic()-started>timeout:reason='Tác vụ quá thời gian chờ.';break
                if out_path.stat().st_size+err_path.stat().st_size>2*1024**2:reason='Đầu ra vượt giới hạn.';break
                time.sleep(.05)
        finally:
            if child.poll() is None:
                if os.name=='nt':
                    subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,creationflags=flags,timeout=10)
                else:child.kill()
                child.wait(timeout=10)
      with out_path.open('rb') as out,err_path.open('rb') as err:
        result={'ok':reason is None and child.returncode==0,'exit_code':child.returncode,
                'stdout':out.read(2*1024**2 if payload is not None else 32000).decode('utf-8',errors='replace'),'stderr':err.read(8000).decode('utf-8',errors='replace')}
        if reason:result.update(error=reason,uncertain=True)
        return result


class TaskTools:
    def __init__(self,files):self.files=files;self.runner=Runner(files,files.audit);self.on_status=None

    def prepare(self,name,args):
        if name in ('file_write','file_edit','file_move','file_delete'):return self.files.prepare(name,args)
        if name in ('python_run','run_command'):return self.runner.prepare(name,args)
        if name=='calculate':return {'action':name,'arguments':dict(args)}
        if name in ('file_read','file_list','document_read'):
            p=self.files.path(args.get('path','.'))
            return {'action':name,'arguments':dict(args),'sha256':digest(p) if p.is_file() else None}
        if name!='task_script':raise ValueError('Công cụ nhiệm vụ không hợp lệ.')
        if args.get('language') not in ('python','powershell'):raise ValueError('Chọn Python hoặc PowerShell.')
        if not isinstance(args.get('code'),str) or not 1<=len(args['code'])<=32000:raise ValueError('Code tối đa 32000 ký tự.')
        root=self.files.path(args['path'])
        if not root.is_dir():raise ValueError('cwd phải là thư mục được phép.')
        paths=args.get('files',[])
        if not isinstance(paths,list) or len(paths)>30:raise ValueError('Khai báo tối đa 30 file.')
        records=[]
        for raw in paths:
            p=self.files.path(raw,exists=False)
            if p.exists() and (not p.is_file() or p.stat().st_size>100*1024**2):raise ValueError('File backup tối đa 100 MiB.')
            records.append({'path':str(p),'sha256':digest(p) if p.exists() else None})
        return {'action':name,'language':args['language'],'code':args['code'],'path':str(root),'files':records,
                'timeout':max(1,min(120,int(args.get('timeout',60)))),'requires_code_approval':True}

    def commit(self,plan):
        name=plan['action']
        if _STOP.is_set():raise PermissionError('Đã dừng nhiệm vụ.')
        if name in ('file_write','file_edit','file_move','file_delete'):
            result=self.files.commit(plan);p=Path(plan['path'])
            if name in ('file_write','file_edit'):
                if p.read_text(encoding='utf-8')!=plan['content']:raise RuntimeError('File đọc lại không khớp nội dung.')
            elif name=='file_move':
                if p.exists() or digest(Path(plan['destination']))!=plan['sha256']:raise RuntimeError('Chưa xác minh file di chuyển.')
            elif p.exists():raise RuntimeError('File vẫn tồn tại sau thao tác xóa.')
            return dict(result,verified=True)
        if name in ('python_run','run_command'):return self.runner.commit(plan)
        if name=='calculate':return {'ok':True,**calculate(**plan['arguments'])}
        if name in ('file_read','file_list','document_read'):
            args=plan['arguments'];p=self.files.path(args.get('path','.'))
            if plan.get('sha256') and digest(p)!=plan['sha256']:raise RuntimeError('File đã thay đổi; đọc lại.')
            if name=='document_read':
                from .document_reader import read_bytes
                content=read_bytes(p.read_bytes(),p.name)
                text=content.get('text','');start=int(args.get('start',0));limit=int(args.get('limit',20000))
                if start<0 or not 1<=limit<=40000:raise ValueError('Vị trí đọc không hợp lệ.')
                return {'ok':True,'path':str(p),'content':text[start:start+limit],'next_start':start+limit if start+limit<len(text) else None,
                        'coverage':content.get('coverage'),'missing_pages':content.get('missing_pages',[])}
            return {'ok':True,**getattr(self.files,name)(**args)}
        backups=[]
        for row in plan['files']:
            p=self.files.path(row['path'],exists=False)
            if (digest(p) if p.exists() else None)!=row['sha256']:raise RuntimeError('File đã đổi sau preview.')
            if p.exists():
                backup=self.files.backups/(uuid.uuid4().hex+p.suffix);shutil.copy2(p,backup);backups.append(str(backup))
        root=self.files.path(plan['path'])
        with tempfile.TemporaryDirectory(prefix='ai_task_',dir=root) as folder:
            suffix='.py' if plan['language']=='python' else '.ps1';script=Path(folder)/('task'+suffix)
            script.write_text(plan['code'],encoding='utf-8-sig' if suffix=='.ps1' else 'utf-8')
            python=Path(sys.executable).with_name('python.exe') if os.name=='nt' else Path(sys.executable)
            command=[str(python),'-u',str(script)] if suffix=='.py' else ['powershell.exe','-NoProfile','-NonInteractive','-File',str(script)]
            self.files.audit('task_script_started',plan)
            result=run_child(command,cwd=root,timeout=plan['timeout'],on_status=self.on_status);result['backups']=backups
            checked=[self.files.path(r['path'],exists=False) for r in plan['files']]
            result['files']=[{'path':str(p),'exists':p.exists(),'sha256':digest(p) if p.is_file() else None} for p in checked]
            self.files.audit('task_script_result',result)
            return result

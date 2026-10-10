"""Phone relay transport. HTTPS runs off the GUI thread; no remote shell execution."""
import json
import threading
import socket
import uuid
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from .accounts import request_account, credentials_path, _dpapi


def credential_path(session):
    import hashlib
    owner=hashlib.sha256((session['endpoint']+'\n'+session['username']).encode()).hexdigest()[:24]
    return credentials_path().parent/('remote-'+owner+'.dpapi')


def load_device(session):
    path=credential_path(session)
    return json.loads(_dpapi(path.read_bytes(),True).decode()) if path.exists() else None


def save_device(session,device):
    path=credential_path(session);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_bytes(_dpapi(json.dumps(device).encode()));temp.replace(path)


def register_device(session):
    device=load_device(session)
    body={**session,'desktop_id':device['desktop_id'] if device else str(uuid.uuid4()),'name':socket.gethostname()[:100]}
    if device:body['desktop_secret']=device['desktop_secret']
    result=request_account(session['endpoint'],'/api/remote/desktop/register',body)
    if not device:
        device={key:result[key] for key in ('desktop_id','desktop_secret')};save_device(session,device)
    return device


def desktop_api(session,device,action,**body):
    return request_account(session['endpoint'],'/api/remote/desktop/'+action,
                           {**body,**device,'username':session['username'],'key':session['key']},timeout=15)


class RemoteChannel(QThread):
    event=Signal(object)
    def __init__(self,session,device,parent=None,request=None):
        super().__init__(parent);self.session=dict(session);self.device=dict(device)
        self.request=request or desktop_api
        self.stop_event=threading.Event();self.lock=threading.Lock()
        self.ready=False;self.update=None;self.current=None;self.last_command=None;self.version=0
    def set_ready(self,ready):
        with self.lock:self.ready=ready
    def report(self,state,progress='',result='',ack=''):
        with self.lock:
            if self.current is None:return
            self.version+=1
            self.update={'id':self.current['id'],'lease_id':self.current['lease_id'],
                         'version':self.version,'state':state,'progress':progress[:2000],
                         'result':result[-48000:],'ack':ack or (self.update or {}).get('ack','')}
    def tick(self):
        with self.lock:
            if self.update:
                self.version+=1;self.update['version']=self.version
            packet={'ready':self.ready and self.current is None,'update':dict(self.update) if self.update else None}
        data=self.request(self.session,self.device,'tick',**packet)
        self.event.emit({'type':'pairs','pairs':data.get('pairs',[])})
        with self.lock:
            active=data.get('active')
            if self.current and packet['update'] and packet['update']['state'] in ('completed','failed','cancelled') and not (active and active['id']==self.current['id']):
                finished_id=self.current['id'];self.current=None;self.update=None;self.last_command=None
                self.event.emit({'type':'ack','id':finished_id})
            task=data.get('task')
            if task and self.current is None:
                self.current=task;self.version=0;self.ready=False
                self.event.emit({'type':'task','task':task})
            elif active and self.current is None:
                # A process died or a claim response was lost. Never replay its prompt.
                self.current=active;self.version=active.get('version',0);self.ready=False
                self.last_command=active.get('command')
                self.event.emit({'type':'orphan','task':active})
            if active and self.current and active['id']==self.current['id']:
                command=active.get('command')
                if command and command!=self.last_command:
                    self.last_command=command
                    self.event.emit({'type':'command','id':active['id'],'action':command,'text':active.get('reply','')})
                elif not command:self.last_command=None
        return data
    def run(self):
        delay=0
        while not self.stop_event.wait(delay):
            try:self.tick();delay=10 if self.current else 20
            except Exception:
                self.event.emit({'type':'connection','text':'Chưa kết nối được điện thoại; đang thử lại, không chạy lại tác vụ.'})
                delay=min(60,max(10,delay*2))
    def stop(self):
        self.stop_event.set()


def existing_plaxis_input():
    """Conservative gate before a new phone job; never replace an open model."""
    import psutil
    return any('plaxis' in str(p.info.get('name','')).lower() and 'input' in str(p.info.get('name','')).lower()
               for p in psutil.process_iter(['name']))

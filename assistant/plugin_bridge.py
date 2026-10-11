"""Small RPC SDK for application plugins: explicit registered functions, JSON only.

Embed BridgeServer in an application add-in or run a local adapter process.
No eval, import-by-name, shell dispatch, or pickle over the wire.
"""
import hmac
import json
import os
import re
import socketserver
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from .application_transport import LIMIT,json_bytes,decode_json

class BridgeServer:
    def __init__(self,handlers=None,token='',descriptions=None):
        self.handlers=dict(handlers or {})
        if 'capabilities' in self.handlers:raise ValueError('capabilities là chức năng SDK dành riêng.')
        if any(not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}',name) or not callable(fn) for name,fn in self.handlers.items()):raise ValueError('Handler plugin không hợp lệ.')
        self.token=token
        self.descriptions=descriptions or {}
        self.server=None

    def dispatch(self,request,authorization=''):
        ident=request.get('id') if isinstance(request,dict) else None
        if not isinstance(ident,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',ident):
            return {'id':None,'ok':False,'error':'Invalid request id.','uncertain':False}
        if self.token and not (hmac.compare_digest(str(request.get('token','')).encode('utf-8'),self.token.encode('utf-8')) or hmac.compare_digest(authorization.encode('utf-8'),('Bearer '+self.token).encode('utf-8'))):
            return {'id':ident,'ok':False,'error':'Authentication required.','uncertain':False}
        action=request.get('action')
        if action=='capabilities':
            result={'protocol':'chatai-json-rpc-v1','actions':[{'name':name,'description':self.descriptions.get(name,'')} for name in ['capabilities',*sorted(self.handlers)]]}
        elif not isinstance(action,str) or action not in self.handlers:
            return {'id':ident,'ok':False,'error':'Unknown action.','uncertain':False}
        else:
            try:result=self.handlers[action](request.get('arguments'))
            except Exception:
                return {'id':ident,'ok':False,'error':'Application handler failed. Effects may be partial.','uncertain':True}
        response={'id':ident,'ok':True,'result':result}
        try:json_bytes(response)
        except (ValueError,TypeError):return {'id':ident,'ok':False,'error':'Application result is not bounded JSON.','uncertain':True}
        return response

    def start_http(self,port=0):
        bridge=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                self.connection.settimeout(10)
                try:
                    count=int(self.headers.get('Content-Length','0'))
                    if not 0<count<=LIMIT:raise ValueError('Invalid length.')
                    request=decode_json(self.rfile.read(count))
                    response=bridge.dispatch(request,self.headers.get('Authorization',''))
                except (ValueError,UnicodeError,TimeoutError):
                    response={'id':None,'ok':False,'error':'Invalid request.','uncertain':False}
                raw=json_bytes(response)
                self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8')
                self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        self.server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
        self.server.daemon_threads=True
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        return self.server.server_address[1]

    def start_tcp(self,port=0):
        bridge=self
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.settimeout(10)
                try:
                    raw=self.rfile.readline(LIMIT+1)
                    if not raw.endswith(b'\n') or len(raw)>LIMIT:raise ValueError('Incomplete/oversized request.')
                    response=bridge.dispatch(decode_json(raw))
                except (ValueError,UnicodeError,TimeoutError):response={'id':None,'ok':False,'error':'Invalid request.','uncertain':False}
                self.wfile.write(json_bytes(response)+b'\n')
        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address=True
            daemon_threads=True
        self.server=Server(('127.0.0.1',port),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        return self.server.server_address[1]

    def start_websocket(self,port=0):
        from websockets.sync.server import serve
        bridge=self
        def handler(connection):
            try:
                raw=connection.recv(timeout=10)
                request=decode_json(raw.encode('utf-8') if isinstance(raw,str) else raw)
                response=bridge.dispatch(request,connection.request.headers.get('Authorization',''))
            except (ValueError,UnicodeError,TimeoutError):response={'id':None,'ok':False,'error':'Invalid request.','uncertain':False}
            connection.send(json_bytes(response).decode('utf-8'))
        self.server=serve(handler,'127.0.0.1',port,max_size=LIMIT,close_timeout=1)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        return self.server.socket.getsockname()[1]

    def serve_pipe(self,name='chatai-plugin'):
        if os.name!='nt':raise RuntimeError('Named pipe server cần Windows.')
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',name):raise ValueError('Tên pipe không hợp lệ.')
        import win32pipe,win32file,pywintypes
        # The same UTF-8 JSON-line protocol as TCP; no Python-specific wire format.
        while True:
            handle=win32pipe.CreateNamedPipe('\\\\.\\pipe\\'+name,win32pipe.PIPE_ACCESS_DUPLEX,
                      win32pipe.PIPE_TYPE_BYTE|win32pipe.PIPE_READMODE_BYTE|win32pipe.PIPE_WAIT,1,LIMIT+1,LIMIT+1,10000,None)
            try:
                try:win32pipe.ConnectNamedPipe(handle,None)
                except pywintypes.error as error:
                    if error.winerror!=535:raise # Client already connected.
                data=bytearray()
                while b'\n' not in data:
                    _,chunk=win32file.ReadFile(handle,min(8192,LIMIT+1-len(data)))
                    if not chunk:raise ValueError('Incomplete request.')
                    data.extend(chunk)
                    if len(data)>LIMIT:raise ValueError('Oversized request.')
                response=self.dispatch(decode_json(bytes(data).split(b'\n',1)[0]))
                win32file.WriteFile(handle,json_bytes(response)+b'\n')
                win32file.FlushFileBuffers(handle)
            except (ValueError,UnicodeError,pywintypes.error):pass
            finally:win32file.CloseHandle(handle)

    def close(self):
        if self.server is not None:
            self.server.shutdown()
            if hasattr(self.server,'server_close'):self.server.server_close()
            self.thread.join(timeout=2);self.server=None

def main():
    import argparse
    parser=argparse.ArgumentParser(description='SDK bridge mẫu: ping và capabilities; không điều khiển app nếu chưa đăng ký handler.')
    parser.add_argument('--transport',choices=['http','websocket','tcp','pipe'],default='http')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--pipe',default='chatai-plugin')
    parser.add_argument('--token-env',default='')
    args=parser.parse_args()
    token=os.environ.get(args.token_env,'') if args.token_env else ''
    if args.token_env and not token:parser.error('Biến môi trường token chưa được đặt.')
    bridge=BridgeServer({'ping':lambda args:{'pong':True}},token=token)
    if args.transport=='pipe':bridge.serve_pipe(args.pipe);return
    port=getattr(bridge,'start_'+args.transport)(args.port)
    print('Plugin bridge mẫu đang chạy trên loopback, cổng',port)
    try:threading.Event().wait()
    except KeyboardInterrupt:pass
    finally:bridge.close()

if __name__=='__main__':main()

"""Working adapter process. Run on Windows: python -m examples.office_cad_bridge.

The target apps and ChatAI's permissions must already be configured.
App-specific native plugins can instead embed assistant.plugin_bridge.BridgeServer.
"""
import argparse
import os
import threading
from assistant.config import load_config,ROOT
from assistant.windows_apps import WindowsApps
from assistant.files import FileTools
from assistant.windows_com import WindowsCOM
from assistant.application_macros import ApplicationMacros,TOOL_NAMES as MACRO_TOOLS
from assistant.plugin_bridge import BridgeServer

def execute(tool,args):
    cfg=load_config()
    audit=lambda event,data:None
    windows=WindowsApps(cfg,audit,policy_path=ROOT/'config.json')
    files=FileTools(cfg['roots'],ROOT/'data/backups',audit)
    adapter=ApplicationMacros(windows,files,audit) if tool in MACRO_TOOLS else WindowsCOM(windows,files,audit)
    return adapter.commit(adapter.prepare(tool,args))

def main():
    parser=argparse.ArgumentParser(description='Cầu nối thực tế Office/CAD, giữ quyền công cụ ChatAI.')
    parser.add_argument('--transport',choices=['http','websocket','tcp','pipe'],default='http')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--pipe',default='chatai-office-cad')
    parser.add_argument('--token-env',default='')
    args=parser.parse_args()
    token=os.environ.get(args.token_env,'') if args.token_env else ''
    if args.token_env and not token:parser.error('Chưa đặt biến môi trường token.')
    names=['excel_com','word_com','powerpoint_com','autocad_com',*sorted(MACRO_TOOLS)]
    handlers={name:(lambda args,name=name:execute(name,args)) for name in names}
    bridge=BridgeServer(handlers,token=token,descriptions={name:'COM adapter: '+name for name in handlers})
    if args.transport=='pipe':bridge.serve_pipe(args.pipe);return
    port=getattr(bridge,'start_'+args.transport)(args.port)
    print('Office/CAD bridge đang chạy, cổng',port)
    try:threading.Event().wait()
    except KeyboardInterrupt:pass
    finally:bridge.close()

if __name__=='__main__':main()

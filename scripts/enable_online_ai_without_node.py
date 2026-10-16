"""User-requested migration: retire local proxies and share existing tool grants."""
import ast
import json
import re
import sys
from datetime import datetime
from pathlib import Path


def patch_python(relative, source):
    ast.parse(source)
    if relative == 'assistant/custom_backup_api.py':
        anchor = "    local = parsed.hostname in ('localhost', '127.0.0.1', '::1')\n"
        marker = 'Local Node.js proxy has been disabled'
        if marker not in source:
            if source.count(anchor) != 1:raise ValueError('Unknown custom API version; no changes written.')
            source = source.replace(anchor, anchor +
                '    from .online_provider_policy import local_proxy\n'
                "    if local_proxy({'url':value}):raise ValueError('Local Node.js proxy has been disabled. Chọn DeepSeek, OpenRouter hoặc API từ xa.')\n")
    elif relative == 'assistant/local_openai.py':
        if '# Retired local Node proxy' not in source:
            tree = ast.parse(source)
            load = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='load_config')
            returns = [n for n in ast.walk(load) if isinstance(n,ast.Return) and isinstance(n.value,ast.Name) and n.value.id=='data']
            if len(returns)!=1:raise ValueError('Unknown local API config loader; nothing written.')
            lines=source.splitlines(keepends=True);index=returns[0].lineno-1
            indent=lines[index][:len(lines[index])-len(lines[index].lstrip())]
            lines[index:index]=[indent+'# Retired local Node proxy\n',indent+'from .online_provider_policy import local_proxy\n',indent+'if local_proxy(data):return None\n']
            source=''.join(lines)
    elif relative == 'assistant/online_automation.py':
        # All online models plan for the same external executor, with actual schemas.
        if "state['node_tool_executor']=bool(local_api)" in source:
            source=source.replace("state['node_tool_executor']=bool(local_api)","state['node_tool_executor']=True  # Shared external executor for all online providers")
            source=source.replace('            if local_api:\n                from .node_tool_bridge import planning_contract',
                                  '            if state[\'node_tool_executor\']:\n                from .node_tool_bridge import planning_contract')
    elif relative in ('desktop_ui.py','assistant/custom_api_window.py'):
        # Keep generic remote APIs; remove only local server start controls.
        source=source.replace('API tùy chỉnh / Node.js — nhập URL và kiểm tra','API tùy chỉnh từ xa — nhập URL và kiểm tra')
        source=source.replace("dialog.setWindowTitle('API tùy chỉnh / Node.js')","dialog.setWindowTitle('API tùy chỉnh từ xa')")
        lines=source.splitlines(keepends=True)
        for i in range(len(lines)-1,-1,-1):
            matches=re.findall(r"(\w+)\s*=\s*QPushButton\('Khởi động server Node.js'\)",lines[i])
            indent=lines[i][:len(lines[i])-len(lines[i].lstrip())]
            for variable in matches:
                addition=indent+variable+'.hide()  # Local Node proxy retired\n'
                if i+1>=len(lines) or lines[i+1]!=addition:lines.insert(i+1,addition)
        source=''.join(lines)
    ast.parse(source)
    return source


def main():
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root))
    from assistant.autonomy import grant_autonomy
    files=('assistant/custom_backup_api.py','assistant/local_openai.py',
           'assistant/online_automation.py','desktop_ui.py','assistant/custom_api_window.py')
    changes={}
    for relative in files:
        path=root/relative
        if not path.exists():continue
        source=path.read_text(encoding='utf-8-sig')
        result=patch_python(relative,source)
        if result!=source:changes[relative]=result
    config=root/'config.json'
    cfg=json.loads(config.read_text(encoding='utf-8-sig'))
    granted=grant_autonomy(cfg)
    # Preserve model selection, whitelisted roots, accounts and provider keys.
    if granted!=cfg:changes['config.json']=json.dumps(granted,ensure_ascii=False,indent=2)+'\n'
    policy=root/'assistant/online_provider_policy.py'
    ast.parse(policy.read_text(encoding='utf-8-sig'))
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for relative,result in changes.items():
        path=root/relative
        backup=root/'data'/'online-no-node-backups'/stamp/relative
        backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(path.read_bytes())
        path.write_text(result,encoding='utf-8')
    print('Local Node proxy disabled in AI routing. Remote AI providers share task-tool grants.')
    print('Preserved keys, login, model selection and whitelisted folders. No server process killed or files deleted.')
    print('Changed files:',len(changes),'Backup:',root/'data'/'online-no-node-backups'/stamp)
    print('Restart Chat AI and select the remote AI provider you want.')


if __name__=='__main__':main()

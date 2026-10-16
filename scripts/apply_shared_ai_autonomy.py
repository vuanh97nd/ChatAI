"""Apply shared task permission without replacing merged application files."""
import ast
import json
import sys
from pathlib import Path
from datetime import datetime


def patch(relative, source):
    ast.parse(source)
    if relative=='desktop_ui.py':
        marker='        cl.addWidget(self.task_autonomy_check)\n'
        addition='        from assistant.shared_autonomy import bind_checkbox\n        bind_checkbox(self)\n'
        if addition not in source:
            if source.count(marker)!=1:raise ValueError('Unknown checkbox layout; nothing written.')
            source=source.replace(marker,addition+marker)
    else:
        marker="        if state is not None and 'task_autonomy' in state:\n"
        addition=("        # Shared setting takes precedence over stale per-turn state, for every provider.\n"
                  "        if 'ai_tools_auto_execute' in self.cfg:\n"
                  "            if not self.cfg['ai_tools_auto_execute']:return False\n"
                  "            return self.windows.check().get('ai_tools_auto_execute') is True\n")
        if addition not in source:
            if source.count(marker)!=1:raise ValueError('Unknown auto-execution policy; nothing written.')
            source=source.replace(marker,addition+marker)
        old=r"            state['task_autonomy']=bool(self.cfg['task_autonomy']) or bool(state.get('task_autonomy') and re.fullmatch(r'\s*(?:ok|tiếp tục|đồng ý|thử lại)[.! ]*',prompt,re.I))"
        new="            state['task_autonomy']=bool(self.cfg.get('ai_tools_auto_execute',self.cfg['task_autonomy']))"
        if old in source:source=source.replace(old,new)
        elif new not in source:raise ValueError('Unknown task-start permission policy; nothing written.')
    ast.parse(source)
    return source


def main():
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
    ast.parse((root/'assistant/shared_autonomy.py').read_text(encoding='utf-8-sig'))
    changes={}
    for relative in ('desktop_ui.py','assistant/online_automation.py'):
        source=(root/relative).read_text(encoding='utf-8-sig')
        result=patch(relative,source)
        if source!=result:changes[relative]=result
    cfg=json.loads((root/'config.json').read_text(encoding='utf-8-sig'))
    from assistant.autonomy import grant_autonomy
    granted=grant_autonomy(cfg)
    if granted!=cfg:changes['config.json']=json.dumps(granted,ensure_ascii=False,indent=2)+'\n'
    backup=root/'data'/'shared-ai-autonomy-backups'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for relative,result in changes.items():
        path=root/relative;copy=backup/relative
        copy.parent.mkdir(parents=True,exist_ok=True);copy.write_bytes(path.read_bytes())
        path.write_text(result,encoding='utf-8')
    print('Shared task execution enabled for all AIs. Model choice, keys and allowed folders preserved.')
    print('Checkbox changes now persist globally. Backup:',backup)
    print('Restart Chat AI.')


if __name__=='__main__':main()

"""Resolve only 60d9921 conflicts, backing up all changes after a complete preflight."""
import ast
import re
import subprocess
from datetime import datetime
from pathlib import Path

REMOVED = {'backup_login_dialog', 'backup_provider_dialog', 'custom_backup_api_dialog'}
REMOVED_CALLBACKS = REMOVED | {'forget_backup'}

def removed_reference(node):
    return (isinstance(node, ast.Attribute) and node.attr in REMOVED_CALLBACKS or
            isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in REMOVED_CALLBACKS)


MARKERS = re.compile(r'^(?:<<<<<<<|=======|>>>>>>>|\|\|\|\|\|\|\|)', re.M)


def resolve_markers(source, keep_current=False):
    source = source.replace('\r\n', '\n')
    pattern = re.compile(r'^<<<<<<<[^\n]*\n(.*?)^=======\n(.*?)^>>>>>>> ([^\n]*)\n?', re.M | re.S)
    def choose(match):
        if not match.group(3).startswith('60d9921'):
            raise ValueError('Conflict is not from 60d9921. No file was changed.')
        if not keep_current:
            return match.group(2)
        ours = match.group(1)
        # Diff3 includes the ancestor after the current branch; it is not source code.
        return re.split(r'^\|\|\|\|\|\|\|[^\n]*\n', ours, maxsplit=1, flags=re.M)[0]
    source = pattern.sub(choose, source)
    if MARKERS.search(source):
        raise ValueError('Unexpected conflict markers. No file was changed.')
    return source


def integrate(source):
    source = resolve_markers(source, keep_current=True)
    tree = ast.parse(source)
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in REMOVED:
            ranges.append((min([node.lineno] + [d.lineno for d in node.decorator_list])-1, node.end_lineno))
        elif isinstance(node, ast.Expr) and any(removed_reference(child) for child in ast.walk(node)):
            ranges.append((node.lineno-1, node.end_lineno))
    lines = source.splitlines(True)
    excluded = {index for start, end in ranges for index in range(start, end)}
    result = ''.join(line for index, line in enumerate(lines) if index not in excluded)
    parsed = ast.parse(result)
    if any(removed_reference(node) for node in ast.walk(parsed)):
        raise ValueError('Unknown references to removed dialogs. No file was changed.')
    compile(result, 'desktop_ui.py', 'exec')
    return result


def repair(root):
    def git(*args):
        return subprocess.check_output(['git', *args],cwd=root).decode('utf-8').strip()
    allowed=set(git('diff-tree','--no-commit-id','--name-only','-r','60d9921').splitlines())
    unmerged=set(git('diff','--name-only','--diff-filter=U').splitlines())
    if unmerged-allowed:
        raise ValueError('Other commits have unresolved files; no files changed: '+', '.join(sorted(unmerged-allowed)))
    originals={};results={}
    for relative in sorted(allowed|{'app.py'}):
        path=root/relative
        if not path.is_file():
            if relative in unmerged:raise ValueError('Missing conflicted file: '+relative)
            continue
        original=path.read_bytes();source=original.decode('utf-8-sig')
        if relative=='desktop_ui.py':result=integrate(source)
        elif MARKERS.search(source):result=resolve_markers(source)
        else:result=source
        if relative.endswith('.py'):compile(result,relative,'exec')
        if result!=source:
            originals[relative]=original;results[relative]=result
    # Everything is validated before any working source or Git index is changed.
    backup=root/'data'/('primary-ai-conflict-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    for relative,original in originals.items():
        target=backup/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(original)
    for relative,result in results.items():
        (root/relative).write_text(result,encoding='utf-8')
    stage=sorted(set(results)|unmerged)
    if stage:subprocess.check_call(['git','add','--',*stage],cwd=root)
    print('Resolved primary AI conflicts; all affected Python files compile.')
    print('Changed:', ', '.join(sorted(results)) or 'none')
    if originals:print('Backup:',backup)
    remaining=git('diff','--name-only','--diff-filter=U')
    if remaining:
        raise RuntimeError('Other conflicts remain: '+remaining)
    cherry_path=Path(git('rev-parse','--git-path','CHERRY_PICK_HEAD'))
    if not cherry_path.is_absolute():cherry_path=root/cherry_path
    print('Next: git -c core.editor=true cherry-pick --continue' if cherry_path.exists() else 'Next: git status (no active cherry-pick detected).')


def main():
    repair(Path(__file__).resolve().parents[1])


if __name__ == '__main__':
    main()

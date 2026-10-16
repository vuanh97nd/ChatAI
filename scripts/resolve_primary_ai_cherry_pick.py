"""Resolve only desktop conflicts from 60d9921; retain local code and remove AI fallback UI."""
import ast
import re
import subprocess
from datetime import datetime
from pathlib import Path

REMOVED = {'backup_login_dialog', 'backup_provider_dialog', 'custom_backup_api_dialog'}
MARKERS = re.compile(r'^(?:<<<<<<<|=======|>>>>>>>|\|\|\|\|\|\|\|)', re.M)


def integrate(source):
    source = source.replace('\r\n', '\n')
    pattern = re.compile(r'^<<<<<<<[^\n]*\n(.*?)^=======\n(.*?)^>>>>>>> ([^\n]*)\n?', re.M | re.S)
    def choose(match):
        if not match.group(3).startswith('60d9921'):
            raise ValueError('Conflict is not from 60d9921. No file was changed.')
        ours = match.group(1)
        # Diff3 includes the ancestor after the current branch; it is not source code.
        return re.split(r'^\|\|\|\|\|\|\|[^\n]*\n', ours, maxsplit=1, flags=re.M)[0]
    source = pattern.sub(choose, source)
    if MARKERS.search(source):
        raise ValueError('Unexpected conflict markers. No file was changed.')
    tree = ast.parse(source)
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in REMOVED:
            ranges.append((min([node.lineno] + [d.lineno for d in node.decorator_list])-1, node.end_lineno))
        elif isinstance(node, ast.Expr) and any(isinstance(child, ast.Attribute) and child.attr in REMOVED for child in ast.walk(node)):
            ranges.append((node.lineno-1, node.end_lineno))
    lines = source.splitlines(True)
    excluded = {index for start, end in ranges for index in range(start, end)}
    result = ''.join(line for index, line in enumerate(lines) if index not in excluded)
    parsed = ast.parse(result)
    if any(isinstance(node, ast.Attribute) and node.attr in REMOVED for node in ast.walk(parsed)):
        raise ValueError('Unknown references to removed dialogs. No file was changed.')
    compile(result, 'desktop_ui.py', 'exec')
    return result


def main():
    root = Path(__file__).resolve().parents[1]
    path = root / 'desktop_ui.py'
    original = path.read_bytes()
    result = integrate(original.decode('utf-8-sig'))
    # Verify other application changes from the cherry-pick before marking this file resolved.
    for relative in ('app.py', 'assistant/cloud.py', 'assistant/failover.py', 'assistant/custom_backup_api.py'):
        candidate = root / relative
        if candidate.exists():
            compile(candidate.read_text(encoding='utf-8-sig'), relative, 'exec')
    backup = root / 'data' / ('primary-ai-conflict-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.txt')
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(original)
    path.write_text(result, encoding='utf-8')
    subprocess.check_call(['git', 'add', '--', 'desktop_ui.py'], cwd=root)
    print('Resolved primary AI UI conflict; Python syntax valid. Local unrelated code retained.')
    print('Backup:', backup)
    remaining = subprocess.check_output(['git', 'diff', '--name-only', '--diff-filter=U'], cwd=root).decode().strip()
    if remaining:
        print('Other conflicts remain; do not continue yet:', remaining)
    elif (root / '.git' / 'CHERRY_PICK_HEAD').exists():
        print('Next: git -c core.editor=true cherry-pick --continue')
    else:
        print('Next: git status (no active cherry-pick detected).')


if __name__ == '__main__':
    main()

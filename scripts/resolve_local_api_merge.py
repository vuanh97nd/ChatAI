"""Resolve the two independent local API dialog additions, retaining both."""
import ast
import re
import subprocess
from datetime import datetime
from pathlib import Path


def resolve(text):
    pattern = re.compile(r'^<<<<<<<[^\n]*\n(.*?)^=======\n(.*?)^>>>>>>>[^\n]*\n', re.M | re.S)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError('Expected exactly one conflict; no files changed.')
    left, right = matches[0].groups()
    names = lambda block: re.findall(r'^    def (\w+)\(', block, re.M)
    if names(left) != ['custom_backup_api_dialog'] or names(right) != ['custom_local_api_dialog']:
        raise ValueError('Different conflict than expected; no files changed.')
    result = text[:matches[0].start()] + left.rstrip() + '\n\n' + right + text[matches[0].end():]
    if re.search(r'^(?:<<<<<<<|=======|>>>>>>>|\|\|\|\|\|\|\|)', result, re.M):
        raise ValueError('Other conflict markers remain; no files changed.')
    ast.parse(result)
    for name in ('custom_backup_api_dialog', 'custom_local_api_dialog'):
        if len(re.findall(r'^    def ' + name + r'\(', result, re.M)) != 1:
            raise ValueError('Duplicate dialog method; no files changed.')
    return result


def main():
    root = Path(__file__).resolve().parents[1]
    subprocess.check_call(['git', 'rev-parse', '--verify', 'MERGE_HEAD'], cwd=root, stdout=subprocess.DEVNULL)
    unmerged = subprocess.check_output(['git', 'diff', '--name-only', '--diff-filter=U'], cwd=root).decode().splitlines()
    if unmerged != ['desktop_ui.py']:
        raise ValueError('Unexpected conflicted files; no files changed.')
    path = root / 'desktop_ui.py'
    text = resolve(path.read_text(encoding='utf-8-sig'))
    for relative in ('assistant/local_openai.py', 'assistant/support_ui.py'):
        ast.parse((root / relative).read_text(encoding='utf-8-sig'))
    backup = root / 'data' / ('desktop-api-merge-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.txt')
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(path.read_bytes())
    path.write_text(text, encoding='utf-8')
    subprocess.check_call(['git', 'add', 'desktop_ui.py'], cwd=root)
    print('Resolved. Both API dialogs retained; Python syntax valid.')
    print('Backup:', backup)
    print('Next: git -c core.editor=true merge --continue')


if __name__ == '__main__':
    main()

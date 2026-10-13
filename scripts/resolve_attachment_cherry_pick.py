"""Repair only the attachment routing cherry-pick, preserving current branch code."""
import ast
import difflib
import subprocess
from datetime import datetime
from pathlib import Path

TARGET = '5104dcc'
RELATIVE = 'assistant/online_automation.py'


def integrate(base, before, after):
    ast.parse(base)
    old, new = before.splitlines(keepends=True), after.splitlines(keepends=True)
    for tag, i, j, a, b in difflib.SequenceMatcher(None, old, new).get_opcodes():
        if tag == 'equal':
            continue
        addition = ''.join(new[a:b])
        removed = ''.join(old[i:j])
        if tag == 'replace':
            if removed in base and base.count(removed) == 1:
                base = base.replace(removed, addition, 1)
            elif addition not in base:
                raise ValueError('Cannot locate exact replacement; nothing written.')
            continue
        if tag != 'insert':
            raise ValueError('Unexpected patch; nothing written.')
        if addition in base:
            continue
        anchor = old[i]
        previous = old[i - 1] if i else ''
        if base.count(anchor) == 1:
            base = base.replace(anchor, addition + anchor, 1)
        elif previous and base.count(previous) == 1:
            base = base.replace(previous, previous + addition, 1)
        else:
            raise ValueError('Cannot locate insertion; nothing written.')
    ast.parse(base)
    return base


def main():
    root = Path(__file__).resolve().parents[1]
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root).decode('utf-8')
    pending_result = subprocess.run(['git', 'rev-parse', '--verify', 'CHERRY_PICK_HEAD'],
                                    cwd=root, capture_output=True, text=True)
    pending = pending_result.stdout.strip() if pending_result.returncode == 0 else ''
    if pending and not pending.startswith(TARGET):
        raise ValueError('Another cherry-pick is pending; nothing changed.')
    path = root / RELATIVE
    current = path.read_text(encoding='utf-8-sig')
    stages = git('ls-files', '--unmerged', '--', RELATIVE)
    if any(line.split('\t', 1)[0].endswith(' 2') for line in stages.splitlines()):
        base = git('show', ':2:' + RELATIVE)
    else:
        # Never discard an invalid, already committed file without diagnosis.
        markers = any(line.startswith(('<<<<<<< ', '=======', '>>>>>>> '))
                      for line in current.splitlines())
        if markers and not pending:
            raise ValueError('Conflict markers found without pending cherry-pick; nothing changed.')
        base = git('show', 'HEAD:' + RELATIVE) if markers else current
    text = integrate(base, git('show', TARGET + '^:' + RELATIVE),
                     git('show', TARGET + ':' + RELATIVE))
    backup = root / 'data' / ('attachment-conflict-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.txt')
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(path.read_bytes())
    path.write_text(text, encoding='utf-8')
    subprocess.check_call(['git', 'add', RELATIVE], cwd=root)
    print('Syntax valid. Attachment routing repaired; current branch code preserved.')
    print('Backup:', backup)
    if pending:
        subprocess.check_call(['git', '-c', 'core.editor=true', 'cherry-pick', '--continue'], cwd=root)
    else:
        print('No cherry-pick pending. Repair staged; restart Chat AI.')


if __name__ == '__main__':
    main()

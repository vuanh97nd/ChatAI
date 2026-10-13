"""Resolve the online_automation conflict of the GeoStudio tool cherry-pick.

Keep the current branch's file (Git stage 2), add only GeoStudio registration
and instructions, validate syntax before writing. Never continue Git automatically.
"""
import ast
from datetime import datetime
from pathlib import Path
import subprocess


def integrate(text):
    ast.parse(text)
    old = "('geoslope_inspect','geoslope_profile')"
    new = "('geoslope_inspect','geoslope_profile','geostudio_python')"
    if old in text:
        text = text.replace(old, new)
    if text.count(new) < 2:
        raise ValueError('Cannot locate both GeoStudio schema registration and component router.')
    old = "{'geoslope_inspect','geoslope_profile','geoslope_solve'}"
    text = text.replace(old, "{'geoslope_inspect','geoslope_profile','geoslope_solve','geostudio_python'}")
    marker = "            volatile=''"
    if 'GeoStudio Python bridge: geostudio_python' not in text:
        if text.count(marker) != 1:
            raise ValueError('Cannot locate the planning context; nothing written.')
        addition = (
            "\n            if _geoslope_workflow(state) and not research:\n"
            "                instruction+='\\nGeoStudio Python bridge: geostudio_python uses PyGeoStudio inventory and official gsi on new GSZ copies. ' \n"
            "                instruction+='No application_connections endpoint or File menu clicks needed. Use inspect before update_points/solve. ' \n"
            "                instruction+='Only update existing 1-based points with observed before values and sourced after coordinates in metres. ' \n"
            "                instruction+='After geometry edits verify materials, water, loads and slip search before solve; use the returned output file. ' \n"
            "                instruction+='No new regions or DXF import in this tool. Do not claim support for those operations.'\n"
        )
        text = text.replace(marker, marker + addition)
    ast.parse(text)
    return text


def main():
    root = Path(__file__).resolve().parents[1]
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root).decode('utf-8')
    pending = git('rev-parse', 'CHERRY_PICK_HEAD').strip()
    if not pending.startswith('3fa0c78'):
        raise ValueError('This resolver is only for cherry-pick 3fa0c78.')
    relative = 'assistant/online_automation.py'
    text = integrate(git('show', ':2:' + relative))
    path = root / relative
    # Preserve the conflicted working file for review, including local edits.
    backup = root / 'data' / ('online_automation-conflict-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.txt')
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(path.read_bytes())
    path.write_text(text, encoding='utf-8')
    subprocess.check_call(['git', 'add', relative], cwd=root)
    print('Resolved GeoStudio registration; preserved current branch code.')
    print('Backup:', backup)
    print('Next: git cherry-pick --continue')


if __name__ == '__main__':
    main()

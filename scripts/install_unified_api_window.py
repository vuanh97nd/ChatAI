"""Replace only the two conflicting dialog entry points; retain all other code."""
import ast
from pathlib import Path
from datetime import datetime


def patch(source):
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    methods = [node for cls in tree.body if isinstance(cls,ast.ClassDef)
               for node in cls.body if isinstance(node,ast.FunctionDef)
               and node.name in ('custom_backup_api_dialog','custom_local_api_dialog')]
    if not methods:
        raise ValueError('No API dialog entry points found; nothing written.')
    for method in sorted(methods,key=lambda node:node.lineno,reverse=True):
        replacement = (
            '    def '+method.name+'(self):\n'
            '        try:\n'
            '            from assistant.custom_api_window import open_window\n'
            '            open_window(self)\n'
            '        except Exception:\n'
            '            import traceback\n'
            "            details=traceback.format_exc()\n"
            "            print(details,flush=True)\n"
            '            try:\n'
            "                log=ROOT/'data'/'crash.log'\n"
            '                log.parent.mkdir(parents=True,exist_ok=True)\n'
            "                with log.open('a',encoding='utf-8') as stream:stream.write('\\nUnified API window failed\\n'+details)\n"
            '            except OSError:pass\n'
            "            QMessageBox.critical(QApplication.activeModalWidget() or self,'API tùy chỉnh','Không mở được hộp cấu hình. Chi tiết mới đã ghi vào data/crash.log.')\n")
        lines[method.lineno-1:method.end_lineno] = [replacement]
    result = ''.join(lines);ast.parse(result)
    return result


def main():
    root = Path(__file__).resolve().parents[1]
    module = root/'assistant'/'custom_api_window.py'
    ast.parse(module.read_text(encoding='utf-8-sig'))
    path = root/'desktop_ui.py'
    original = path.read_text(encoding='utf-8-sig')
    result = patch(original)
    if result == original:
        print('Already installed. Restart Chat AI.');return
    backup = root/'data'/('api-unified-before-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.txt')
    backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(path.read_bytes())
    path.write_text(result,encoding='utf-8')
    print('Unified API window installed; syntax valid. Backup:',backup)
    print('Restart Chat AI. Previous visibility scripts are no longer needed.')


if __name__ == '__main__':main()

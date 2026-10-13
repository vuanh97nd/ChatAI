"""Patch both API dialogs in a merged checkout without replacing other UI code."""
import ast
import re
from pathlib import Path
from datetime import datetime


def fix(text):
    ast.parse(text)
    old = '        custom_api.clicked.connect(lambda:(dialog.reject(),QTimer.singleShot(0,self.custom_backup_api_dialog)))\n'
    new = (
        '        def open_custom_api(checked=False):\n'
        '            try:\n'
        '                self.custom_backup_api_dialog()\n'
        '            except Exception:\n'
        '                import traceback\n'
        '                details=traceback.format_exc()\n'
        '                try:\n'
        "                    log=ROOT/'data'/'crash.log'\n"
        '                    log.parent.mkdir(parents=True,exist_ok=True)\n'
        "                    with log.open('a',encoding='utf-8') as stream:stream.write('\\nCustom API dialog open failed\\n'+details)\n"
        '                except OSError:pass\n'
        "                QMessageBox.warning(dialog,'API tùy chỉnh','Không mở được hộp cấu hình API. Chi tiết đã ghi trong data/crash.log. Hộp hiện tại được giữ nguyên.')\n"
        '        custom_api.clicked.connect(open_custom_api)\n'
    )
    text = text.replace(old, new)
    count = 0
    for name in ('custom_backup_api_dialog', 'custom_local_api_dialog'):
        pattern = re.compile(r'(^    def ' + name + r'\(self\):\n)(.*?)(?=^    def |\Z)', re.M | re.S)
        match = pattern.search(text)
        if not match:
            continue
        body = match[2]
        body = body.replace(
            "        if self.busy():\n"
            "            QMessageBox.information(self,'API tùy chỉnh','Ứng dụng đang thực hiện công việc. Dừng hoặc chờ xong rồi mở cấu hình API.');return\n", '')
        if '# API dialog visibility fix' in body:
            text = text[:match.start(2)] + body + text[match.end(2):]
            count += 1
            continue
        body = body.replace('        if self.busy() or not self.server_session:return\n',
            "        if not self.server_session:\n"
            "            QMessageBox.information(self,'API tùy chỉnh','Đăng nhập Chat AI trước khi cấu hình API cho tài khoản.');return\n")
        body = body.replace('dialog=QDialog(self);', 'dialog=QDialog(QApplication.activeModalWidget() or self);')
        body = body.replace('dialog.resize(600,0)', 'dialog.resize(680,480)')
        body = body.replace('dialog.resize(640,360)', 'dialog.resize(680,480)')
        # Open above the settings dialog instead of a disabled main window.
        body = body.replace('        dialog.exec()\n',
            '        dialog.setMinimumSize(620,420)\n'
            '        dialog.show();dialog.raise_();dialog.activateWindow()\n'
            '        dialog.exec()\n')
        text = text[:match.start(2)] + '        # API dialog visibility fix\n' + body + text[match.end(2):]
        count += 1
    if not count:
        raise ValueError('No custom API dialog found; nothing written.')
    ast.parse(text)
    return text


def main():
    root = Path(__file__).resolve().parents[1]
    path = root / 'desktop_ui.py'
    original = path.read_text(encoding='utf-8-sig')
    result = fix(original)
    if result == original:
        print('Already patched. Restart Chat AI.');return
    backup = root / 'data' / ('api-dialog-before-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.txt')
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(path.read_bytes())
    path.write_text(result, encoding='utf-8')
    print('Both available API dialogs patched; Python syntax valid.')
    print('Backup:', backup)
    print('Restart Chat AI. Git changes are not committed automatically.')


if __name__ == '__main__':
    main()

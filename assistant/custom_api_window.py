"""One retained Qt window for both custom API entry points."""
import os
import subprocess
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QApplication, QDialog, QFormLayout, QLabel,
    QLineEdit, QCheckBox, QPushButton, QDialogButtonBox, QMessageBox)


class ChatProbe(QThread):
    result = Signal(str)

    def __init__(self, profile, parent):
        super().__init__(parent)
        self.profile = profile

    def run(self):
        from .custom_backup_api import chat
        try:
            value = chat(self.profile, [{'role':'user','content':'Chỉ trả lời OK.'}],
                         {'num_predict':64,'temperature':0}, 30)
            self.result.emit('API trả lời: ' + value['answer'][:300])
        except Exception as error:
            self.result.emit('Chưa thành công: ' + str(error).replace(self.profile['api_key'], '[ẨN]'))


class ApiDialog(QDialog):
    def reject(self):
        probe = getattr(self, '_probe', None)
        if probe is not None and probe.isRunning():
            return
        super().reject()

    def closeEvent(self, event):
        probe = getattr(self, '_probe', None)
        if probe is not None and probe.isRunning():
            event.ignore();return
        super().closeEvent(event)


def open_window(owner):
    existing = getattr(owner, '_unified_custom_api_window', None)
    if existing is not None:
        try:
            existing.showNormal();existing.raise_();existing.activateWindow()
            return existing
        except RuntimeError:
            owner._unified_custom_api_window = None
    from .custom_backup_api import load, save, validate
    session = getattr(owner, 'server_session', None)
    primary = {k:session[k] for k in ('endpoint','username')} if session else None
    saved = load(primary) if primary else None
    legacy = None
    try:
        from . import local_openai
        legacy = local_openai
        old = legacy.load_config()
        if not saved and old:
            saved = {'url':old.get('url',''), 'api_key':old.get('key',''),
                     'model':old.get('model','auto'), 'enabled':old.get('use_as_fallback',False),
                     'use_direct':old.get('use_directly',False)}
    except ImportError:
        pass
    saved = saved or {}
    parent = QApplication.activeModalWidget() or owner
    dialog = ApiDialog(parent)
    dialog.setWindowTitle('API tùy chỉnh / Node.js')
    dialog.setMinimumSize(620, 420)
    dialog.resize(700, 480)
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    owner._unified_custom_api_window = dialog
    form = QFormLayout(dialog)
    note = QLabel('Nhập khóa server Node.js, không nhập accessToken ChatGPT. Khóa được lưu theo tài khoản Windows.')
    note.setWordWrap(True);form.addRow(note)
    url = QLineEdit(saved.get('url') or 'http://127.0.0.1:3040')
    key = QLineEdit();key.setEchoMode(QLineEdit.EchoMode.Password)
    key.setPlaceholderText('Để trống giữ khóa đã lưu' if saved else 'Nhập khóa server')
    model = QLineEdit(saved.get('model') or 'auto')
    fallback = QCheckBox('Dùng làm API dự phòng');fallback.setChecked(saved.get('enabled',False))
    direct = QCheckBox('Dùng API này ngay cho chat và thao tác AI');direct.setChecked(saved.get('use_direct',False))
    status = QLabel('Chưa kiểm tra chat.');status.setWordWrap(True)
    form.addRow('URL API:',url);form.addRow('Khóa server:',key);form.addRow('Model:',model)
    form.addRow(fallback);form.addRow(direct);form.addRow(status)
    start = QPushButton('Khởi động server Node.js')
    test = QPushButton('Kiểm tra chat');store = QPushButton('Lưu cấu hình')
    for button in (start,test,store):form.addRow(button)
    close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close.rejected.connect(dialog.reject);form.addRow(close)
    def profile():
        entered = key.text().strip()
        if not entered and url.text().strip().rstrip('/') != str(saved.get('url','')).rstrip('/'):
            raise ValueError('URL đã đổi hoặc chưa có khóa: nhập khóa của server này.')
        return validate({'url':url.text(),'api_key':entered or saved.get('api_key',''),
                         'model':model.text(),'enabled':fallback.isChecked(),'use_direct':direct.isChecked()})
    def persist():
        nonlocal saved
        try:
            value = profile()
            if not primary:
                raise ValueError('Đăng nhập Chat AI trước khi lưu cấu hình cho tài khoản.')
            save(primary,value)
            if legacy:
                legacy.save_config(value['url'],value['api_key'],value['model'],value['enabled'],value['use_direct'])
            saved = value;key.clear();key.setPlaceholderText('Để trống giữ khóa đã lưu')
            status.setText('Đã lưu cấu hình API cho các luồng chat và thao tác AI.')
        except Exception as error:
            status.setText(str(error).replace(key.text(), '[ẨN]') if key.text() else str(error))
    def check():
        try:
            value = profile()
        except Exception as error:
            status.setText(str(error));return
        test.setEnabled(False);status.setText('Đang kiểm tra chat…')
        probe = ChatProbe(value,dialog)
        dialog._probe = probe
        # Keep the window and thread alive until the request finishes.
        close.setEnabled(False)
        probe.result.connect(status.setText)
        probe.finished.connect(lambda:(test.setEnabled(True),close.setEnabled(True)))
        probe.start()
    def launch():
        local = os.environ.get('LOCALAPPDATA')
        launcher = Path(local)/'ChatAI'/'NodeServer'/'start-local.ps1' if local else None
        if os.name != 'nt' or launcher is None or not launcher.is_file():
            status.setText('Chưa có server Node.js đã cài trên Windows. Chạy setup-local-node-server.ps1 -Start.');return
        try:
            import socket
            try:
                with socket.create_connection(('127.0.0.1',3040),timeout=0.3):
                    status.setText('Cổng 3040 đã có dịch vụ chạy. Bấm Kiểm tra chat.');return
            except OSError:pass
            subprocess.Popen(['powershell.exe','-NoProfile','-NoExit','-ExecutionPolicy','Bypass','-File',str(launcher)],
                             cwd=str(launcher.parent),creationflags=subprocess.CREATE_NEW_CONSOLE)
            status.setText('Đã mở cửa sổ server. Giữ cửa sổ đó mở, rồi kiểm tra chat.')
        except OSError:
            status.setText('Không khởi động được PowerShell.')
    def clear_reference(result):
        if owner._unified_custom_api_window is dialog:
            owner._unified_custom_api_window = None
    dialog.finished.connect(clear_reference)
    test.clicked.connect(check);store.clicked.connect(persist);start.clicked.connect(launch)
    dialog.open();dialog.raise_();dialog.activateWindow()
    return dialog

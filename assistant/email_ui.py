"""Admin email configuration; secrets remain in the encrypted Worker store."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QWidget,QVBoxLayout,QFormLayout,QLabel,
    QLineEdit,QCheckBox,QPushButton)
from .billing_ui import BillingRequest


class EmailSettingsDialog(QDialog):
    def __init__(self,session,parent=None):
        super().__init__(parent);self.session=dict(session);self.worker=None
        self.setWindowTitle('Cấu hình email · Admin');self.resize(600,450)
        layout=QVBoxLayout(self);self.panel=QWidget();form=QFormLayout(self.panel);layout.addWidget(self.panel)
        note=QLabel('Dùng Resend để gửi xác minh email và đặt lại mật khẩu.\nTên miền gửi phải được xác minh trong Resend; API key được mã hóa trên server.');note.setWordWrap(True);form.addRow(note)
        self.enabled=QCheckBox('Bật email xác minh và quên mật khẩu');form.addRow(self.enabled)
        self.name=QLineEdit('ChatAI');self.sender=QLineEdit();self.sender.setPlaceholderText('noreply@tenmiencuaban.vn')
        self.secret=QLineEdit();self.secret.setEchoMode(QLineEdit.EchoMode.Password)
        for label,field in [('Tên người gửi',self.name),('Email người gửi',self.sender),('API key Resend',self.secret)]:form.addRow(label,field)
        save=QPushButton('Lưu cấu hình email');save.clicked.connect(self.save);form.addRow(save)
        self.recipient=QLineEdit();self.recipient.setPlaceholderText('Email nhận thử');form.addRow('Người nhận thử',self.recipient)
        test=QPushButton('Gửi email thử với cấu hình đã lưu');test.clicked.connect(lambda:self.send('/api/admin/email/test',{'to':self.recipient.text().strip()}));form.addRow(test)
        self.status=QLabel('Đang tải cấu hình…');self.status.setTextFormat(Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status)
        close=QPushButton('Đóng');close.clicked.connect(self.close);layout.addWidget(close)
        self.send('/api/admin/email/config/get')

    def send(self,path,body=None):
        if self.worker is not None:return False
        self.panel.setEnabled(False);self.status.setText('Đang xử lý…')
        self.worker=BillingRequest(self.session,path,body or {},self)
        self.worker.completed.connect(self.received);self.worker.failed.connect(self.status.setText)
        self.worker.finished.connect(self.request_finished);self.worker.start();return True

    def save(self):
        if self.send('/api/admin/email/config/save',{'config':{'enabled':self.enabled.isChecked(),'from':self.sender.text().strip(),'name':self.name.text().strip(),'secret':self.secret.text().strip()}}):self.secret.clear()

    def received(self,path,result):
        if 'config' in result:
            c=result['config'];self.enabled.setChecked(c['enabled']);self.sender.setText(c['from']);self.name.setText(c['name'])
            self.secret.setPlaceholderText('Đã lưu khóa · để trống giữ nguyên' if c['secret_configured'] else 'Nhập API key Resend')
        self.status.setText(result.get('message','Đã tải cấu hình.'))

    def request_finished(self):
        self.panel.setEnabled(True)
        if self.worker:self.worker.deleteLater();self.worker=None

    def reject(self):
        if self.worker is not None:
            self.status.setText('Đợi yêu cầu hoàn tất trước khi đóng.');return
        self.session.clear();super().reject()

    def closeEvent(self,event):
        if self.worker is not None:self.status.setText('Đợi yêu cầu hoàn tất trước khi đóng.');event.ignore();return
        self.session.clear();event.accept()

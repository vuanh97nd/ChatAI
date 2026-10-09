"""Account notifications stored on the server."""
import uuid
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QListWidget,QLineEdit,QTextEdit,QPushButton
from .billing_ui import BillingRequest


class NotificationDialog(QDialog):
    def __init__(self,session,parent=None):
        super().__init__(parent);self.session=dict(session);self.worker=None;self.attempt=None
        self.setWindowTitle('Thông báo');self.resize(650,550)
        layout=QVBoxLayout(self);self.count=QLabel();layout.addWidget(self.count)
        self.items=QListWidget();layout.addWidget(self.items)
        self.detail=QTextEdit();self.detail.setReadOnly(True);layout.addWidget(self.detail)
        self.items.currentItemChanged.connect(self.select)
        if session.get('is_system') or session.get('username','').lower()=='admin':
            layout.addWidget(QLabel('Gửi thông báo · để trống người nhận để gửi tất cả'))
            self.target=QLineEdit();self.target.setPlaceholderText('Tên đăng nhập người nhận');layout.addWidget(self.target)
            self.title=QLineEdit();self.title.setPlaceholderText('Tiêu đề');layout.addWidget(self.title)
            self.text=QTextEdit();self.text.setPlaceholderText('Nội dung thông báo');layout.addWidget(self.text)
            send=QPushButton('Gửi thông báo');send.clicked.connect(self.publish);layout.addWidget(send)
        self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);layout.addWidget(self.status)
        refresh=QPushButton('Làm mới');refresh.clicked.connect(self.refresh);layout.addWidget(refresh)
        self.refresh()

    def request(self,path,body=None):
        if self.worker:return False
        self.worker=BillingRequest(self.session,path,body or {},self)
        self.worker.completed.connect(self.received);self.worker.failed.connect(self.status.setText)
        self.worker.finished.connect(self.done_request);self.worker.start();return True

    def refresh(self):self.request('/api/notifications/list')

    def select(self,item,previous):
        if not item:return
        data=item.data(Qt.UserRole);self.detail.setPlainText(data['title']+'\n\n'+data['text'])
        if not data.get('read_at'):
            if self.request('/api/notifications/read',{'id':data['id']}):self.reload_next=True

    def publish(self):
        body={'title':self.title.text().strip(),'text':self.text.toPlainText().strip(),'target':self.target.text().strip() or '*'}
        signature=(body['title'],body['text'],body['target'])
        if not self.attempt or self.attempt[0]!=signature:self.attempt=(signature,str(uuid.uuid4()))
        self.request('/api/admin/notifications/send',{**body,'id':self.attempt[1]})

    def received(self,path,result):
        self.status.setText(result.get('message',''))
        if 'notifications' in result:
            self.count.setText(f"Chưa đọc: {result['unread']}")
            self.items.blockSignals(True);self.items.clear()
            from PySide6.QtWidgets import QListWidgetItem
            for data in result['notifications']:
                item=QListWidgetItem(('● ' if not data.get('read_at') else '')+data['title']);item.setData(Qt.UserRole,data);self.items.addItem(item)
            self.items.blockSignals(False)
        if path.endswith('/send'):self.reload_next=True

    def done_request(self):
        self.worker.deleteLater();self.worker=None
        if getattr(self,'reload_next',False):self.reload_next=False;self.refresh()

    def reject(self):
        if self.worker is not None:
            self.status.setText('Đợi yêu cầu hoàn tất trước khi đóng.');return
        self.session.clear();super().reject()

    def closeEvent(self,event):
        if self.worker:event.ignore();self.status.setText('Đợi yêu cầu hoàn tất trước khi đóng.');return
        self.session.clear();event.accept()

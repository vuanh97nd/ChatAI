"""Admin review of the shared lesson cache, with server-authorized withdrawal."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QListWidget,QListWidgetItem,QTextEdit,QCheckBox
from .billing_ui import BillingRequest
from .procedure_memory import ProcedureMemory
import json


class TrainingDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.session=dict(window.server_session);self.worker=None;self.offset=0
        self.setWindowTitle('Bộ nhớ đào tạo AI · Admin');self.resize(760,650)
        layout=QVBoxLayout(self)
        note=QLabel('Bật đào tạo trước khi thực hiện bài mẫu. Bài học mới từ công cụ sẽ được chia sẻ sau khi lọc thông tin riêng.\nKho không giới hạn tổng số bản ghi; danh sách bên dưới hiển thị 50 bản ghi mỗi trang.');note.setWordWrap(True);layout.addWidget(note)
        self.mode=QCheckBox('Đào tạo AI · chia sẻ bài học mới');self.mode.setChecked(window.cfg.get('procedure_training_enabled',False));self.mode.toggled.connect(window.set_training_mode);layout.addWidget(self.mode)
        self.count=QLabel();layout.addWidget(self.count)
        self.items=QListWidget();self.items.currentItemChanged.connect(self.selected);layout.addWidget(self.items)
        self.detail=QTextEdit();self.detail.setReadOnly(True);layout.addWidget(self.detail)
        row=QHBoxLayout()
        for title,callback in [('Trang trước',lambda:self.page(-50)),('Trang sau',lambda:self.page(50)),('Làm mới',self.refresh),('Thu hồi bài học đã chọn',self.withdraw)]:
            button=QPushButton(title);button.clicked.connect(callback);row.addWidget(button)
        layout.addLayout(row);self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);layout.addWidget(self.status)
        self.load()

    def page(self,delta):self.offset=max(0,self.offset+delta);self.load()

    def refresh(self):self.window.sync_procedures();self.load();self.status.setText('Đã yêu cầu đồng bộ nền. Khi hoàn tất, bấm Làm mới để xem bản ghi mới.')

    def load(self):
        memory=ProcedureMemory(self.window.store);owner=memory.shared_owner(self.session['username'])
        with self.window.store.connection() as db:
            total=db.execute('SELECT COUNT(*) FROM procedure_memory WHERE owner=?',(owner,)).fetchone()[0]
            rows=db.execute('SELECT data FROM procedure_memory WHERE owner=? ORDER BY updated DESC,id LIMIT 50 OFFSET ?',(owner,self.offset)).fetchall()
        self.count.setText(f'Kho chung trên máy: {total} bản ghi · trang {self.offset//50+1}')
        self.items.clear()
        for row in rows:
            record=json.loads(row[0]);item=QListWidgetItem(record['tool']+' · '+record['outcome']+' · '+record.get('level','command'))
            item.setData(Qt.UserRole,record);self.items.addItem(item)

    def selected(self,item,previous):
        if item:self.detail.setPlainText(json.dumps(item.data(Qt.UserRole),ensure_ascii=False,indent=2))

    def withdraw(self):
        item=self.items.currentItem()
        if not item or self.worker is not None:return
        record=item.data(Qt.UserRole);self.withdraw_id=record['id']
        self.worker=BillingRequest(self.session,'/api/admin/lessons/withdraw',{'id':record['id']},self)
        self.worker.completed.connect(self.received);self.worker.failed.connect(self.status.setText);self.worker.finished.connect(self.finished_request);self.worker.start()

    def received(self,path,result):
        self.status.setText(result.get('message','Đã cập nhật.'));self.window.sync_procedures()
        # Remove it from the local shared cache now; other clients receive the tombstone.
        if getattr(self,'withdraw_id',None):
            owner=ProcedureMemory(self.window.store).shared_owner(self.session['username'])
            with self.window.store.connection() as db:db.execute('DELETE FROM procedure_memory WHERE owner=? AND id=?',(owner,self.withdraw_id))
        self.load()

    def finished_request(self):self.worker.deleteLater();self.worker=None

    def reject(self):
        if self.worker is not None:self.status.setText('Đợi yêu cầu hoàn tất trước khi đóng.');return
        self.session.clear();super().reject()

    def closeEvent(self,event):
        if self.worker is not None:event.ignore();return
        self.session.clear();event.accept()

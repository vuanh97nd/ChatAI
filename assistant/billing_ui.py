"""Prepaid wallet and admin payments, using the existing Qt application theme."""
import uuid
from datetime import datetime
from urllib.request import urlopen
from urllib.parse import urlparse
from PySide6.QtCore import QThread, Signal, QTimer, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QFormLayout, QLineEdit, QComboBox, QCheckBox,
    QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea)
from .accounts import request_account


def money(value):
    whole,fraction=f'{float(value):,.2f}'.split('.')
    fraction=fraction.rstrip('0')
    return whole.replace(',', '.')+(','+fraction if fraction else '')+' đ'


def date_label(value):
    if not value:return '—'
    return datetime.fromtimestamp(value/1000).strftime('%d/%m/%Y %H:%M')


class BillingRequest(QThread):
    completed=Signal(str,object)
    failed=Signal(str)

    def __init__(self,session,path,body,parent):
        super().__init__(parent)
        self.session=dict(session);self.path=path;self.body=dict(body)

    def run(self):
        try:
            result=request_account(self.session['endpoint'],self.path,
                {**self.body,'username':self.session['username'],'key':self.session['key']},timeout=20)
            if result.get('qr_url'):
                # Only fetch the public QR image, never forward account credentials.
                url=result['qr_url'];parsed=urlparse(url)
                if parsed.scheme=='https' and parsed.hostname=='img.vietqr.io':
                    try:
                        with urlopen(url,timeout=10) as response:
                            raw=response.read(1000001)
                            if len(raw)<=1000000:result['_qr_bytes']=raw
                    except Exception:result['_qr_error']=True
            self.completed.emit(self.path,result)
        except Exception as error:
            text=str(error)
            for key in (self.session.get('key'),self.body.get('config',{}).get('secret')):
                if key:text=text.replace(key,'[ẨN]')
            self.failed.emit(text)
        finally:
            self.session.clear();self.body.clear()


class BillingDialog(QDialog):
    def __init__(self,session,parent=None):
        super().__init__(parent)
        self.session=dict(session);self.worker=None;self.current_order=None;self.credit_attempt=None
        self.is_admin=session.get('is_system') is True or session.get('username','').lower()=='admin'
        self.setWindowTitle('Số dư và thanh toán');self.resize(760,720)
        layout=QVBoxLayout(self)
        title=QLabel('Số dư và thanh toán');title.setStyleSheet('font-size: 20px; font-weight: 600;')
        layout.addWidget(title)
        note=QLabel('Cloud AI, NVIDIA và AI local miễn phí. DeepSeek: 4.000 đ/triệu token.\n'
                    'Miễn phí duy trì 30 ngày đầu; vẫn cần nạp token. Sau đó 100.000 đ/30 ngày.\nOpenAI chưa thiết lập bảng giá; chưa mở tính phí.');note.setWordWrap(True);layout.addWidget(note)
        self.tabs=QTabWidget();layout.addWidget(self.tabs)
        wallet=QWidget();wl=QVBoxLayout(wallet);self.tabs.addTab(wallet,'Ví token')
        self.summary=QLabel('Đang tải số dư…');self.summary.setWordWrap(True);wl.addWidget(self.summary)
        row=QHBoxLayout();self.amount=QComboBox()
        for value in [20000,50000,100000,200000,500000]:self.amount.addItem(money(value),value)
        row.addWidget(self.amount);self.topup=QPushButton('Nạp token bằng QR');self.topup.clicked.connect(lambda:self.create_order('topup'));row.addWidget(self.topup)
        self.renew=QPushButton('Gia hạn 30 ngày · 100.000 đ');self.renew.clicked.connect(lambda:self.create_order('service'));wl.addLayout(row);wl.addWidget(self.renew)
        self.qr=QLabel();self.qr.setAlignment(Qt.AlignCenter);wl.addWidget(self.qr)
        self.payment_info=QLabel('QR sẽ tự xác nhận khi ngân hàng gửi giao dịch. Không cần gửi ảnh chuyển khoản.');self.payment_info.setWordWrap(True);self.payment_info.setTextFormat(Qt.PlainText);wl.addWidget(self.payment_info);wl.addStretch()
        self.orders=self.table(['Thời gian','Loại','Số tiền','Trạng thái','Nội dung / người nạp'])
        self.tabs.addTab(self.orders,'Lịch sử nạp')
        self.usage=self.table(['Thời gian','Token','Tiền sử dụng','Trạng thái','Mã lượt'])
        self.tabs.addTab(self.usage,'Sử dụng AI')
        if self.is_admin:self.build_admin()
        self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);layout.addWidget(self.status)
        footer=QHBoxLayout();refresh=QPushButton('Làm mới');refresh.clicked.connect(self.refresh);footer.addWidget(refresh);footer.addStretch();close=QPushButton('Đóng');close.clicked.connect(self.close);footer.addWidget(close);layout.addLayout(footer)
        self.timer=QTimer(self);self.timer.setInterval(5000);self.timer.timeout.connect(self.poll)
        self.refresh()

    @staticmethod
    def table(headers):
        table=QTableWidget(0,len(headers));table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.NoEditTriggers);table.setSelectionBehavior(QTableWidget.SelectRows)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True);return table

    def build_admin(self):
        panel=QWidget();form=QFormLayout(panel)
        self.enabled=QCheckBox('Bật QR tự động và thu phí DeepSeek');form.addRow(self.enabled)
        self.bank=QLineEdit();self.bank.setPlaceholderText('Mã VietQR: VCB, BIDV, MB, …')
        self.account=QLineEdit();self.name=QLineEdit();self.secret=QLineEdit();self.secret.setEchoMode(QLineEdit.Password)
        for label,widget in [('Ngân hàng',self.bank),('Số tài khoản',self.account),('Tên người nhận',self.name),('Khóa webhook SePay',self.secret)]:form.addRow(label,widget)
        self.webhook=QLineEdit();self.webhook.setReadOnly(True);form.addRow('URL webhook',self.webhook)
        help_text=QLabel('Trong SePay, tạo webhook nhận tiền vào URL trên, xác thực kiểu API Key.\n'
                        'Khóa để trống giữ nguyên khóa đã lưu. Chỉ bật sau khi cấu hình webhook và thử giao dịch thực.');help_text.setWordWrap(True);form.addRow(help_text)
        save=QPushButton('Lưu cấu hình thanh toán');save.clicked.connect(self.save_config);form.addRow(save)
        self.target=QLineEdit();self.target.setPlaceholderText('Tên đăng nhập người dùng')
        self.manual_amount=QSpinBox();self.manual_amount.setRange(1000,5000000);self.manual_amount.setSingleStep(1000);self.manual_amount.setValue(20000);self.manual_amount.setSuffix(' đ')
        self.reason=QLineEdit();self.reason.setMaxLength(300);self.reason.setPlaceholderText('Lý do nạp / chứng từ')
        for label,widget in [('Người dùng',self.target),('Nạp thủ công',self.manual_amount),('Lý do',self.reason)]:form.addRow(label,widget)
        row=QHBoxLayout();view=QPushButton('Xem ví người dùng');view.clicked.connect(self.view_user);row.addWidget(view)
        credit=QPushButton('Nạp thủ công');credit.clicked.connect(self.manual_credit);row.addWidget(credit);form.addRow(row)
        manage=QPushButton('Quản lý / khóa / mở khóa người dùng');manage.clicked.connect(self.manage_users);form.addRow(manage)
        self.review_id=QLineEdit();self.review_tokens=QSpinBox();self.review_tokens.setRange(0,10000000)
        form.addRow('Mã lượt chờ đối soát',self.review_id);form.addRow('Token đã xác minh',self.review_tokens)
        reconcile=QPushButton('Đối soát lượt (cần lý do ở trên)');reconcile.clicked.connect(self.reconcile);form.addRow(reconcile)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(panel);self.tabs.addTab(scroll,'Quản trị thanh toán')

    def manage_users(self):
        parent=self.parent()
        if parent and hasattr(parent,'open_user_admin'):parent.open_user_admin()

    def send(self,path,body=None):
        if self.worker and self.worker.isRunning():return False
        self.tabs.setEnabled(False);self.status.setText('Đang xử lý…')
        self.worker=BillingRequest(self.session,path,body or {},self)
        self.worker.completed.connect(self.received);self.worker.failed.connect(self.failed)
        self.worker.finished.connect(self.finished);self.worker.start();return True

    def finished(self):
        self.tabs.setEnabled(True)
        if self.worker:self.worker.deleteLater();self.worker=None
        if getattr(self,'load_config_next',False):
            self.load_config_next=False;self.send('/api/admin/billing/config/get')

    def failed(self,text):self.status.setText(text)

    def refresh(self):
        if self.send('/api/billing/status') and self.is_admin:self.load_config_next=True

    def poll(self):
        if self.current_order:self.send('/api/billing/status')

    def create_order(self,kind):
        self.send('/api/billing/order',{'kind':kind,'amount':self.amount.currentData() if kind=='topup' else 100000,'request_id':str(uuid.uuid4())})

    def save_config(self):
        self.send('/api/admin/billing/config/save',{'config':{'enabled':self.enabled.isChecked(),'bank':self.bank.text().strip(),'account':self.account.text().strip(),'name':self.name.text().strip(),'secret':self.secret.text().strip()}})
        self.secret.clear()

    def view_user(self):self.send('/api/admin/billing/status',{'target':self.target.text().strip()})

    def manual_credit(self):
        fields=(self.target.text().strip(),self.manual_amount.value(),self.reason.text().strip())
        if not self.credit_attempt or self.credit_attempt[0]!=fields:self.credit_attempt=(fields,str(uuid.uuid4()))
        self.send('/api/admin/billing/credit',{'target':fields[0],'amount':fields[1],'note':fields[2],'request_id':self.credit_attempt[1]})

    def reconcile(self):
        self.send('/api/admin/billing/reconcile',{'id':self.review_id.text().strip(),'tokens':self.review_tokens.value(),'note':self.reason.text().strip()})

    def received(self,path,result):
        self.status.setText(result.get('message','Đã cập nhật.'))
        if 'config' in result:
            c=result['config'];self.enabled.setChecked(c['enabled']);self.bank.setText(c['bank']);self.account.setText(c['account']);self.name.setText(c['name']);self.webhook.setText(c['webhook_url'])
            self.secret.setPlaceholderText('Đã lưu khóa · để trống giữ nguyên' if c['secret_configured'] else 'Nhập khóa xác thực webhook')
        if 'wallet' in result:
            w=result['wallet'];self.summary.setText('Admin miễn phí; không trừ ví.' if w.get('exempt') else
                f"Tài khoản: {w['owner']} · Số dư {money(w['balance_vnd'])} · Khả dụng {money(w['available_vnd'])}\n"
                f"Giữ chỗ / đối soát: {money(w['held_vnd'])}\nMiễn phí duy trì đến {date_label(w['trial_until'])}\n"
                f"Gia hạn đến {date_label(w['service_until'])} · {'Còn hiệu lực' if w['service_active'] else 'Cần gia hạn để dùng DeepSeek'}")
            self.topup.setEnabled(result.get('enabled',False) and not self.is_admin);self.renew.setEnabled(result.get('enabled',False) and not self.is_admin)
        if 'orders' in result:
            states={'pending':'Chờ chuyển khoản','paid':'Đã nhận','expired':'Hết hạn'}
            rows=[]
            for o in result['orders']:
                state=o['status']
                if state=='pending' and o['expires']/1000<datetime.now().timestamp():state='expired'
                rows.append([date_label(o['created']),'Token' if o['kind']=='topup' else 'Duy trì',money(o['amount']),states.get(state,state),o.get('note') or o['memo']])
                if self.current_order and o['id']==self.current_order['id'] and state!='pending':
                    self.payment_info.setText('Đã nhận tiền, cập nhật ví / thời hạn duy trì.' if state=='paid' else 'QR đã hết hạn. Hãy tạo yêu cầu mới.');self.timer.stop();self.current_order=None
            self.fill(self.orders,rows)
        if 'usage' in result:
            states={'charged':'Đã tính phí','reserved':'Đang xử lý','pending_review':'Chờ đối soát','released':'Không tính phí','reconciled':'Đã đối soát','free':'Miễn phí','free_unknown_usage':'Miễn phí · thiếu usage'}
            self.fill(self.usage,[[date_label(u['created']),u['tokens'] if u['tokens'] is not None else '—',money(u['charged']/1000),states.get(u['state'],u['state']),u['id']] for u in result['usage']])
        if 'order' in result:
            self.current_order=result['order'];self.timer.start()
            pix=QPixmap();pix.loadFromData(result.get('_qr_bytes',b''))
            if not pix.isNull():self.qr.setPixmap(pix.scaled(300,300,Qt.KeepAspectRatio,Qt.SmoothTransformation))
            else:self.qr.clear();self.qr.setText('Chưa tải được ảnh QR. Có thể chuyển khoản bằng thông tin dưới đây.')
            self.payment_info.setText(f"{result['bank']} · {result['account']} · {result['name']}\nSố tiền: {money(self.current_order['amount'])}\nNội dung: {self.current_order['memo']}\nHiệu lực đến {date_label(self.current_order['expires'])}. Chuyển đúng số tiền và nội dung.")

    @staticmethod
    def fill(table,rows):
        table.setRowCount(len(rows))
        for row,values in enumerate(rows):
            for col,value in enumerate(values):table.setItem(row,col,QTableWidgetItem(str(value)))

    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            self.status.setText('Đợi yêu cầu hiện tại hoàn tất để đóng cửa sổ.');event.ignore();return
        self.timer.stop();self.session.clear();event.accept()

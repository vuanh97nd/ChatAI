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
        self.session=dict(session);self.worker=None;self.current_order=None;self.credit_attempt=None;self.service_fee=100000;self.token_price=4000
        self.is_admin=session.get('is_system') is True or session.get('username','').lower()=='admin'
        self.setWindowTitle('Số dư và thanh toán');self.resize(760,720)
        layout=QVBoxLayout(self)
        title=QLabel('Số dư và thanh toán');title.setStyleSheet('font-size: 20px; font-weight: 600;')
        layout.addWidget(title)
        self.plan_note=QLabel('Đang tải bảng giá từ server…');self.plan_note.setWordWrap(True);layout.addWidget(self.plan_note)
        self.tabs=QTabWidget();layout.addWidget(self.tabs)
        wallet=QWidget();wl=QVBoxLayout(wallet);self.tabs.addTab(wallet,'Ví token')
        self.summary=QLabel('Đang tải số dư…');self.summary.setWordWrap(True);wl.addWidget(self.summary)
        self.month_data={};self.usage_month=QComboBox();self.usage_month.currentIndexChanged.connect(self.show_month_usage)
        wl.addWidget(QLabel('Token sử dụng theo tháng · giờ Việt Nam'));wl.addWidget(self.usage_month)
        self.month_summary=QLabel('Đang tải thống kê token…');self.month_summary.setWordWrap(True);wl.addWidget(self.month_summary)
        row=QHBoxLayout();self.amount=QComboBox()
        for value in [20000,50000,100000,200000,500000]:self.amount.addItem(money(value),value)
        self.amount.addItem('Số tiền khác',None)
        self.custom_amount=QSpinBox();self.custom_amount.setRange(20000,10000000);self.custom_amount.setSingleStep(1000);self.custom_amount.setValue(20000);self.custom_amount.setSuffix(' đ');self.custom_amount.setGroupSeparatorShown(True);self.custom_amount.hide()
        self.custom_amount.editingFinished.connect(self.custom_amount_changed)
        row.addWidget(self.custom_amount)
        self.amount.currentIndexChanged.connect(self.amount_changed)
        row.addWidget(self.amount);self.topup=QPushButton('Nạp token bằng QR');self.topup.clicked.connect(lambda:self.create_order('topup'));row.addWidget(self.topup)
        self.renew=QPushButton('Đang tải phí duy trì…');self.renew.setEnabled(False);self.renew.clicked.connect(lambda:self.create_order('service'));wl.addLayout(row);wl.addWidget(self.renew)
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
        self.fee_field=QSpinBox();self.fee_field.setRange(0,5000000);self.fee_field.setSingleStep(1000);self.fee_field.setValue(self.service_fee);self.fee_field.setSuffix(' đ / 30 ngày')
        form.addRow('Phí duy trì',self.fee_field)
        self.token_price_field=QSpinBox();self.token_price_field.setRange(1,10000000);self.token_price_field.setValue(self.token_price);self.token_price_field.setSuffix(' đ / triệu token')
        form.addRow('Giá token DeepSeek',self.token_price_field)
        save_fee=QPushButton('Lưu bảng giá');save_fee.clicked.connect(lambda:self.send('/api/admin/billing/fee/save',{'service_fee':self.fee_field.value(),'token_price':self.token_price_field.value()}));form.addRow(save_fee)
        fee_note=QLabel('Phí duy trì 0 = miễn phí duy trì; vẫn trả phí token. Giá mới chỉ áp dụng cho đơn mới; không thay đổi thời hạn đã thanh toán.');fee_note.setWordWrap(True);form.addRow(fee_note)
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

    def send(self,path,body=None,background=False):
        if self.worker is not None:return False
        if not background:self.tabs.setEnabled(False);self.status.setText('Đang xử lý…')
        self.worker=BillingRequest(self.session,path,body or {},self)
        self.worker.completed.connect(self.received);self.worker.failed.connect(self.failed)
        self.worker.finished.connect(self.request_finished);self.worker.start();return True

    def request_finished(self):
        self.tabs.setEnabled(True)
        if self.worker:self.worker.deleteLater();self.worker=None
        if getattr(self,'pending_topup',False):
            self.pending_topup=False;self.create_order('topup');return
        if getattr(self,'load_config_next',False):
            self.load_config_next=False;self.send('/api/admin/billing/config/get')

    def failed(self,text):
        self.status.setText(text)
        if self.summary.text()=='Đang tải số dư…':
            self.summary.setText('Chưa tải được số dư. Bấm Làm mới để thử lại.')
            self.month_summary.setText('Chưa tải được thống kê token.')
        if not getattr(self,'pricing_loaded',False):
            self.plan_note.setText('Chưa tải được bảng giá từ server; chưa thể xác định phí duy trì.')
            self.renew.setText('Chưa tải được phí duy trì');self.renew.setEnabled(False)

    def show_month_usage(self):
        month=self.usage_month.currentData()
        if not month:return
        data=self.month_data[month]
        tokens=f"{int(data['tokens']):,}".replace(',','.')
        note=f" · {data['unknown_requests']} lượt chưa có số liệu token" if data['unknown_requests'] else ''
        self.month_summary.setText(f"{tokens} token · Phí token: {money(data['fee_vnd'])}{note}\nCập nhật: {self.month_updated}\nChỉ thống kê token API trả về; AI trên máy chưa thống kê.")

    def refresh(self):
        if self.send('/api/billing/status') and self.is_admin:self.load_config_next=True

    def poll(self):
        if self.current_order:self.send('/api/billing/status',background=True)

    def topup_amount(self):
        return self.custom_amount.value() if self.amount.currentData() is None else self.amount.currentData()

    def custom_amount_changed(self):
        if self.amount.currentData() is None and self.current_order and self.current_order.get('kind')=='topup' and self.current_order.get('amount')!=self.topup_amount():self.amount_changed()

    def amount_changed(self):
        self.custom_amount.setVisible(self.amount.currentData() is None)
        if self.current_order and self.current_order.get('kind')=='topup':
            self.timer.stop();self.current_order=None;self.qr.clear()
            self.payment_info.setText('Đang tạo QR theo mệnh giá mới…')
            if self.worker is not None:self.pending_topup=True
            else:self.create_order('topup')

    def create_order(self,kind):
        if kind=='topup' and self.topup_amount()%1000:
            self.status.setText('Số tiền nạp phải theo bội số 1.000đ.');return
        self.send('/api/billing/order',{'kind':kind,'amount':self.topup_amount() if kind=='topup' else self.service_fee,'request_id':str(uuid.uuid4())})

    def save_config(self):
        self.send('/api/admin/billing/config/save',{'config':{'enabled':self.enabled.isChecked(),'service_fee':self.fee_field.value(),'token_price':self.token_price_field.value(),'bank':self.bank.text().strip(),'account':self.account.text().strip(),'name':self.name.text().strip(),'secret':self.secret.text().strip()}})
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
        fee=result.get('service_fee',result.get('config',{}).get('service_fee'))
        price=result.get('token_price',result.get('price_per_million',result.get('config',{}).get('token_price')))
        if fee is not None:
            self.service_fee=fee;self.pricing_loaded=True
            if fee==0:self.renew.setEnabled(False)
        if price is not None:self.token_price=price
        if fee is not None or price is not None:
            if self.is_admin:
                self.fee_field.setValue(self.service_fee);self.token_price_field.setValue(self.token_price)
            self.renew.setText('Miễn phí duy trì' if self.service_fee==0 else 'Gia hạn 30 ngày · '+money(self.service_fee))
            maintenance='Miễn phí duy trì; vẫn cần nạp tiền token.' if self.service_fee==0 else 'Miễn phí duy trì 30 ngày đầu; vẫn cần nạp token. Sau đó '+money(self.service_fee)+'/30 ngày.'
            self.plan_note.setText('Cloud AI, NVIDIA và AI trên máy miễn phí. DeepSeek: '+money(self.token_price)+'/triệu token.\n'+maintenance+'\nOpenAI chưa thiết lập bảng giá; chưa mở tính phí.')
        if 'config' in result:
            c=result['config'];self.enabled.setChecked(c['enabled']);self.bank.setText(c['bank']);self.account.setText(c['account']);self.name.setText(c['name']);self.webhook.setText(c['webhook_url'])
            self.secret.setPlaceholderText('Đã lưu khóa · để trống giữ nguyên' if c['secret_configured'] else 'Nhập khóa xác thực webhook')
        if 'wallet' in result:
            w=result['wallet']
            maintenance='Miễn phí duy trì; không cần gia hạn.' if w.get('maintenance_waived') else (
                f"Miễn phí duy trì đến {date_label(w['trial_until'])}\nGia hạn đến {date_label(w['service_until'])} · {'Còn hiệu lực' if w['service_active'] else 'Cần gia hạn để dùng DeepSeek'}")
            self.summary.setText('Admin miễn phí; không trừ ví.' if w.get('exempt') else
                f"Tài khoản: {w['owner']} · Số dư {money(w['balance_vnd'])} · Khả dụng {money(w['available_vnd'])}\n"
                f"Giữ chỗ / đối soát: {money(w['held_vnd'])}\n"+maintenance)
            self.topup.setEnabled(result.get('enabled',False) and not self.is_admin);self.renew.setEnabled(result.get('enabled',False) and not self.is_admin and self.service_fee>0)
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
        if 'monthly_usage' in result:
            selected=self.usage_month.currentData() or result['current_month']
            self.month_data={m['month']:m for m in result['monthly_usage']}
            self.month_data.setdefault(result['current_month'],{'tokens':0,'fee_vnd':0,'unknown_requests':0})
            self.month_updated=date_label(result['usage_updated_at'])
            self.usage_month.blockSignals(True);self.usage_month.clear()
            for month in sorted(self.month_data,reverse=True):
                self.usage_month.addItem(month[5:]+'/'+month[:4],month)
            index=self.usage_month.findData(selected);self.usage_month.setCurrentIndex(max(0,index))
            self.usage_month.blockSignals(False);self.show_month_usage()
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

    def reject(self):
        if self.worker is not None:
            self.status.setText('Đợi yêu cầu hoàn tất trước khi đóng.');return
        self.timer.stop();self.session.clear();super().reject()

    def closeEvent(self,event):
        if self.worker is not None:
            self.status.setText('Đợi yêu cầu hiện tại hoàn tất để đóng cửa sổ.');event.ignore();return
        self.timer.stop();self.session.clear();event.accept()

"""Administrator account management; all permission checks are repeated by server."""
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QComboBox,
    QTableWidget,QTableWidgetItem,QAbstractItemView,QHeaderView,QDialog,QFormLayout,
    QDialogButtonBox,QMessageBox,QInputDialog,QPlainTextEdit)
from .accounts import request_account


def admin_session(session):
    return bool(session and session.get('role')=='system')


def date_label(value):
    if not value:return 'Chưa có dữ liệu'
    try:return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone().strftime('%d/%m/%Y %H:%M')
    except (ValueError,AttributeError):return str(value)


class AdminMixin:
    def admin_request(self,action,body,callback):
        if not admin_session(self.server_session) or self.busy():return
        session=dict(self.server_session)
        def done(result):
            current=self.server_session or {}
            if admin_session(current) and (current.get('username'),current.get('endpoint'))==(session['username'],session['endpoint']):callback(result)
        self.work(lambda emit:request_account(session['endpoint'],'/api/admin/accounts/'+action,
            dict(body,username=session['username'],key=session['key']),timeout=20),done)

    def open_user_admin(self):
        if not admin_session(self.server_session):return
        if not hasattr(self,'admin_page'):
            page=QWidget();self.admin_page=page;layout=QVBoxLayout(page)
            self.button(layout,'← Quay lại chat',lambda:self.tabs.setCurrentIndex(0))
            title=QLabel('Quản lý người dùng');title.setStyleSheet('font-size:22px;font-weight:600;');layout.addWidget(title)
            row=QHBoxLayout();layout.addLayout(row)
            self.admin_search=QLineEdit();self.admin_search.setPlaceholderText('Họ tên, tên đăng nhập hoặc email');row.addWidget(self.admin_search)
            self.admin_filter=QComboBox()
            for label,value in [('Tất cả','all'),('Đang hoạt động','active'),('Bị khóa','locked'),('Đã xóa mềm','deleted')]:self.admin_filter.addItem(label,value)
            row.addWidget(self.admin_filter);self.button(row,'Tìm / Làm mới',self.reload_admin_users)
            self.admin_search.returnPressed.connect(self.reload_admin_users)
            self.admin_table=QTableWidget(0,14);self.admin_table.setHorizontalHeaderLabels(['Họ tên','Tên đăng nhập','Liên hệ','Tài khoản','Hoạt động','Lần gần nhất','Cập nhật hồ sơ','Thời hạn','Token tháng này','Tổng token','Phí token tháng','Số dư ví','Hạn duy trì','Thiếu usage / đối soát'])
            self.admin_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            self.admin_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            self.admin_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            self.admin_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            self.admin_table.setMinimumHeight(320);layout.addWidget(self.admin_table)
            self.admin_table.cellDoubleClicked.connect(lambda *_:self.show_admin_user())
            self.admin_status=QLabel('Chọn một tài khoản để xem chi tiết.');self.admin_status.setWordWrap(True);layout.addWidget(self.admin_status)
            note=QLabel('Online theo tín hiệu ứng dụng trong 90 giây gần nhất; không phải theo dõi thời gian thực. Ngày tạo cũ chưa ghi nhận sẽ hiển thị “Chưa có dữ liệu”. Token tính theo usage API đã ghi nhận; lượt thiếu usage và token local không được ước lượng. Tháng tính theo giờ Việt Nam.');note.setWordWrap(True);layout.addWidget(note)
            actions=QHBoxLayout();layout.addLayout(actions)
            for label,fn in [('Chi tiết / Chỉnh sửa',self.show_admin_user),('Khóa',lambda:self.admin_account_action('lock')),
                             ('Mở khóa',lambda:self.admin_account_action('unlock')),('Thu hồi đăng nhập',lambda:self.admin_account_action('revoke')),
                             ('Xóa tài khoản',lambda:self.admin_account_action('delete')),('Khôi phục',lambda:self.admin_account_action('restore'))]:self.button(actions,label,fn)
            pager=QHBoxLayout();layout.addLayout(pager)
            self.button(pager,'← Trang trước',lambda:self.admin_page_move(-100));self.button(pager,'Trang sau →',lambda:self.admin_page_move(100))
            self.admin_offset=0;self.admin_total=0;self.admin_users=[]
            self.add_scroll_page(page,'Quản lý người dùng');self.admin_page_index=self.tabs.count()-1;self.admin_scroll=self.tabs.widget(self.admin_page_index)
        self.tabs.setCurrentWidget(self.admin_scroll);self.reload_admin_users()

    def reload_admin_users(self,reset=True):
        if not hasattr(self,'admin_table') or not admin_session(self.server_session):return
        if reset:self.admin_offset=0
        self.admin_status.setText('Đang tải danh sách người dùng…')
        def done(result):
            self.admin_users=result['users'];self.admin_total=result['total'];self.admin_table.setRowCount(len(self.admin_users))
            for row,user in enumerate(self.admin_users):
                account={'active':'Hoạt động','locked':'Bị khóa','deleted':'Đã xóa mềm'}.get(user['account_status'],'Không rõ')
                activity={'online':'● Online','offline':'Offline','unknown':'Không rõ trạng thái'}.get(user.get('activity_status'),'Không rõ trạng thái')
                values=[user['fullname'],user['username'],user.get('email') or user.get('phone') or '',account,activity,
                        date_label(user.get('presence_at') or user.get('last_seen_at')),date_label(user.get('profile_updated_at') or user.get('updated_at')),user['expires_at']]
                from .billing_ui import money,date_label as billing_date
                billing=user.get('billing') or {}
                values.extend([f"{billing.get('month_tokens',0):,}",f"{billing.get('total_tokens',0):,}",money(billing.get('month_token_fee',0)),money(billing.get('balance_vnd',0)),('Miễn phí' if billing.get('maintenance_waived') else billing_date(billing.get('maintenance_until'))),billing.get('pending_count',0)])
                for col,value in enumerate(values):
                    item=QTableWidgetItem(str(value));item.setToolTip(str(value));self.admin_table.setItem(row,col,item)
                    if col in (8,9):item.setToolTip('Tổng token API đã ghi nhận (đầu vào + đầu ra).\nDeepSeek tính phí: '+str(billing.get('paid_total_tokens',0))+' token tổng cộng\nAI miễn phí: '+str(billing.get('free_total_tokens',0))+' token tổng cộng\nChưa gồm lượt thiếu usage và token local. Tháng theo giờ Việt Nam.')
            self.admin_status.setText(f"{self.admin_offset+1 if self.admin_users else 0}–{self.admin_offset+len(self.admin_users)} / {self.admin_total} tài khoản · cập nhật {datetime.now():%H:%M:%S}")
        self.admin_request('list',{'search':self.admin_search.text(),'filter':self.admin_filter.currentData(),'offset':self.admin_offset},done)

    def admin_page_move(self,delta):
        offset=max(0,self.admin_offset+delta)
        if delta>0 and offset>=self.admin_total:return
        self.admin_offset=offset;self.reload_admin_users(False)

    def selected_admin_user(self):
        row=self.admin_table.currentRow()
        if 0<=row<len(self.admin_users):return self.admin_users[row]
        QMessageBox.information(self,'Quản lý người dùng','Chọn một tài khoản trước.');return None

    def admin_account_action(self,action):
        user=self.selected_admin_user()
        if not user:return
        target=user['username'];labels={'lock':'Khóa','unlock':'Mở khóa','revoke':'Thu hồi đăng nhập','delete':'Xóa mềm','restore':'Khôi phục'}
        text=labels[action]+' tài khoản '+target+'?'
        if action=='delete':text+='\nTài khoản bị vô hiệu hóa. Giữ dữ liệu để khôi phục trong 30 ngày; không xóa hội thoại trên máy người dùng.'
        elif action=='revoke':text+='\nCác phiên đang dùng bị vô hiệu hóa; người dùng có thể đăng nhập lại bằng mật khẩu.'
        if QMessageBox.question(self,labels[action],text,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        if action=='delete':
            value,ok=QInputDialog.getText(self,'Xác nhận xóa mềm','Nhập đúng tên đăng nhập: '+target)
            if not ok or value.strip()!=target:return
        def done(result):
            QMessageBox.information(self,'Quản lý người dùng',result['message']);self.reload_admin_users(False)
        self.admin_request(action,{'target':target,'confirm':True},done)

    def show_admin_user(self):
        user=self.selected_admin_user()
        if not user:return
        self.admin_request('detail',{'target':user['username']},self.edit_admin_user_dialog)

    def edit_admin_user_dialog(self,result):
        user=result['user'];dialog=QDialog(self);dialog.setWindowTitle('Tài khoản '+user['username']);dialog.resize(650,620)
        layout=QVBoxLayout(dialog)
        from .profile_ui import paint_avatar
        avatar=QLabel();paint_avatar(avatar,user.get('avatar'),user['fullname'],64,self.preview_theme);layout.addWidget(avatar)
        form=QFormLayout();layout.addLayout(form)
        fields={}
        for key,label in [('fullname','Họ và tên'),('email','Email'),('phone','Số điện thoại')]:
            field=QLineEdit(str(user.get(key) or ''));fields[key]=field;form.addRow(label,field)
        tier=QComboBox();tier.addItems(['trial','pro','oem']);tier.setCurrentText(user['tier']);form.addRow('Loại tài khoản',tier)
        expiry=QLineEdit(user['expires_at']);expiry.setPlaceholderText('YYYY-MM-DD hoặc Vĩnh viễn');form.addRow('Thời hạn',expiry)
        info=QLabel('Tên đăng nhập: '+user['username']+'\nNgày tạo: '+date_label(user.get('created_at'))+'\nCập nhật: '+date_label(user.get('updated_at'))+'\nHồ sơ cập nhật: '+date_label(user.get('profile_updated_at'))+'\nHoạt động gần nhất: '+date_label(user.get('last_seen_at'))+'\nTrạng thái: '+user['account_status']);info.setWordWrap(True);layout.addWidget(info)
        from .billing_ui import money,date_label as billing_date
        billing=user.get('billing') or {}
        totals=QLabel('Token tháng này: '+f"{billing.get('month_tokens',0):,}"+' · Tổng: '+f"{billing.get('total_tokens',0):,}"+'\nPhí token tháng: '+money(billing.get('month_token_fee',0))+' · Ví: '+money(billing.get('balance_vnd',0))+'\nHạn duy trì: '+('Miễn phí' if billing.get('maintenance_waived') else billing_date(billing.get('maintenance_until')))+' · Lượt thiếu usage / đối soát: '+str(billing.get('pending_count',0)));totals.setWordWrap(True);layout.addWidget(totals)
        log=QPlainTextEdit();log.setReadOnly(True);log.setPlainText('\n'.join(date_label(row['created_at'])+' · '+row['action']+' · '+row['details'] for row in result.get('audit',[])));layout.addWidget(QLabel('Nhật ký quản trị gần nhất'));layout.addWidget(log)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.button(QDialogButtonBox.StandardButton.Save).setText('Lưu thay đổi');buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Hủy');layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
        buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(user['account_status']!='deleted')
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        profile={key:field.text().strip() for key,field in fields.items()}
        preview='\n'.join(key+': '+str(user.get(key) or '')+' → '+value for key,value in profile.items())+'\nLoại: '+user['tier']+' → '+tier.currentText()+'\nThời hạn: '+user['expires_at']+' → '+expiry.text().strip()
        if QMessageBox.question(self,'Xác nhận cập nhật',preview,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        self.admin_request('update',{'target':user['username'],'profile':profile,'tier':tier.currentText(),'expires_at':expiry.text().strip(),'confirm':True},lambda _:self.reload_admin_users(False))

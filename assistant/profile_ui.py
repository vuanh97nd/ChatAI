"""Account presentation and editing, with no connection URL in profile pages."""
import re
from PySide6.QtCore import Qt,QByteArray,QBuffer,QIODevice,QRectF
from PySide6.QtGui import QImageReader,QPixmap,QPainter,QPainterPath
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QLabel,QGroupBox,QFormLayout,QDialog,
    QDialogButtonBox,QLineEdit,QHBoxLayout,QFileDialog,QMessageBox)
from .accounts import request_account
from .themes import recolor

PROFILE_KEYS=('fullname','email','phone','avatar')


def paint_avatar(label,data,name,size,theme):
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setFixedSize(size,size);label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setProperty('chatBaseStyle',None)
    if data and data.startswith('data:image/jpeg;base64,'):
        raw=QByteArray.fromBase64(data.split(',',1)[1].encode());buffer=QBuffer(raw);buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        reader=QImageReader(buffer);dimensions=reader.size();source=QPixmap()
        if dimensions.isValid() and dimensions.width()*dimensions.height()<=1048576:source=QPixmap.fromImage(reader.read())
        buffer.close()
        if not source.isNull():
            image=source.scaled(size,size,Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation)
            target=QPixmap(size,size);target.fill(Qt.GlobalColor.transparent)
            painter=QPainter(target);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            clip=QPainterPath();clip.addEllipse(QRectF(0,0,size,size));painter.setClipPath(clip)
            painter.drawPixmap((size-image.width())//2,(size-image.height())//2,image);painter.end()
            label.setStyleSheet('background:transparent;');label.setPixmap(target);return
    label.clear();label.setText(''.join(word[0] for word in name.split()[:2]).upper() or '?')
    css=f'background:#282a2c;color:#a8c7fa;border-radius:{size//2}px;font-size:{max(12,size//3)}px;'
    label.setProperty('chatBaseStyle',css);label.setStyleSheet(recolor(css,theme))


class ProfileMixin:
    def refresh_account_ui(self):
        session=self.server_session or {};logged=bool(session)
        for button in (self.account_register_button,self.account_login_button,self.account_remember):button.setVisible(not logged)
        for button in (self.account_edit_button,self.account_password_button,self.account_logout_button):button.setVisible(logged)
        self.account_name_label.setVisible(logged);self.account_username_label.setVisible(logged)
        self.account_email_label.setVisible(logged);self.account_phone_label.setVisible(logged)
        name=session.get('fullname') or session.get('username') or 'Khách'
        self.account_name_label.setText('Họ và tên: '+name)
        self.account_username_label.setText('Tên đăng nhập: '+session.get('username',''))
        self.account_email_label.setText('Email: '+(session.get('email') or 'Chưa cập nhật'))
        self.account_phone_label.setText('Số điện thoại: '+(session.get('phone') or 'Chưa cập nhật'))
        paint_avatar(self.profile_avatar,session.get('avatar'),name,30,self.preview_theme)
        self.apply_settings_button.setEnabled(not self.busy() and self.settings_dirty())
        identity=(session.get('endpoint'),session.get('username'))
        if identity!=getattr(self,'profile_visible_identity',None):
            self.profile_visible_identity=identity
            old_index=getattr(self,'profile_page_index',None)
            if old_index is not None:
                if self.tabs.currentIndex()==old_index:self.tabs.setCurrentIndex(0)
                self.remove_dynamic_page('profile_page_index')

    def account_settings_changed(self,value=None):
        if hasattr(self,'apply_settings_button'):
            self.apply_settings_button.setEnabled(not self.busy() and self.settings_dirty())

    def edit_personal_info(self):
        if self.busy():return
        if not self.server_session:self.login_dialog();return
        session=dict(self.server_session)
        def task(emit):return request_account(session['endpoint'],'/api/account/profile/get',{'username':session['username'],'key':session['key']})['profile']
        self.work(task,self.show_profile_editor)

    def show_profile_editor(self,profile):
        if not self.server_session:return
        session=dict(self.server_session)
        dialog=QDialog(self);dialog.setWindowTitle('Chỉnh sửa thông tin cá nhân');form=QFormLayout(dialog)
        username=QLineEdit(session['username']);username.setReadOnly(True);form.addRow('Tên đăng nhập',username)
        fullname=QLineEdit(profile.get('fullname') or session.get('fullname') or session['username']);fullname.setMaxLength(120);form.addRow('Họ và tên',fullname)
        email=QLineEdit(profile.get('email',''));email.setMaxLength(254);email.setPlaceholderText('Không bắt buộc');form.addRow('Email',email)
        phone=QLineEdit(profile.get('phone',''));phone.setMaxLength(30);phone.setPlaceholderText('Không bắt buộc');form.addRow('Số điện thoại',phone)
        avatar={'data':profile.get('avatar') or ''};preview=QLabel();form.addRow('Ảnh đại diện',preview)
        paint_avatar(preview,avatar['data'],fullname.text(),72,self.preview_theme)
        row=QHBoxLayout()
        def choose():
            path,_=QFileDialog.getOpenFileName(dialog,'Chọn ảnh đại diện','','Ảnh (*.png *.jpg *.jpeg *.webp)')
            if not path:return
            from pathlib import Path
            if Path(path).stat().st_size>8*1024*1024:QMessageBox.warning(dialog,'Ảnh đại diện','Ảnh đầu vào tối đa 8 MB.');return
            reader=QImageReader(path);size=reader.size()
            if not size.isValid() or size.width()*size.height()>16000000:
                QMessageBox.warning(dialog,'Ảnh đại diện','Chọn ảnh hợp lệ không quá 16 triệu điểm ảnh.');return
            image=reader.read()
            if image.isNull():QMessageBox.warning(dialog,'Ảnh đại diện','Không đọc được ảnh.');return
            image=image.scaled(256,256,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
            raw=QByteArray();buffer=QBuffer(raw);buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            ok=image.save(buffer,'JPEG',85);buffer.close()
            if not ok or raw.size()>131072:QMessageBox.warning(dialog,'Ảnh đại diện','Không chuẩn bị được ảnh đại diện.');return
            avatar['data']='data:image/jpeg;base64,'+bytes(raw.toBase64()).decode('ascii')
            paint_avatar(preview,avatar['data'],fullname.text(),72,self.preview_theme)
        def remove():avatar['data']='';paint_avatar(preview,'',fullname.text(),72,self.preview_theme)
        self.button(row,'Chọn ảnh',choose);self.button(row,'Bỏ ảnh',remove);form.addRow(row)
        note=QLabel('Email là thông tin liên hệ, chưa dùng để khôi phục mật khẩu.');note.setWordWrap(True);form.addRow(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('Lưu thông tin');buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Hủy')
        buttons.rejected.connect(dialog.reject)
        def accept():
            if not fullname.text().strip():QMessageBox.warning(dialog,'Thông tin cá nhân','Nhập họ và tên.');return
            if email.text().strip() and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email.text().strip()):
                QMessageBox.warning(dialog,'Thông tin cá nhân','Email chưa hợp lệ.');return
            if phone.text().strip() and (not re.fullmatch(r'\+?[0-9 ()-]{7,30}',phone.text().strip()) or not 7<=len(re.sub(r'\D','',phone.text()))<=15):
                QMessageBox.warning(dialog,'Thông tin cá nhân','Số điện thoại cần 7–15 chữ số.');return
            dialog.accept()
        buttons.accepted.connect(accept);form.addRow(buttons)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        payload={'fullname':fullname.text().strip(),'email':email.text().strip(),'phone':phone.text().strip(),'avatar':avatar['data']}
        def task(emit):
            result=request_account(session['endpoint'],'/api/account/profile/update',{'username':session['username'],'key':session['key'],'profile':payload})['profile']
            # Update remembered login only if it was already enabled for this account.
            warning=''
            try:
                from .accounts import load_login,save_login
                saved=load_login()
                if saved and saved.get('username')==session['username'] and saved.get('endpoint')==session['endpoint']:
                    for key in PROFILE_KEYS:saved[key]=result.get(key,'')
                    save_login(saved)
            except Exception:warning=' Chưa cập nhật được dữ liệu đăng nhập đã nhớ; thông tin trên tài khoản đã lưu.'
            return result,warning
        def done(result):
            if not self.server_session or self.server_session['username']!=session['username']:return
            for key in PROFILE_KEYS:self.server_session[key]=result[0].get(key,'')
            self.render();self.account_status.setText('Đã cập nhật thông tin cá nhân.')
            profile_tab=getattr(self,'profile_page_index',None)
            if profile_tab is not None and self.tabs.currentIndex()==profile_tab:self.open_profile()
            QMessageBox.information(self,'Thông tin cá nhân','Đã lưu thông tin.'+result[1])
        self.work(task,done)

    def open_profile(self):
        session=self.server_session
        if not session:self.login_dialog();return
        self.remove_dynamic_page('profile_page_index')
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(32,24,32,24)
        self.button(layout,'← Quay lại chat',lambda:self.tabs.setCurrentIndex(0))
        name=session.get('fullname') or session['username'];avatar=QLabel()
        paint_avatar(avatar,session.get('avatar'),name,80,self.preview_theme);layout.addWidget(avatar,alignment=Qt.AlignmentFlag.AlignHCenter)
        title=QLabel(name);title.setTextFormat(Qt.TextFormat.PlainText);title.setAlignment(Qt.AlignmentFlag.AlignCenter);title.setStyleSheet('font-size:24px;font-weight:600;');layout.addWidget(title)
        card=QGroupBox('Thông tin cá nhân');form=QFormLayout(card)
        for label,value in [('Tên đăng nhập',session['username']),('Email',session.get('email') or 'Chưa cập nhật'),('Số điện thoại',session.get('phone') or 'Chưa cập nhật')]:
            field=QLabel(value);field.setTextFormat(Qt.TextFormat.PlainText);form.addRow(label,field)
        layout.addWidget(card);self.button(layout,'Chỉnh sửa thông tin cá nhân',self.edit_personal_info)
        self.button(layout,'Đổi mật khẩu',self.change_password_dialog);layout.addStretch(1)
        self.add_scroll_page(page,'Hồ sơ');self.profile_page_index=self.tabs.count()-1;self.tabs.setCurrentIndex(self.profile_page_index)

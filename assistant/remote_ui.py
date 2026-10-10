"""Desktop pairing and delivery into the existing ChatAI executor."""
import json
import re
from PySide6.QtCore import QTimer, Qt, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QPlainTextEdit,QPushButton,QCheckBox,QMessageBox,QApplication
from .remote_bridge import RemoteChannel,register_device,desktop_api,existing_plaxis_input

class RemoteMixin:
    def init_remote(self):
        self.remote_channel=None;self.remote_device=None;self.remote_task=None
        self.remote_screen_allowed=False
        self.remote_approval_seen=set();self.remote_stop_action=None
        self.remote_ready_timer=QTimer(self);self.remote_ready_timer.setInterval(1000)
        self.remote_ready_timer.timeout.connect(self.remote_ready);self.remote_ready_timer.start()
    def remote_ready(self):
        channel=self.remote_channel
        if not channel:return
        if not self.server_session or self.server_session['username']!=channel.session['username'] or self.server_session['endpoint']!=channel.session['endpoint']:
            channel.stop();channel.set_ready(False)
            if self.remote_task and self.worker and self.worker.cancellable:self.worker.stop_requested.set()
            return
        channel.session['key']=self.server_session['key']
        channel.set_ready(not self.busy() and not self.remote_task and not self.input.toPlainText().strip()
                          and not self.store.load(self.cid).get('running') and not self.pending_documents and not self.pending_image)
    def remote_connect_dialog(self):
        if self.remote_task:
            QMessageBox.information(self,'Kết nối điện thoại','Dừng hoặc kết thúc tác vụ hiện tại trước khi tạo phiên kết nối mới.');return
        if not self.server_session:
            QMessageBox.information(self,'Kết nối điện thoại','Đăng nhập cùng tài khoản trên máy tính và điện thoại trước.');return
        session=dict(self.server_session)
        def setup(emit):
            device=register_device(session)
            # The first explicit connection enables receipt; normal startup does not.
            desktop_api(session,device,'enable',enabled=True)
            return device,desktop_api(session,device,'pair'),desktop_api(session,device,'links')
        def show(result):
            device,pair,links=result;self.remote_device=device
            if self.remote_channel and self.remote_channel.isRunning():self.remote_channel.stop()
            self.remote_screen_allowed=False
            channel=RemoteChannel(session,device,self);self.remote_channel=channel
            channel.event.connect(self.remote_event);channel.finished.connect(lambda:self.remote_channel_ended(channel));channel.start()
            dialog=QDialog(self);dialog.setWindowTitle('Kết nối điện thoại');dialog.resize(540,650)
            layout=QVBoxLayout(dialog)
            label=QLabel('Android → Máy tính → Quét QR. QR hết hạn sau 5 phút.\nWindows sẽ hỏi xác nhận tên điện thoại một lần.');label.setWordWrap(True);layout.addWidget(label)
            try:
                import qrcode,io
                data=io.BytesIO();qrcode.make(pair['qr']).save(data,format='PNG')
                pixmap=QPixmap();pixmap.loadFromData(data.getvalue(),'PNG');image=QLabel();image.setPixmap(pixmap.scaled(300,300,Qt.AspectRatioMode.KeepAspectRatio));image.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(image)
            except ImportError:layout.addWidget(QLabel('Chưa có thư viện QR. Sao chép mã bên dưới để nhập trên Android.'))
            text=QPlainTextEdit(pair['qr']);text.setReadOnly(True);text.setMaximumHeight(100);layout.addWidget(text)
            toggle=QCheckBox('Nhận việc từ điện thoại khi ChatAI đang mở');toggle.setChecked(True);layout.addWidget(toggle)
            toggle.toggled.connect(lambda enabled:self.work(lambda emit:desktop_api(session,device,'enable',enabled=enabled)))
            screen_toggle=QCheckBox('Cho phép điện thoại yêu cầu ảnh màn hình trong phiên này')
            screen_toggle.setToolTip('Ảnh toàn màn hình có thể chứa dữ liệu của ứng dụng khác. Mặc định tắt; không tự chụp định kỳ.')
            layout.addWidget(screen_toggle)
            screen_toggle.toggled.connect(lambda enabled:setattr(self,'remote_screen_allowed',enabled))
            for link in links['links']:
                if link['revoked']:continue
                button=QPushButton('Thu hồi quyền: '+link['name']);layout.addWidget(button)
                button.clicked.connect(lambda checked=False,mobile=link['mobile'],b=button:self.work(
                    lambda emit:desktop_api(session,device,'revoke',mobile_id=mobile),lambda result,b=b:b.setEnabled(False)))
            close=QPushButton('Đóng');close.clicked.connect(dialog.accept);layout.addWidget(close)
            dialog.exec()
        self.work(setup,show)
    def remote_event(self,event):
        channel=self.remote_channel
        if not channel or self.sender() is not channel:return
        if not self.server_session or self.server_session['username']!=channel.session['username'] or self.server_session['endpoint']!=channel.session['endpoint']:return
        kind=event['type']
        if kind=='pairs':
            for pair in event['pairs']:
                if pair['id'] in self.remote_approval_seen:continue
                self.remote_approval_seen.add(pair['id'])
                yes=QMessageBox.question(self,'Ghép điện thoại',f"Cho phép {pair['mobile_name']} (mã {pair.get('mobile','')[:8]}) gửi việc, xem tiến trình và kết quả trên máy này?\nAI chỉ dùng quyền và thư mục đã cấp trong Cài đặt.")==QMessageBox.StandardButton.Yes
                import threading
                threading.Thread(target=self.remote_pair_decision,args=(channel,pair['id'],yes),daemon=True).start()
        elif kind=='capture':
            image=None
            if self.remote_screen_allowed:
                try:
                    screen=QApplication.primaryScreen()
                    pixmap=screen.grabWindow(0) if screen else QPixmap()
                    if not pixmap.isNull():
                        pixmap=pixmap.scaled(1600,1000,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
                        raw=QByteArray();buffer=QBuffer(raw);buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                        if pixmap.save(buffer,'JPEG',65) and raw.size()<=600000:
                            import base64
                            image=base64.b64encode(bytes(raw)).decode('ascii')
                        buffer.close()
                except Exception:pass
            channel.submit_capture(event['id'],image)
        elif kind=='task':
            self.remote_accept(event['task'])
        elif kind=='orphan':
            self.remote_task=event['task']
            channel.report('failed','Phiên thực thi cũ không còn xác minh được. Không tự chạy lại.',
                           'Kiểm tra mô hình và hội thoại trên Windows trước khi gửi tác vụ mới.')
        elif kind=='ack':
            if self.remote_task and self.remote_task['id']==event['id']:
                self.remote_task=None;self.remote_stop_action=None
        elif kind=='command' and self.remote_task and self.remote_task['id']==event['id']:
            action=event['action']
            if action in ('pause','cancel'):
                self.remote_stop_action=action
                if self.worker and self.worker.cancellable and self.worker.chat_cid==self.remote_task.get('cid'):
                    self.stop_windows_apps()
                    channel.report('running','Đang chờ thao tác hiện tại dừng tại điểm an toàn.',ack=action)
                else:channel.report('paused' if action=='pause' else 'cancelled','Đã dừng.',ack=action)
            else:
                if self.busy() or self.input.toPlainText().strip():
                    channel.report('needs_input','Máy đang có công việc hoặc bản nháp cục bộ. Thử Tiếp tục khi máy rảnh.',ack=action);return
                cid=self.remote_task.get('cid')
                if not cid:
                    channel.report('failed','Không còn ngữ cảnh để tiếp tục. Cần kiểm tra trên máy tính.',ack=action);return
                self.cid=cid;self.remote_stop_action=None;self.chat_mode.setCurrentIndex(1);self.render()
                reply=event.get('text','').strip()
                self.input.setPlainText(reply or 'Tiếp tục tác vụ từ trạng thái đã xác minh. Không lặp lại thao tác đã làm, không ghi đè mô hình đang mở.')
                channel.report('running','Đang tiếp tục tác vụ.',ack=action)
                self.send()
                if not self.worker:channel.report('needs_input','Cần thao tác hoặc bổ sung trên Windows.',ack=action)
    def remote_prepare_close(self,event):
        channel=self.remote_channel
        if channel and channel.isRunning():
            channel.set_ready(False);channel.stop();self.remote_exit_pending=True
            event.ignore();QTimer.singleShot(250,self.close);return False
        return True
    def remote_channel_ended(self,channel):
        if self.remote_channel is channel:
            self.remote_channel=None
            if not self.server_session or self.server_session['username']!=channel.session['username']:self.remote_task=None
        channel.deleteLater()
    def remote_pair_decision(self,channel,pair,approved):
        try:desktop_api(channel.session,channel.device,'approve',pair_id=pair,approve=approved)
        except Exception:channel.event.emit({'type':'connection','text':'Chưa lưu được xác nhận ghép nối. Tạo QR mới để thử lại.'})
    def remote_accept(self,task):
        self.remote_task=dict(task)
        channel=self.remote_channel
        if self.busy() or self.input.toPlainText().strip():
            channel.report('failed','Máy đang có công việc cục bộ; chưa thực hiện yêu cầu. Gửi lại khi máy rảnh.');return
        if re.search(r'plaxis',task['prompt'],re.I):
            try:
                if existing_plaxis_input():
                    channel.report('failed','PLAXIS Input đang mở; không bắt đầu tác vụ có thể thay thế mô hình.',
                                   'Lưu/đóng mô hình trên Windows hoặc chuẩn bị project riêng rồi gửi tác vụ mới.');return
            except Exception:
                channel.report('failed','Không kiểm tra được mô hình PLAXIS đang mở; chưa thực hiện yêu cầu.');return
        self.new_chat();self.remote_task['cid']=self.cid
        state=self.store.load(self.cid);state['remote_task_id']=task['id'];self.store.save(self.cid,state)
        self.chat_mode.setCurrentIndex(1)
        self.input.setPlainText(task['prompt']+'\n\n[Yêu cầu từ điện thoại đã ghép nối] Chỉ dùng quyền và thư mục đã cấp. '
            'Không ghi đè mô hình PLAXIS đang mở; nếu cần thay thế dữ liệu thì hỏi người dùng. '
            'Tự tra cứu, thực hiện và kiểm tra kết quả; báo rõ dữ kiện còn thiếu.')
        channel.report('running','Máy tính đã nhận và bắt đầu xử lý.')
        self.send()
        if not self.worker:channel.report('needs_input','Cần kiểm tra cấu hình hoặc bổ sung trên Windows: '+self.status.text())
    def remote_progress(self,event):
        if not self.remote_task or not self.remote_channel:return
        if not self.worker or self.worker.chat_cid!=self.remote_task.get('cid'):return
        if event.get('type')=='status':self.remote_channel.report('running',event.get('text',''))
    def remote_finished(self,worker):
        if not self.remote_task or not self.remote_channel or worker.chat_cid!=self.remote_task.get('cid') or self.worker:return
        state=self.store.load(worker.chat_cid)
        answer=next((m.get('content','') for m in reversed(state.get('messages',[])) if m.get('role')=='assistant'),'')
        if worker.failure:self.remote_channel.report('failed',str(worker.failure),answer)
        elif self.remote_stop_action:self.remote_channel.report('paused' if self.remote_stop_action=='pause' else 'cancelled','Đã dừng tác vụ.',answer)
        elif worker.cancelled:self.remote_channel.report('paused','Đã dừng trên Windows; chờ tiếp tục.',answer)
        elif state.get('pending'):
            pending=state['pending'];self.remote_channel.report('needs_input','AI cần bổ sung hoặc xác nhận. Xem hội thoại trên Windows.',answer or json.dumps(pending,ensure_ascii=False)[:48000])
        else:self.remote_channel.report('completed','Đã kết thúc lượt xử lý. Xem kết quả và các giới hạn AI báo bên dưới.',answer)

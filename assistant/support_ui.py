"""Desktop support pages and Cloudflare presentation; existing chat widgets stay intact."""
import base64
import html
import mimetypes
import threading
import uuid
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPlainTextEdit,
    QComboBox,QListWidget,QListWidgetItem,QTextBrowser,QMessageBox,QFileDialog,QDialog,QDialogButtonBox)
from .accounts import request_account
from .cloud import CLOUD_MODEL, NVIDIA_MODEL, REMOTE_MODELS, SWITCH_MESSAGE, CloudError, cloud_events, guest_token, ApiDocumentClient, api_key, api_answer_events, ServerApiClient
from .trial import GUEST_OWNER

HELP_GUIDE='''Chọn mô hình: NVIDIA AI (mặc định), DeepSeek API và Gemini API dùng key chung do Admin cấu hình trên server; người dùng chỉ chọn AI. Cloudflare xử lý nội dung trên server. Chọn Qwen hoặc DeepSeek để chạy trên máy; model chưa có sẽ hỏi trước khi tải.

Tìm kiếm mạng: bật nút Tìm kiếm mạng trước khi gửi. Khi tắt, AI không được tìm web.

Tài liệu: ưu tiên file đính kèm/RAG. Khi chọn Cloudflare, các đoạn văn bản được gửi tới server để tổng hợp; mô hình trên máy xử lý tại máy.

Office: chọn công cụ Office. Thư mục phải có trong danh sách được phép. Ghi/sửa/xóa/chạy lệnh cần xác nhận; sửa file có backup.

Bộ nhớ: đăng nhập để quản lý bộ nhớ riêng. Hãy kiểm tra nội dung trước khi lưu.

Hỗ trợ: gửi tiêu đề, mô tả lỗi và ảnh/tệp liên quan, tối đa 1 MB mỗi tin nhắn. Không gửi mật khẩu hoặc khóa truy cập. Log không được gửi tự động.

Cài đặt: bấm Lưu cài đặt để lưu; khi rời trang có thay đổi chưa lưu sẽ được hỏi.'''


def _reader_context(documents, limit=70000):
    """Đóng gói văn bản do Python trích xuất, giữ tên file và phạm vi đọc."""
    sections=[];remaining=limit
    for item in documents:
        name=str(item.get('file') or item.get('title') or 'Tài liệu')[:240]
        text=str(item.get('text') or '')
        header=(f"\n\n[TÀI LIỆU: {name}; định dạng: {item.get('format','không rõ')}; "
                f"phạm vi: {item.get('coverage','full_text' if item.get('full_text') else 'partial')}]\n")
        note=str(item.get('coverage_note') or '')
        issues=item.get('issues') or []
        if note:header+='Ghi chú trích xuất: '+note+'\n'
        if issues:header+='Vấn đề: '+'; '.join(str(x) for x in issues[:5])+'\n'
        available=max(0,remaining-len(header)-180)
        excerpt=text[:available]
        if len(excerpt)<len(text):
            excerpt+='\n[Đã trích văn bản bằng Python nhưng phần gửi đến AI bị giới hạn dung lượng; không xem phần còn lại là đã được AI đọc.]'
        if not excerpt and remaining<300:break
        sections.append(header+excerpt);remaining-=len(header)+len(excerpt)
        if remaining<300:break
    if len(sections)<len(documents):sections.append('\n[Không gửi được hết các tệp do giới hạn dung lượng ngữ cảnh.]')
    return ''.join(sections)


def _web_context(result, limit=70000):
    if not result:return 'Bing: chưa lấy được kết quả hoặc chưa đọc được trang nào.'
    sections=['Kết quả Bing và nội dung trang đã tải/đọc bằng Python.']
    remaining=limit
    for source in result.get('sources',[]):
        if not source.get('read'):continue
        page=next((x for x in result.get('pages',[]) if x.get('url')==source.get('url')),{})
        title=str(page.get('title') or source.get('title') or 'Trang web')[:300]
        url=str(page.get('url') or source.get('url') or '')[:2000]
        text=str(page.get('text') or '')
        header=f"\n\n[NGUỒN: {title}\nURL: {url}\nLoại: {page.get('format','web')}; phạm vi: {page.get('coverage','partial')}]\n"
        note=str(page.get('coverage_note') or '')
        if note:header+='Ghi chú: '+note+'\n'
        available=max(0,remaining-len(header)-180)
        excerpt=text[:available]
        if len(excerpt)<len(text):excerpt+='\n[Phần văn bản gửi cho AI bị giới hạn; không xem phần còn lại là đã đọc.]'
        if not excerpt and remaining<300:break
        sections.append(header+excerpt);remaining-=len(header)+len(excerpt)
        if remaining<300:break
    if result.get('note'):sections.append('\n\nTrạng thái đọc nguồn: '+str(result['note']))
    if not result.get('pages'):sections.append('\nChưa đọc được toàn văn trang web/PDF nào; không suy đoán rằng đã đọc.')
    return ''.join(sections)


class SupportMixin:
    def choose_other_model(self):
        dialog=QDialog(self);dialog.setWindowTitle('Chọn mô hình');layout=QVBoxLayout(dialog)
        layout.addWidget(QLabel(SWITCH_MESSAGE));combo=QComboBox()
        from .modules import CHAT_MODELS
        combo.addItems(list(CHAT_MODELS));combo.setCurrentText(self.cfg['default_model']);layout.addWidget(combo)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Dùng mô hình này')
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            model=combo.currentText();self.model.setCurrentText(model)
            if model not in self.models:self.download(model)
            self.input.setFocus()

    def cloud_chat_task(self,prompt):
        if self.busy():return
        cid=self.cid;session=dict(self.server_session) if self.server_session else None
        selected_model=self.model.currentText();provider=REMOTE_MODELS.get(selected_model,'cloudflare')
        cfg=dict(self.cfg)
        owner=session['username'] if session else GUEST_OWNER
        if self.store.load(cid).get('account_username') not in (None,owner):
            self.cid=self.store.create(persist=False);cid=self.cid
        self.store.remember_conversation(owner,cid)
        token=guest_token(self.store);endpoint=session['endpoint'] if session else self.cfg['server_url']
        use_web=self.chat_mode.currentIndex()==4
        use_deep=bool(getattr(self,'deep_analysis_enabled',False))
        attached_paths=list(self.pending_documents)
        attached_image=self.pending_image
        # Chụp tệp đính kèm trước khi ghi nhận tin nhắn trên máy; không chờ API để hiển thị.
        self.answer_actions.hide();self.reply_active=True;self.reply_dots.show();self.reply_timer.start()
        self.status.setText('Đang phân tích sâu; lượt này có thể lâu hơn…' if use_deep else ('Đang tìm kiếm mạng…' if use_web else 'Đang kết nối AI trên server…'))
        def run_chat(emit):
            state=self.store.load(cid)
            history=[{'role':m['role'],'content':m['content'][:1600]} for m in state['messages'] if m['role'] in ('user','assistant') and m.get('content')][-20:]
            state['account_username']=owner;state['model']=selected_model
            state['online_automation']=False
            state['messages'].append({'role':'user','content':prompt})
            state['running']=True;state['pending']=None;state['queue']=[]
            self.store.save(cid,state)
            emit({'type':'sent','cid':cid,'prompt':prompt})
            emit({'type':'snapshot','messages':[m for m in state['messages'] if m['role'] in ('user','assistant') and m.get('content')]})
            body={'text':prompt,'history':history,'guest_token':token,'web_search':use_web,'deep_analysis':use_deep}
            if attached_image:body['image']={'mime':'image/jpeg','data':attached_image}
            if use_web:
                body['search_query']=' '.join(prompt.split()[:70])[:500].strip()
            if session:body.update(username=session['username'],key=session['key'])
            api_client=ServerApiClient(session,provider,on_status=lambda text:emit({'type':'status','text':text}),cancel_event=getattr(self.worker,'stop_requested',None)) if provider!='cloudflare' else None
            import re
            document_request=bool(attached_paths or use_web or re.search(r'(?i)(tài liệu|file|pdf|docx|xlsx|pptx|dxf|tiêu chuẩn|nghị định|thông tư|báo cáo|điều khoản|số liệu|bài báo|quy chuẩn)',prompt))
            if api_client and document_request:
                from .cloud import CloudDocumentClient
                from .document_intent import analyze_intent
                from .document_pipeline import prepare_events, matching_recent_documents
                document_client=api_client
                emit({'type':'status','text':'Đang phân tích ý định tài liệu…'})
                attachments=self.read_attachments(attached_paths,online=True) if attached_paths else []
                conversation=history+[{'role':'user','content':prompt}]
                intent=analyze_intent(document_client,conversation,'document-small',bool(attachments),'document-small')
                if attachments:state['recent_documents']=attachments
                elif intent['target_type']=='document':attachments=matching_recent_documents(state.get('recent_documents',[]),intent)
                rag=None
                if self.manager.ready('rag'):
                    from .rag import RagTools
                    from .files import FileTools
                    rag=RagTools(FileTools(self.cfg['roots'],Path(self.store.path).parent/'backups',lambda *a:None),
                        self.client,Path(__file__).resolve().parents[1],lambda *a:None,owner=owner,storage_root=Path(self.store.path).parent,
                        vision_model=self.cfg.get('vision_model','gemma3:4b'))
                research_intent=dict(intent,target_type='document') if api_client and use_web and intent['target_type']!='document' else intent
                for event in prepare_events(document_client,'document-small',conversation,attachments,rag,use_web,intent=research_intent):
                    if event['type']=='document_result':
                        body['document_result']=event['result']
                        if attachments or use_web:
                            research=event['result']
                            contexts=[]
                            if attachments:contexts.append(_reader_context(attachments))
                            if use_web:contexts.append(_web_context(research))
                            body['document_context']='\n\n'.join(x for x in contexts if x)[:140000]
                        if use_web:
                            research=event['result']
                            emit({'type':'status','text':f"Tra cứu mạng: {research.get('search_successes',0)}/{research.get('search_attempts',0)} truy vấn thành công, {research.get('search_hits',0)} kết quả; {research.get('status','')}"})
                    else:emit(event)

            elif provider=='cloudflare' and (attached_paths or use_web):
                # Cloudflare streaming chỉ nhận văn bản, vì vậy desktop đọc PDF bằng
                # pypdf trước rồi gửi phần trích xuất kèm nguồn vào đúng lượt chat.
                evidence=[]
                if attached_paths:
                    emit({'type':'status','text':'Đang đọc PDF/tài liệu bằng Python…'})
                    attachments=self.read_attachments(attached_paths,online=True)
                    state['recent_documents']=attachments
                    evidence.append(_reader_context(attachments))
                if use_web:
                    # The Worker performs web search with BRAVE_SEARCH_API_KEY.
                    # This also works when the desktop cannot reach a search engine.
                    emit({'type':'status','text':'Đang tìm kiếm web trên Worker…'})
                body['document_context']='\n\n'.join(evidence)[:140000]

            body['options']={'num_predict':cfg.get('num_predict',1536),'temperature':cfg.get('temperature',.2),'num_ctx':cfg.get('num_ctx',4096)}
            events=api_answer_events(api_client,body) if api_client else cloud_events(endpoint,body)
            try:first=next(events)
            except CloudError as error:
                if error.code in ('CLOUD_LIMIT','CLOUD_BUSY','LOGIN_REQUIRED'):
                    return {'cloud_action':error.code,'message':str(error)}
                raise
            except StopIteration:raise RuntimeError('Server chưa trả về luồng AI.') from None
            emit({'type':'status','text':'Đang trả lời bằng AI trên server…'})
            answer=[];completed=False;failure=None;switch_required=False
            try:
                import itertools
                for event,value in itertools.chain([first],events):
                    if event=='meta' and value.get('memory_warning'):emit({'type':'status','text':value['memory_warning']})
                    elif event=='status':emit({'type':'status','text':value.get('text','AI đang xử lý…')})
                    if event=='delta':answer.append(value['text']);emit({'type':'token','text':value['text']})
                    elif event=='done':completed=True;switch_required=bool(value.get('switch_required'))
                if not completed:failure='Luồng AI kết thúc sớm. Phần trả lời đã nhận vẫn được giữ.'
            except Exception as error:failure=str(error)
            finally:
                events.close()
                if answer:state['messages'].append({'role':'assistant','content':''.join(answer)})
                state['running']=False;self.store.save(cid,state)
            if failure:emit({'type':'status','text':failure})
            return {'cloud_done':True,'message':failure or 'Hoàn tất','switch_required':switch_required}
        def task(emit):
            try:return run_chat(emit)
            finally:
                # Preparation/auth failures and cancellation must not leave a queued
                # user message marked running. The local message remains available.
                state=self.store.load(cid)
                if state.get('running'):
                    state['running']=False;self.store.save(cid,state)

        def done(result):
            if result.get('cloud_action'):
                if self.sent_prompt==prompt and not self.input.toPlainText().strip():
                    self.input.setPlainText(prompt);self.input.setFocus();self.sent_prompt=None
                self.status.setText(result['message'])
                if result['cloud_action']=='LOGIN_REQUIRED':self.login_dialog()
                # Keep the selected AI; quota/network errors do not force a model switch.
            else:
                self.status.setText(result['message'])
                # Ignore legacy Worker switch_required after a successful answer.
        self.work(task,done,cancellable=True)

    def open_support(self,checked=False):
        if not hasattr(self,'help_page'):
            page=QWidget();self.help_page=page;layout=QVBoxLayout(page)
            self.button(layout,'← Quay lại chat',lambda:self.tabs.setCurrentIndex(0))
            title=QLabel('Hỗ trợ');self.help_heading=title;title.setStyleSheet('font-size:22px;font-weight:600;');layout.addWidget(title)
            self.help_menu=QComboBox();self.help_menu.addItems(['Gửi yêu cầu hỗ trợ','Báo lỗi','Góp ý tính năng','Hướng dẫn sử dụng','Yêu cầu của tôi']);layout.addWidget(self.help_menu)
            self.help_form=QWidget();form=QVBoxLayout(self.help_form)
            self.help_issue=QComboBox();self.help_issue.addItems(['Đăng nhập','Tải model','AI trả lời','Lỗi ứng dụng']);form.addWidget(self.help_issue)
            self.help_title=QLineEdit();self.help_title.setPlaceholderText('Tiêu đề yêu cầu');self.help_title.setMaxLength(160);form.addWidget(self.help_title)
            self.help_text=QPlainTextEdit();self.help_text.setPlaceholderText('Mô tả yêu cầu. Không gửi mật khẩu hoặc khóa truy cập.');self.help_text.setMaximumHeight(150);form.addWidget(self.help_text)
            self.help_attachment_label=QLabel('Chưa có tệp đính kèm. Tối đa 1 MB mỗi tin nhắn.');form.addWidget(self.help_attachment_label)
            row=QHBoxLayout();self.button(row,'Đính kèm ảnh / tệp',self.attach_help_file);self.button(row,'Bỏ tệp',self.clear_help_file);form.addLayout(row)
            self.button(form,'Gửi đến quản trị viên',self.send_help_request);layout.addWidget(self.help_form)
            self.help_guide=QTextBrowser();self.help_guide.setPlainText(HELP_GUIDE);layout.addWidget(self.help_guide)
            self.help_filter=QComboBox();self.help_filter.addItems(['Tất cả','Chưa xử lý','Chưa đọc']);self.help_filter.currentIndexChanged.connect(self.filter_help_tickets);layout.addWidget(self.help_filter)
            self.help_threads=QListWidget();self.help_threads.itemClicked.connect(self.read_help_ticket);layout.addWidget(self.help_threads)
            self.button(layout,'Làm mới yêu cầu',self.refresh_help_tickets)
            self.help_view=QTextBrowser();self.help_view.setOpenLinks(False);self.help_view.anchorClicked.connect(self.save_help_attachment);layout.addWidget(self.help_view)
            self.help_reply=QPlainTextEdit();self.help_reply.setPlaceholderText('Trả lời yêu cầu đang chọn…');self.help_reply.setMaximumHeight(100);layout.addWidget(self.help_reply)
            self.help_reply_attachment_label=QLabel('');layout.addWidget(self.help_reply_attachment_label)
            self.help_reply_attach=self.button(layout,'Đính kèm phản hồi',self.attach_help_file)
            self.help_reply_button=self.button(layout,'Gửi phản hồi',self.reply_help_ticket)
            self.help_status=QComboBox();self.help_status.addItems(['Đã gửi','Đang xử lý','Đã trả lời','Đã đóng']);layout.addWidget(self.help_status)
            self.help_status_button=self.button(layout,'Áp dụng trạng thái',self.change_help_status)
            self.help_ticket=None;self.help_attachment=None;self.help_send_id=str(uuid.uuid4());self.help_reply_id=str(uuid.uuid4());self.help_downloads={}
            if not hasattr(self,'help_filter'):
                self.help_filter=QComboBox();self.help_filter.addItems(['Tất cả','Chưa xử lý','Chưa đọc']);self.help_filter.currentIndexChanged.connect(self.filter_help_tickets);layout.addWidget(self.help_filter)
            self.help_menu.currentIndexChanged.connect(self.select_help_section)
            self.add_scroll_page(page,'Hỗ trợ');self.help_page_index=self.tabs.count()-1;self.help_scroll=self.tabs.widget(self.help_page_index);self.select_help_section(0)
        from .admin_ui import admin_session
        admin=admin_session(self.server_session)
        self.help_heading.setText('Quản lý hỗ trợ' if admin else 'Hỗ trợ')
        self.help_menu.setItemText(4,'Yêu cầu người dùng' if admin else 'Yêu cầu của tôi')
        for index in range(3):self.help_menu.model().item(index).setEnabled(not admin)
        if admin:self.help_menu.setCurrentIndex(4)
        self.select_help_section(self.help_menu.currentIndex())
        self.tabs.setCurrentWidget(self.help_scroll)
        self.refresh_help_tickets()

    def select_help_section(self,index):
        self.help_form.setVisible(index<3);self.help_issue.setVisible(index==1)
        self.help_guide.setVisible(index==3);self.help_threads.setVisible(index==4)
        self.help_view.setVisible(index==4);self.help_reply.setVisible(index==4);self.help_reply_button.setVisible(index==4);self.help_reply_attach.setVisible(index==4);self.help_reply_attachment_label.setVisible(index==4)
        from .admin_ui import admin_session
        admin=admin_session(self.server_session)
        self.help_filter.setVisible(index==4 and admin)
        self.help_status.setVisible(index==4 and admin);self.help_status_button.setVisible(index==4 and admin)

    def support_request(self,path,body,callback):
        if self.busy():return
        if not self.server_session:self.login_dialog();return
        session=dict(self.server_session)
        payload=dict(body,username=session['username'],key=session['key'])
        self.work(lambda emit:request_account(session['endpoint'],path,payload,timeout=20),callback)

    def attach_help_file(self):
        path,_=QFileDialog.getOpenFileName(self,'Đính kèm ảnh hoặc tệp')
        if not path:return
        file=Path(path)
        if file.stat().st_size>1048576 or not file.stat().st_size:
            QMessageBox.warning(self,'Tệp hỗ trợ','Tệp cần có dữ liệu và không quá 1 MB.');return
        self.help_attachment={'name':file.name,'mime':mimetypes.guess_type(file.name)[0] or 'application/octet-stream','data':base64.b64encode(file.read_bytes()).decode()}
        self.help_attachment_label.setText('Đính kèm: '+file.name);self.help_reply_attachment_label.setText('Đính kèm: '+file.name)

    def clear_help_file(self):
        self.help_attachment=None;self.help_reply_attachment_label.setText('');self.help_attachment_label.setText('Chưa có tệp đính kèm. Tối đa 1 MB mỗi tin nhắn.')

    def send_help_request(self):
        title=self.help_title.text().strip();text=self.help_text.toPlainText().strip()
        if not title or not text or len(text)>4000:
            QMessageBox.warning(self,'Hỗ trợ','Nhập tiêu đề và nội dung không quá 4000 ký tự.');return
        if self.help_menu.currentIndex()==1:text='Loại lỗi: '+self.help_issue.currentText()+'\n'+text
        body={'id':self.help_send_id,'category':self.help_menu.currentText(),'title':title,'text':text,'attachment':self.help_attachment}
        def done(result):
            self.help_send_id=str(uuid.uuid4());self.help_title.clear();self.help_text.clear();self.clear_help_file()
            self.status.setText('Đã gửi yêu cầu đến quản trị viên.');self.help_menu.setCurrentIndex(4);self.refresh_help_tickets()
        self.support_request('/api/support/create',body,done)

    def refresh_help_tickets(self):
        if not self.server_session or not hasattr(self,'help_threads') or self.busy():return
        def done(result):
            self.help_tickets=result['items'];self.filter_help_tickets()
            from .admin_ui import admin_session
            label='Quản lý hỗ trợ' if admin_session(self.server_session) else 'Hỗ trợ'
            self.support_button.setText(label+(' ●' if any(t.get('unread') for t in result['items']) else ''))
        self.support_request('/api/support/list',{},done)

    def filter_help_tickets(self,*_):
        if not hasattr(self,'help_threads'):return
        from .admin_ui import admin_session,date_label
        admin=admin_session(self.server_session);index=self.help_filter.currentIndex() if admin else 0
        self.help_threads.clear()
        for ticket in getattr(self,'help_tickets',[]):
            if index==1 and ticket['status']!='Đã gửi':continue
            if index==2 and not ticket.get('unread'):continue
            text=ticket['title']+' · '+ticket['status']+(' · Chưa đọc' if ticket.get('unread') else '')
            if admin:text+='\n'+ticket['owner']+' · '+date_label(ticket.get('updated'))
            item=QListWidgetItem(text);item.setData(Qt.ItemDataRole.UserRole,ticket['id']);self.help_threads.addItem(item)

    def read_help_ticket(self,item):
        tid=item.data(Qt.ItemDataRole.UserRole)
        def done(result):
            self.help_ticket=result['ticket']['id'];self.help_downloads={};parts=[];self.clear_help_file()
            self.help_status.setCurrentText(result['ticket']['status'])
            for message in result['messages']:
                sender='Quản trị viên' if message['sender']!=result['ticket']['owner'] else ('Bạn' if self.server_session['username']==result['ticket']['owner'] else 'Người dùng: '+html.escape(result['ticket']['owner']))
                parts.append('<p><b>'+sender+'</b><br>'+html.escape(message['text']).replace('\n','<br>')+'</p>')
                attachment=message.get('attachment')
                if attachment:
                    self.help_downloads[message['id']]=attachment
                    parts.append('<p><a href="attachment:'+message['id']+'">Tải tệp: '+html.escape(attachment['name'])+'</a></p>')
            self.help_view.setHtml(''.join(parts));self.poll_support_badge()
        self.support_request('/api/support/read',{'id':tid},done)

    def reply_help_ticket(self):
        if not self.help_ticket:return
        text=self.help_reply.toPlainText().strip()
        if (not text and not self.help_attachment) or len(text)>4000:return
        def done(result):
            self.help_reply.clear();self.help_reply_id=str(uuid.uuid4());self.clear_help_file();self.refresh_help_tickets()
        self.support_request('/api/support/reply',{'id':self.help_ticket,'text':text,'message_id':self.help_reply_id,'attachment':self.help_attachment},done)

    def change_help_status(self):
        if self.help_ticket:self.support_request('/api/support/status',{'id':self.help_ticket,'status':self.help_status.currentText()},lambda result:self.refresh_help_tickets())

    def save_help_attachment(self,url):
        message_id=url.toString().removeprefix('attachment:')
        file=self.help_downloads.get(message_id)
        if not file:return
        path,_=QFileDialog.getSaveFileName(self,'Lưu tệp hỗ trợ',Path(file['name']).name)
        if not path:return
        def done(result):
            try:
                Path(path).write_bytes(base64.b64decode(result['file']['data'],validate=True))
                self.status.setText('Đã lưu tệp hỗ trợ.')
            except (OSError,ValueError) as error:QMessageBox.warning(self,'Lưu tệp',str(error))
        self.support_request('/api/support/attachment',{'id':self.help_ticket,'message_id':message_id},done)

    def poll_support_badge(self):
        if not self.server_session or getattr(self,'support_poll_active',False):return
        session=dict(self.server_session);self.support_poll_active=True
        if not hasattr(self,'presence_id'):self.presence_id=str(uuid.uuid4())
        def read():
            from .accounts import AccountAPIError
            presence={}
            try:
                presence=request_account(session['endpoint'],'/api/account/presence',{'username':session['username'],'key':session['key'],'presence_id':self.presence_id},timeout=8)
            except AccountAPIError as error:
                if error.status==401:
                    try:self.support_badge_finished.emit({'username':session['username'],'endpoint':session['endpoint'],'auth_failed':True})
                    except RuntimeError:pass
                    return
            except Exception:pass
            try:
                result=request_account(session['endpoint'],'/api/support/list',{'username':session['username'],'key':session['key']},timeout=8)
                value={'username':session['username'],'endpoint':session['endpoint'],'unread':any(t.get('unread') for t in result['items']),'verified_role':presence.get('role')}
            except Exception:value={}
            try:self.support_badge_finished.emit(value)
            except RuntimeError:pass
        threading.Thread(target=read,daemon=True).start()

    def apply_support_badge(self,value):
        self.support_poll_active=False
        session=self.server_session or {}
        if value.get('username')==session.get('username') and value.get('endpoint')==session.get('endpoint'):
            if value.get('auth_failed'):
                if self.busy():return
                from .accounts import forget_login
                try:forget_login()
                except OSError:pass
                self.server_session=None;self.personal_memories=[]
                self.cid=self.store.create(persist=False);self.render();self.status.setText('Phiên đăng nhập đã bị thu hồi, khóa hoặc hết hạn. Đăng nhập lại để tiếp tục.');return
            if value.get('verified_role') and value['verified_role']!=session.get('role'):
                session['role']=value['verified_role'];self.sync_support_identity()
            from .admin_ui import admin_session
            label='Quản lý hỗ trợ' if admin_session(session) else 'Hỗ trợ'
            self.support_button.setText(label+(' ●' if value.get('unread') else ''))

    def sync_support_identity(self):
        session=self.server_session or {}
        identity=(session.get('endpoint'),session.get('username'),session.get('role'))
        if identity==getattr(self,'support_visible_owner',None):return
        self.support_visible_owner=identity
        from .admin_ui import admin_session
        if hasattr(self,'support_button'):self.support_button.setText('Quản lý hỗ trợ' if admin_session(session) else 'Hỗ trợ')
        if hasattr(self,'admin_button'):self.admin_button.setVisible(admin_session(session))
        if hasattr(self,'help_threads'):
            admin=admin_session(session)
            self.help_heading.setText('Quản lý hỗ trợ' if admin else 'Hỗ trợ')
            self.help_menu.setItemText(4,'Yêu cầu người dùng' if admin else 'Yêu cầu của tôi')
            for index in range(3):self.help_menu.model().item(index).setEnabled(not admin)
            self.help_tickets=[]
            self.help_threads.clear();self.help_view.clear();self.help_reply.clear();self.help_title.clear();self.help_text.clear();self.help_ticket=None;self.help_downloads={};self.clear_help_file()
            self.help_send_id=str(uuid.uuid4());self.help_reply_id=str(uuid.uuid4());self.select_help_section(self.help_menu.currentIndex())

"""Qt actions for code blocks; the model never receives an executable save tool."""
import difflib
import html
import time
import uuid
from pathlib import Path
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication,QFileDialog,QMessageBox,QDialog,QVBoxLayout,
                              QLabel,QPlainTextEdit,QPushButton,QHBoxLayout,QInputDialog)
from .code_files import fences, suggested_name, source_record, CodeFiles
from .locking import execution_lock
from .config import ROOT


class CodeMixin:
    def render_code_content(self, content, markdown, message_index=None):
        blocks=fences(content)
        if not blocks:return markdown(content)
        output=[];start=0
        for block in blocks:
            output.append(markdown(content[start:block.start]))
            token=uuid.uuid4().hex
            key=str(message_index)+':'+block.digest
            self.code_actions[token]={'block':block,'index':message_index,'key':key}
            def action(name,label):
                return '<a href="chatai-code://'+name+'/'+token+'">'+label+'</a>'
            actions=action('copy','Đã sao chép' if self.copied_codes.get(key,0)>time.monotonic() else 'Sao chép')
            if block.complete and message_index is not None:
                actions+=' &nbsp; '+action('save','Lưu file')+' &nbsp; '+action('compare','So sánh với file gốc')
                saved=next((a for a in reversed(self.saved_code_files) if a.get('key')==key),None)
                if saved:
                    self.code_actions[token]['saved']=saved
                    actions+=' &nbsp; '+action('folder','Mở thư mục')
                    actions+='<br>📄 '+html.escape(Path(saved['path']).name)+' · Đã lưu'
            elif not block.complete:
                actions+=' · Đang viết…'
            output.append('<table width="100%" cellspacing="0" cellpadding="8"><tr><td><b>'+
                          html.escape(block.language[:40])+'</b> &nbsp; '+actions+'</td></tr><tr><td><pre>'+html.escape(block.code)+'</pre></td></tr></table><br>')
            start=block.end
        output.append(markdown(content[start:]))
        return ''.join(output)

    def handle_code_action(self,url):
        record=self.code_actions.get(url.path().lstrip('/'))
        if not record:return
        action=url.host()
        if action=='copy':
            QApplication.clipboard().setText(record['block'].code)
            self.copied_codes[record['key']]=time.monotonic()+2
            self.draw()
            QTimer.singleShot(2050,self.draw)
            return
        if self.busy():
            QMessageBox.information(self,'File mã nguồn','Đợi AI trả lời xong trước khi lưu hoặc sửa file.');return
        try:
            if action=='save':self.save_code_file(record)
            elif action=='compare':self.compare_code_file(record)
            elif action=='folder' and record.get('saved'):
                folder=Path(record['saved']['path']).parent
                if folder.is_dir():QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
                else:raise FileNotFoundError('Thư mục đã lưu không còn tồn tại.')
        except Exception as error:
            QMessageBox.warning(self,'File mã nguồn',str(error))

    def code_service(self):
        return CodeFiles(self.cfg['roots'],ROOT/'data/backups',lambda action,details:self.store.audit(self.cid,action,details))

    def save_code_file(self,record,source=None):
        if record['index'] is None or not record['block'].complete:return
        root=Path(self.cfg['roots'][0])
        default=root/suggested_name(record['block'].language,source['name'] if source else None)
        raw,_=QFileDialog.getSaveFileName(self,'Lưu file AI trả về',str(default),'File mã nguồn / văn bản (*)')
        if not raw:return
        state=self.store.load(self.cid)
        current_user=next((i for i in range(record['index']-1,-1,-1) if state['messages'][i]['role']=='user'),None)
        original=next((s for s in state.get('attachment_records',[]) if s.get('user_index')==current_user and Path(s['path']).resolve()==Path(raw).resolve()),None)
        plan=self.code_service().prepare(raw,record['block'].code,original)
        self.review_code_plan(record,plan)

    def review_code_plan(self,record,plan):
        dialog=QDialog(self);dialog.setWindowTitle('Xác nhận lưu file');dialog.resize(760,560)
        layout=QVBoxLayout(dialog)
        label=QLabel('File: '+plan['path']+'\nKiểm tra đây là toàn bộ nội dung cần lưu. File đã tồn tại sẽ được backup trước khi ghi đè.')
        label.setWordWrap(True);layout.addWidget(label)
        preview=QPlainTextEdit();preview.setReadOnly(True)
        preview.setPlainText(plan['diff'] or '(Nội dung không thay đổi)');layout.addWidget(preview)
        if len(plan['diff'])>=16000:layout.addWidget(QLabel('Bản so sánh bị rút gọn; hãy kiểm tra toàn bộ code trong chat.'))
        row=QHBoxLayout();layout.addLayout(row)
        cancel=QPushButton('Hủy');cancel.clicked.connect(dialog.reject);row.addWidget(cancel)
        save=QPushButton('Xác nhận ghi đè' if plan['sha256'] else 'Xác nhận lưu file');save.clicked.connect(dialog.accept);row.addWidget(save)
        cancel.setDefault(True)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        # Use the same interprocess lock as chat tools; recheck hash at commit.
        with execution_lock(ROOT/'data/agent.lock'):
            result=self.code_service().commit(plan)
            state=self.store.load(self.cid)
            item={'key':record['key'],'path':result['path'],'backup':result['backup']}
            state.setdefault('generated_files',[]).append(item)
            state['generated_files']=state['generated_files'][-100:]
            self.store.save(self.cid,state)
            self.saved_code_files=state['generated_files']
        self.status.setText('Đã lưu: '+result['path']);self.draw()

    def compare_code_file(self,record):
        state=self.store.load(self.cid)
        index=record['index']
        if index is None:return
        user_index=next((i for i in range(index-1,-1,-1) if state['messages'][i]['role']=='user'),None)
        sources=[s for s in state.get('attachment_records',[]) if s.get('user_index')==user_index]
        if not sources:
            QMessageBox.information(self,'So sánh','Tin nhắn này chưa có file mã nguồn UTF-8 để so sánh. Hãy đính kèm file gốc và yêu cầu AI trả lại toàn bộ file trong một khối code.')
            return
        source=sources[0]
        if len(sources)>1:
            labels=[s['name']+' · '+s['path'] for s in sources]
            value,ok=QInputDialog.getItem(self,'Chọn file gốc','File cần so sánh:',labels,0,False)
            if not ok:return
            source=sources[labels.index(value)]
        service=self.code_service();old=service.source_text(source)
        dialog=QDialog(self);dialog.setWindowTitle('So sánh với '+source['name']);dialog.resize(800,580)
        layout=QVBoxLayout(dialog)
        note='Chọn đúng khối chứa TOÀN BỘ file; không ghi đè bằng một đoạn ví dụ.'
        if source.get('truncated'):note+=' AI chỉ nhận trích đoạn; chỉ cho lưu bản mới.'
        label=QLabel(note);label.setWordWrap(True);layout.addWidget(label)
        diff=''.join(difflib.unified_diff(old.splitlines(True),record['block'].code.splitlines(True),fromfile=source['name'],tofile=suggested_name(record['block'].language,source['name'])))
        preview=QPlainTextEdit();preview.setReadOnly(True);preview.setPlainText(diff or '(Không có khác biệt)');layout.addWidget(preview)
        row=QHBoxLayout();layout.addLayout(row)
        cancel=QPushButton('Hủy');cancel.clicked.connect(dialog.reject);row.addWidget(cancel)
        new=QPushButton('Lưu bản mới');new.clicked.connect(lambda:dialog.done(2));row.addWidget(new)
        overwrite=QPushButton('Ghi đè file gốc');row.addWidget(overwrite)
        try:service.tools.path(source['path'])
        except PermissionError:overwrite.setEnabled(False);overwrite.setToolTip('File ngoài thư mục được phép; chỉ lưu bản mới trong whitelist.')
        if source.get('truncated'):overwrite.setEnabled(False)
        overwrite.clicked.connect(dialog.accept);cancel.setDefault(True)
        choice=dialog.exec()
        if choice==2:self.save_code_file(record,source)
        elif choice==QDialog.DialogCode.Accepted:
            plan=service.prepare(source['path'],record['block'].code,source)
            self.review_code_plan(record,plan)

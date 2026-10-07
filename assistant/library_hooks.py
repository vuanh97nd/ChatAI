"""Nối Thư viện tài liệu vào cửa sổ Chat AI mà không sửa desktop_ui.py / agent.py.

- Tự ghi nhớ: mọi tài liệu đính kèm sau khi đọc xong được lưu vào thư viện (theo tài khoản).
- Tự nhớ lại: trước mỗi lượt trả lời, tìm trong thư viện; đoạn liên quan được đưa vào
  "DỮ LIỆU THAM KHẢO" như kết quả tra tài liệu riêng.
- Nền: tạo vector (CPU) và đồng bộ với server D1 mỗi 10 phút hoặc khi bấm "Đồng bộ ngay".
- Thanh bên có mục "Thư viện tài liệu" để xem, tìm, quên tài liệu.
"""
import threading
import traceback

_STATE = {'window': None, 'libraries': {}, 'busy': threading.Lock(), 'last': ''}
STOP_WORDS = set('là và của có cho về một các những được không thì này đó trong với từ theo khi nào gì sao bao nhiêu hãy giúp tôi bạn mình'.split())


def _owner(win):
    session = getattr(win, 'server_session', None)
    if session and session.get('username'):
        return session['username']
    try:
        from .trial import GUEST_OWNER
        return GUEST_OWNER
    except Exception:
        return 'guest'


def library_for(win):
    from .library import Library
    owner = _owner(win)
    lib = _STATE['libraries'].get(owner)
    if lib is None:
        lib = Library(owner, client=getattr(win, 'client', None))
        _STATE['libraries'][owner] = lib
    return lib


def background(win, sync=True):
    """Tạo vector còn thiếu và đồng bộ; chạy trong luồng riêng, không chạm vào Qt."""
    def job():
        if not _STATE['busy'].acquire(blocking=False):
            return
        try:
            lib = library_for(win)
            try:
                lib.embed_pending(limit=3000)
            except Exception as error:
                _STATE['last'] = 'Chưa tạo được vector (cần model bge-m3 trong Ollama): ' + str(error)[:160]
            session = getattr(win, 'server_session', None)
            if sync and session and session.get('endpoint'):
                stats = lib.sync(session)
                if stats.get('pulled'):
                    lib.embed_pending(limit=3000)
                usage = stats.get('usage') or {}
                _STATE['last'] = ('Đồng bộ xong: gửi %d, nhận %d, xóa %d. Dung lượng server: %.1f/%d MB.' % (
                    stats['pushed'], stats['pulled'], stats['deleted'],
                    (usage.get('bytes') or 0) / 1048576, (usage.get('quota') or 0) // 1048576))
            elif sync:
                _STATE['last'] = 'Chưa đăng nhập server nên thư viện chỉ lưu trên máy này.'
        except Exception as error:
            _STATE['last'] = 'Đồng bộ thư viện chưa thành công: ' + str(error)[:200]
            print('Chat AI library:', traceback.format_exc()[-800:], flush=True)
        finally:
            _STATE['busy'].release()
    threading.Thread(target=job, daemon=True, name='chat-ai-library').start()


def _wrap_read_attachments(win):
    original = win.read_attachments

    def read_attachments(paths, progress=None):
        items = original(paths, progress)
        try:
            lib = library_for(win)
            remembered = 0
            for index, item in enumerate(items):
                path = item.get('source') or (paths[index] if index < len(paths) else None)
                if lib.remember(item, path):
                    remembered += 1
            if remembered:
                if progress:
                    progress(f'Đã ghi nhớ {remembered} tài liệu vào Thư viện.')
                background(win)
        except Exception:
            print('Chat AI library remember:', traceback.format_exc()[-800:], flush=True)
        return items

    win.read_attachments = read_attachments


def _patch_agent():
    from . import agent as agent_module
    Agent = agent_module.Agent
    if getattr(Agent.run, '_library', False):
        return
    original = Agent.run

    def run(self, state):
        try:
            recall(state)
        except Exception:
            print('Chat AI library recall:', traceback.format_exc()[-600:], flush=True)
        yield from original(self, state)

    run._library = True
    Agent.run = run


def recall(state):
    win = _STATE['window']
    if win is None or not state.get('running') or state.get('attached_documents'):
        return
    messages = state.get('messages', [])
    index = next((i for i in range(len(messages) - 1, -1, -1) if messages[i].get('role') == 'user'), None)
    if index is None or state.get('library_turn') == index:
        return
    state['library_turn'] = index
    question = str(messages[index].get('content') or '')
    words = [w for w in question.casefold().split() if w not in STOP_WORDS]
    if len(question) < 8 or len(words) < 2:
        return
    results = library_for(win).search(question, limit=4)
    def relevant(r):
        # Chỉ dùng khi chắc liên quan: trùng số hiệu, hoặc vừa trùng từ khóa vừa gần nghĩa, hoặc rất gần nghĩa.
        return r['code'] or (r['keyword'] and r['similarity'] >= 0.55) or r['similarity'] >= 0.68
    keep = [r for r in results if relevant(r)]
    if not keep:
        return
    state['rag_results'] = {
        'note': ('Các đoạn dưới đây lấy từ Thư viện tài liệu mà người dùng đã cho AI đọc trước đây. '
                 'Chỉ dùng khi liên quan câu hỏi; khi dùng hãy nêu tên tài liệu và vị trí (trang/đoạn).'),
        'sources': [{'source': r['source'], 'chunk': r['chunk'], 'text': r['text']} for r in keep]}
    state['rag_prepared'] = True
    state['library_hits'] = list(dict.fromkeys(r['source'] for r in keep))


def open_library(win):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
                                   QPlainTextEdit, QPushButton, QLabel, QMessageBox)
    lib = library_for(win)
    dialog = QDialog(win)
    dialog.setWindowTitle('Thư viện tài liệu')
    dialog.resize(860, 600)
    layout = QVBoxLayout(dialog)
    heading = QLabel('Tài liệu AI đã đọc và ghi nhớ. File đính kèm được tự động thêm vào đây; '
                     'các lần hỏi sau AI sẽ tự tra lại.')
    heading.setWordWrap(True)
    layout.addWidget(heading)
    search = QLineEdit()
    search.setPlaceholderText('Tìm theo tên, số hiệu hoặc nội dung…')
    layout.addWidget(search)
    row = QHBoxLayout()
    listing = QListWidget()
    detail = QPlainTextEdit()
    detail.setReadOnly(True)
    row.addWidget(listing, 2)
    row.addWidget(detail, 3)
    layout.addLayout(row, 1)
    status = QLabel(_STATE['last'] or 'Thư viện lưu trên máy và đồng bộ qua server Chat AI khi đã đăng nhập.')
    status.setWordWrap(True)
    status.setStyleSheet('color:#8f8f8f;font-size:12px;')
    layout.addWidget(status)
    buttons = QHBoxLayout()
    forget = QPushButton('Quên tài liệu này')
    sync = QPushButton('Đồng bộ ngay')
    close = QPushButton('Đóng')
    buttons.addWidget(forget)
    buttons.addStretch(1)
    buttons.addWidget(sync)
    buttons.addWidget(close)
    layout.addLayout(buttons)

    def fill():
        listing.clear()
        query = search.text().strip()
        docs = lib.documents()
        if query:
            hits = {r['doc'] for r in lib.search(query, limit=20, semantic=False)}
            from .library import fold
            folded = fold(query)
            docs = [d for d in docs if d['id'] in hits or folded in fold(d['title'] + ' ' + d['codes'] + ' ' + d['filename'])]
        for doc in docs:
            label = doc['title'] + (('  ·  ' + doc['codes'].split(', ')[0]) if doc['codes'] else '') + '  ·  ' + doc['created']
            item = QListWidgetItem(label)
            item.setData(256, doc)
            listing.addItem(item)
        total = len(lib.documents())
        heading.setText(f'{total} tài liệu đã ghi nhớ. File đính kèm được tự động thêm vào đây; các lần hỏi sau AI sẽ tự tra lại.')
        detail.setPlainText('' if listing.count() else 'Chưa có tài liệu phù hợp.')

    def show(item):
        if item is None:
            return
        doc = item.data(256)
        sync_state = 'Đã đồng bộ' if doc['synced'] else 'Chưa đồng bộ'
        detail.setPlainText(f"{doc['summary']}\n\nTệp: {doc['filename']}\nNgày ghi nhớ: {doc['created']}\n"
                            f"Số ký tự: {doc['chars']:,}\nTrạng thái: {sync_state}")

    def do_forget():
        item = listing.currentItem()
        if item is None:
            return
        doc = item.data(256)
        if QMessageBox.question(dialog, 'Quên tài liệu', f"AI sẽ quên \"{doc['title']}\" trên mọi máy đã đồng bộ. Tiếp tục?") != QMessageBox.StandardButton.Yes:
            return
        lib.forget(doc['id'])
        fill()
        background(win)

    def do_sync():
        status.setText('Đang đồng bộ thư viện…')
        background(win)
        QTimer.singleShot(4000, lambda: (status.setText(_STATE['last'] or 'Đang đồng bộ…'), fill()))

    listing.currentItemChanged.connect(lambda current, previous: show(current))
    search.textChanged.connect(lambda text: fill())
    forget.clicked.connect(do_forget)
    sync.clicked.connect(do_sync)
    close.clicked.connect(dialog.accept)
    fill()
    dialog.exec()


def attach(win):
    """Gọi một lần khi cửa sổ chính hiển thị."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QPushButton
    _STATE['window'] = win
    _wrap_read_attachments(win)
    _patch_agent()
    nav = win.new_btn.parentWidget().layout() if win.new_btn.parentWidget() else None
    if nav is not None:
        button = QPushButton('▤  Thư viện tài liệu')
        button.setToolTip('Tài liệu AI đã đọc và ghi nhớ')
        button.clicked.connect(lambda: open_library(win))
        position = nav.indexOf(win.history_search)
        nav.insertWidget(position + 1 if position >= 0 else 1, button)
        win.library_button = button
    timer = QTimer(win)
    timer.setInterval(10 * 60 * 1000)
    timer.timeout.connect(lambda: background(win))
    timer.start()
    win.library_timer = timer
    QTimer.singleShot(20000, lambda: background(win))

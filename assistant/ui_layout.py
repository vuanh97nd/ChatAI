"""Bố cục kiểu ChatGPT cho cửa sổ Chat AI, áp dụng sau khi cửa sổ được dựng.

Không sửa desktop_ui.py: module bọc QMainWindow.show, lần hiển thị đầu tiên của cửa sổ
chính (lớp Window) sẽ được sắp xếp lại. Lỗi ở bất kỳ bước nào đều được bỏ qua để app
vẫn chạy với bố cục cũ.
"""

ATTACH_FILTER = ('Tài liệu và ảnh (*.pdf *.docx *.xlsx *.pptx *.txt *.md *.csv *.html '
                 '*.png *.jpg *.jpeg *.webp *.bmp);;Tất cả tệp (*.*)')


def _find_layout(root_layout, widget):
    """Tìm layout con chứa trực tiếp widget."""
    if root_layout is None:
        return None
    if root_layout.indexOf(widget) >= 0:
        return root_layout
    for i in range(root_layout.count()):
        child = root_layout.itemAt(i).layout()
        found = _find_layout(child, widget)
        if found is not None:
            return found
    return None


def _containing_layout(widget):
    parent = widget.parentWidget()
    while parent is not None:
        found = _find_layout(parent.layout(), widget)
        if found is not None:
            return found
        parent = parent.parentWidget()
    return None


def _style(widget, css):
    widget.setStyleSheet(css)
    widget.setProperty('chatBaseStyle', css)


def _step(fn, win):
    try:
        fn(win)
    except Exception as error:  # không để lỗi bố cục làm hỏng app
        print('Chat AI ui_layout: bỏ qua bước', fn.__name__, '-', error, flush=True)


def _buttons(win, text):
    from PySide6.QtWidgets import QPushButton
    return [b for b in win.findChildren(QPushButton) if b.text() == text]


def _labels(win, prefix):
    from PySide6.QtWidgets import QLabel
    return [l for l in win.findChildren(QLabel) if l.text().startswith(prefix)]


def sidebar(win):
    rename = {'Trò chuyện': '◎  Trò chuyện', 'Chuyên gia': '✦  Chuyên gia', 'Hỗ trợ': '?  Hỗ trợ'}
    for button in win.sidebar.findChildren(type(win.new_btn)):
        if button.text() in rename:
            button.setText(rename[button.text()])
    win.delete_btn.hide()  # chuyển vào menu ⋯
    for label in _labels(win, 'Gần đây'):
        if label.text() == 'Gần đây':
            _style(label, 'color:#8f8f8f;font-size:12px;font-weight:600;padding:10px 12px 2px 12px;')


def header(win):
    from PySide6.QtWidgets import QPushButton, QMenu
    row = _containing_layout(win.conversation_title)
    index = row.indexOf(win.conversation_title)
    if index > 0:
        logo = row.itemAt(index - 1).widget()
        if logo is not None and logo.width() <= 40:
            logo.hide()
    _style(win.conversation_title, 'font-size:17px;font-weight:600;padding:0 6px;')
    anchor = None
    for text in ('↻', 'Cấu hình máy'):
        for button in _buttons(win, text):
            if _find_layout(row, button) is row:
                anchor = anchor or button
                button.hide()
    more = QPushButton('⋯')
    more.setToolTip('Tùy chọn khác')
    more.setFixedSize(38, 34)
    _style(more, 'QPushButton{font-size:18px;padding:0;border-radius:12px;} QPushButton::menu-indicator{image:none;width:0;}')
    menu = QMenu(more)
    menu.addAction('Xóa cuộc trò chuyện', win.delete_chat)
    menu.addAction('Xem toàn bộ lịch sử', win.full_history)
    menu.addAction('Nhật ký thao tác', win.show_audit)
    menu.addSeparator()
    menu.addAction('Kết nối lại Ollama', win.refresh_models)
    menu.addAction('Cấu hình máy và AI', lambda: win.open_settings_section('Cấu hình máy và AI'))
    more.setMenu(menu)
    position = row.indexOf(anchor) if anchor is not None else row.count()
    row.insertWidget(position, more)
    win.more_button = more


def welcome(win):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QPushButton
    _style(win.greeting, 'font-size:30px;font-weight:600;color:#ececec;')
    win.greeting.setAlignment(Qt.AlignmentFlag.AlignCenter)
    _style(win.welcome_subtitle, 'font-size:18px;color:#b4b4b4;margin-bottom:20px;')
    win.welcome_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    cards = {
        '▦  Xử lý Excel': '▦  Xử lý Excel\nĐọc, tính, tổng hợp bảng',
        '▤  Soạn tài liệu': '▤  Soạn tài liệu\nBáo cáo, công văn, email',
        '✦  Tạo hình ảnh': '✦  Tạo hình ảnh\nMô tả ảnh bạn muốn',
    }
    card_css = 'text-align:left;padding:12px 14px;border-radius:16px;font-size:13px;color:#b4b4b4;'
    row = None
    for old, new in cards.items():
        for button in _buttons(win, old):
            button.setText(new)
            button.setMinimumHeight(72)
            _style(button, card_css)
            row = row or _containing_layout(button)
    if row is not None:
        extra = [('▧  Tóm tắt tài liệu\nĐính kèm PDF, Word rồi hỏi', 'Tóm tắt tài liệu tôi đính kèm và nêu các ý chính.'),
                 ('⌘  Viết code\nPython, SQL, sửa lỗi', 'Viết hàm Python ')]
        for text, prompt in extra:
            button = QPushButton(text)
            button.setMinimumHeight(72)
            _style(button, card_css)
            button.clicked.connect(lambda checked=False, p=prompt: win.fill_prompt(p))
            row.insertWidget(0 if text.startswith('▧') else row.count(), button)
        row.setSpacing(10)
        for i in range(row.count()):
            row.setStretch(i, 1)


def composer(win):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QPushButton, QFileDialog
    win.input.setPlaceholderText('Hỏi bất kỳ điều gì…')
    win.input.setMinimumHeight(52)
    win.input.setMaximumHeight(180)
    actions = _containing_layout(win.image_btn)
    for text in ('Lịch sử', 'Nhật ký'):
        for button in _buttons(win, text):
            if _find_layout(actions, button) is actions:
                button.hide()

    def choose():
        paths, _ = QFileDialog.getOpenFileNames(win, 'Đính kèm tệp', '', ATTACH_FILTER)
        if paths:
            win.attach_files(paths)
            win.input.setFocus()

    attach = QPushButton('＋')
    attach.setToolTip('Đính kèm ảnh hoặc tài liệu (PDF, Word, Excel, PowerPoint, TXT)')
    attach.setAccessibleName('Đính kèm tệp')
    attach.setFixedSize(34, 34)
    _style(attach, 'font-size:18px;padding:0;border-radius:17px;')
    attach.clicked.connect(choose)
    actions.insertWidget(actions.indexOf(win.image_btn), attach)
    win.attach_btn = attach
    for hint in _labels(win, 'Enter để gửi'):
        hint.setText('Chat AI có thể mắc lỗi. Hãy kiểm tra các thông tin quan trọng.  ·  Enter gửi, Shift + Enter xuống dòng')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _style(hint, 'color:#8f8f8f;font-size:11px;background:transparent;')
    composer_widget = win.input.parentWidget()
    if composer_widget is not None and composer_widget.layout() is not None:
        composer_widget.layout().setContentsMargins(14, 10, 10, 10)
        composer_widget.layout().setSpacing(6)


def status(win):
    _style(win.status, 'color:#8f8f8f;font-size:12px;')
    _style(win.reply_dots, 'color:#ececec;background:#2f2f2f;font-size:20px;padding:4px;border-radius:14px;')


def chat_corners(win):
    """Bo tròn góc bong bóng tin nhắn của người gửi.

    Bản cũ lấy vị trí bằng frameBoundingRect, vốn tính theo khung cha nên bị lệch và tạo
    vệt đen đè lên chữ. Ở đây vị trí được lấy từ con trỏ ký tự đầu tiên trong bong bóng
    (luôn đúng toạ độ màn hình), kích thước lấy từ khung bảng, rồi tô 4 góc bằng màu nền.
    """
    from PySide6.QtGui import QPainter, QColor, QPainterPath, QTextTable
    from PySide6.QtCore import Qt, QRectF
    from assistant.themes import recolor
    view_class = type(win.view)
    if getattr(view_class, '_corner_fix', False):
        return
    base_paint = view_class.__mro__[1].paintEvent  # QTextBrowser.paintEvent

    def bubbles(frame, found):
        for child in frame.childFrames():
            if isinstance(child, QTextTable) and child.format().property(1048581) == True:
                found.append(child)
            bubbles(child, found)
        return found

    def paintEvent(self, event):
        base_paint(self, event)
        try:
            tables = bubbles(self.document().rootFrame(), [])
            if not tables:
                return
            theme = getattr(self.window(), 'preview_theme', 'dark')
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(recolor('#212121', theme)))
            layout = self.document().documentLayout()
            visible = QRectF(self.viewport().rect())
            try:
                for table in tables:
                    size = layout.frameBoundingRect(table).size()
                    fmt = table.format()
                    inset = fmt.cellPadding() + fmt.border() + fmt.padding()
                    caret = self.cursorRect(table.cellAt(0, 0).firstCursorPosition())
                    rect = QRectF(caret.left() - inset, caret.top() - inset, size.width(), size.height())
                    if rect.width() < 24 or rect.height() < 24 or not rect.intersects(visible):
                        continue
                    radius = min(16.0, rect.width() / 2, rect.height() / 2)
                    square = QPainterPath(); square.addRect(rect)
                    rounded = QPainterPath(); rounded.addRoundedRect(rect, radius, radius)
                    painter.drawPath(square.subtracted(rounded))
            finally:
                painter.end()
        except Exception:
            pass

    view_class.paintEvent = paintEvent
    view_class._corner_fix = True
    win.view.viewport().update()


def library(win):
    from .library_hooks import attach
    attach(win)


def apply(win):
    if getattr(win, '_chatgpt_layout', False):
        return
    win._chatgpt_layout = True
    for fn in (sidebar, header, welcome, composer, status, chat_corners, library):
        _step(fn, win)
    try:
        win.apply_theme(win.preview_theme, win.preview_font_size)
    except Exception:
        pass


def install():
    try:
        from PySide6.QtWidgets import QMainWindow
    except Exception:
        return
    for name in ('show', 'showNormal', 'showMaximized'):
        original = getattr(QMainWindow, name, None)
        if original is None or getattr(original, '_ui_layout', False):
            continue

        def make(original):
            def wrapper(self, *args, **kwargs):
                if type(self).__name__ == 'Window' and hasattr(self, 'conversation_title'):
                    apply(self)
                return original(self, *args, **kwargs)
            wrapper._ui_layout = True
            return wrapper

        try:
            setattr(QMainWindow, name, make(original))
        except Exception:
            pass

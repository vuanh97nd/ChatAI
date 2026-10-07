"""Small independent control window while the chat is minimized."""
import time
from PySide6.QtCore import Qt, Signal, QTimer, QSettings, QPoint
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QApplication


class AutomationPanel(QWidget):
    pauseRequested=Signal(bool)
    chatRequested=Signal()
    stopRequested=Signal()

    def __init__(self):
        super().__init__(None,Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle('ChatAI · Đang thao tác')
        self.setFixedWidth(390)
        layout=QVBoxLayout(self)
        self.label=QLabel('AI đang thao tác…');self.label.setWordWrap(True);layout.addWidget(self.label)
        row=QHBoxLayout();layout.addLayout(row)
        self.pause=QPushButton('Tạm dừng');row.addWidget(self.pause)
        chat=QPushButton('Mở chat');row.addWidget(chat)
        stop=QPushButton('Kết thúc');row.addWidget(stop)
        self.pause.clicked.connect(self.toggle_pause);chat.clicked.connect(self.chatRequested)
        stop.clicked.connect(self.stopRequested)
        self.paused=False;self.message='AI đang thao tác';self.started=time.monotonic()
        self.timer=QTimer(self);self.timer.timeout.connect(self.update_label)
        self._drag=None

    def begin(self,message):
        self.message=message;self.started=time.monotonic();self.paused=False
        self.pause.setText('Tạm dừng');self.pause.setEnabled(True)
        screen=QApplication.primaryScreen().availableGeometry()
        saved=QSettings('ChatAI','Desktop').value('automation_panel_position')
        point=saved if isinstance(saved,QPoint) else QPoint(screen.right()-self.width()-20,screen.bottom()-120)
        self.move(max(screen.left(),min(point.x(),screen.right()-self.width())),max(screen.top(),min(point.y(),screen.bottom()-self.sizeHint().height())))
        self.update_label();self.timer.start(1000);self.show()

    def update_label(self):
        status='Tạm dừng trước bước tiếp theo' if self.paused else self.message
        self.label.setText(f'{status} · {int(time.monotonic()-self.started)} giây')

    def toggle_pause(self):
        self.paused=not self.paused;self.pause.setText('Tiếp tục' if self.paused else 'Tạm dừng')
        self.pauseRequested.emit(self.paused);self.update_label()

    def end(self):
        self.timer.stop();self.hide()

    def closeEvent(self,event):
        # Closing the control window reveals chat, never abandons the worker.
        self.chatRequested.emit();event.ignore()

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self._drag=event.globalPosition().toPoint()-self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self._drag is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint()-self._drag)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if self._drag is not None:QSettings('ChatAI','Desktop').setValue('automation_panel_position',self.pos())
        self._drag=None;super().mouseReleaseEvent(event)

"""Windows desktop: event loop hoạt động ngay, nạp backend ở luồng nền."""
import faulthandler
import sys
import traceback
import time
import math
from assistant.performance import measure,record
LAUNCH_STARTED=time.monotonic()
from pathlib import Path
with measure('startup.project_path'):
    ROOT = Path(__file__).resolve().parent

def main():
    with measure('startup.crash_log'):
        (ROOT/'data').mkdir(exist_ok=True)
        crash_log=(ROOT/'data/crash.log').open('a',encoding='utf-8',buffering=1)
    faulthandler.enable(file=crash_log,all_threads=True)
    faulthandler.dump_traceback_later(30, repeat=True,file=crash_log)
    qt_import_started=time.monotonic()
    from assistant.runtime_compat import prepare_six
    prepare_six()
    from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QWidget, QVBoxLayout
    from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QRadialGradient
    from PySide6.QtCore import Qt, QThread, Signal, QTimer, QRectF
    record('startup.qt_import',time.monotonic()-qt_import_started)
    app = QApplication(sys.argv)
    app.setApplicationName('Chat AI')
    def report_error(error_type,error,tb):
        detail=''.join(traceback.format_exception(error_type,error,tb))
        crash_log.write(time.strftime('%Y-%m-%d %H:%M:%S')+'\n'+detail+'\n');crash_log.flush()
        print(detail,flush=True)
        # Report Python exceptions from Qt callbacks without requesting app.exit().
        QMessageBox.warning(None,'Chat AI gặp lỗi','Một thao tác gặp lỗi. Hãy gửi data\\crash.log để kiểm tra.\n'+str(error)[:500])
    sys.excepthook=report_error
    app.setWindowIcon(QIcon(str(ROOT/('chat_ai.ico' if (ROOT/'chat_ai.ico').is_file() else 'logo_chat_ai.png'))))
    class Loader(QThread):
        progress = Signal(str)
        def run(self):
            self.result, self.error = None, None
            try:
                self.progress.emit('Đang nạp giao diện · phiên bản 2.6.6…')
                with measure('startup.desktop_import'):
                    from desktop_ui import Window, prepare_context
                with measure('startup.prepare_context'):
                    self.result = (Window, prepare_context(self.progress.emit))
            except Exception:
                self.error = traceback.format_exc()
    class AnimatedLogo(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setFixedHeight(174)
            self.pixmap=QPixmap(str(ROOT/'logo_chat_ai.png'))
            self.started=time.monotonic(); self.ready=False
            self.animation=QTimer(self)
            self.animation.timeout.connect(self.update); self.animation.start(33)
        def paintEvent(self,event):
            elapsed=time.monotonic()-self.started
            pulse=(math.sin(elapsed*math.pi)+1)/2
            entrance=min(1,elapsed/.4)
            size=128*(.92+.08*entrance)
            y=self.height()/2-4*math.sin(elapsed*math.pi)
            painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setOpacity(entrance)
            glow=QRadialGradient(self.width()/2,y,84)
            glow.setColorAt(0,QColor(100,65,255,110 if self.ready else int(35+45*pulse)))
            glow.setColorAt(.65,QColor(36,149,255,int(25+30*pulse)))
            glow.setColorAt(1,QColor(36,149,255,0))
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(glow)
            painter.drawEllipse(QRectF(self.width()/2-84,y-84,168,168))
            painter.drawPixmap(QRectF((self.width()-size)/2,y-size/2,size,size),self.pixmap,QRectF(self.pixmap.rect()))
    class Splash(QWidget):
        loading = True
        def __init__(self):
            super().__init__()
            layout = QVBoxLayout(self); layout.setContentsMargins(36,28,36,28); layout.setSpacing(12)
            self.logo=AnimatedLogo(self); layout.addWidget(self.logo)
            title=QLabel('Chat AI'); title.setAlignment(Qt.AlignmentFlag.AlignCenter); title.setStyleSheet('font-size:26px;font-weight:600;'); layout.addWidget(title)
            self.heading=QLabel('Đang khởi động…'); self.heading.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(self.heading)
            self.dots=QLabel('●  ·  ·'); self.dots.setAlignment(Qt.AlignmentFlag.AlignCenter); self.dots.setStyleSheet('color:#80baff;font-size:20px;');layout.addWidget(self.dots)
            note=QLabel('Xin vui lòng đợi trong giây lát'); note.setAlignment(Qt.AlignmentFlag.AlignCenter); note.setStyleSheet('color:#b5bed0;font-size:14px;'); layout.addWidget(note)
            self.detail=QLabel(); self.detail.setWordWrap(True); self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter); self.detail.setStyleSheet('color:#99a5bb;font-size:12px;'); layout.addWidget(self.detail)
        def closeEvent(self,event):
            if self.loading:
                event.ignore(); self.detail.setText('Đang nạp dữ liệu. Vui lòng đợi để đóng an toàn.')
            else: event.accept()
    splash = Splash()
    splash.setWindowTitle('Chat AI — Đang khởi động')
    splash.setStyleSheet('background:#131722;color:#e8edf5;font:18px "Segoe UI";')
    splash.resize(480,430); splash.show()
    loader = Loader(); windows = []
    status = {'text':'Đang khởi động…','frame':0}
    started=time.monotonic()
    def progress(text):
        status['text']=text; print(text,flush=True)
    def tick():
        status['frame']=(status['frame']+1)%3
        splash.heading.setText('Đang khởi động')
        splash.dots.setText('  '.join('●' if i==status['frame'] else '·' for i in range(3)))
        splash.detail.setText('%s · %ds' % (status['text'],time.monotonic()-started))
    timer = QTimer(); timer.timeout.connect(tick); timer.start(350)
    def ready():
        timer.stop()
        try:
            if loader.error: raise RuntimeError(loader.error)
            Window, context = loader.result
            with measure('startup.build_window'):
                window = Window(context)
            windows.append(window)
            splash.heading.setText('Sẵn sàng'); splash.dots.setText('●  ●  ●'); splash.logo.ready=True
            def reveal():
                with measure('startup.show_window'):
                    window.showNormal(); window.raise_(); window.activateWindow()
                record('startup.total',time.monotonic()-LAUNCH_STARTED)
                splash.loading=False; splash.logo.animation.stop(); splash.close()
            QTimer.singleShot(450,reveal)
            print('Chat AI Desktop 2.6.6 đã mở.',flush=True)
        except Exception:
            error=traceback.format_exc(); print(error,flush=True)
            QMessageBox.critical(splash,'Không mở được Chat AI',error)
            splash.loading=False; splash.close(); app.exit(1)
        finally:
            faulthandler.cancel_dump_traceback_later()
    loader.progress.connect(progress); loader.finished.connect(ready)
    QTimer.singleShot(0,loader.start)
    return app.exec()

if __name__ == '__main__':
    sys.exit(main())

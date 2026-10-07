import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import threading
import unittest
from PySide6.QtWidgets import QApplication, QMainWindow
from assistant.automation_panel import AutomationPanel
from assistant.windows_apps import pause_automation, wait_automation, stop_automation, resume_automation


class PanelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def tearDown(self):resume_automation()

    def test_pause_resume_signals_and_close_reveals_chat(self):
        panel=AutomationPanel();signals=[]
        panel.pauseRequested.connect(signals.append)
        revealed=[];panel.chatRequested.connect(lambda:revealed.append(True))
        panel.begin('Đang mở Word');self.assertTrue(panel.isVisible())
        panel.toggle_pause();self.assertTrue(panel.paused)
        self.assertEqual(panel.pause.text(),'Tiếp tục')
        panel.toggle_pause();self.assertEqual(signals,[True,False])
        panel.close();self.assertEqual(revealed,[True])
        panel.end();self.assertFalse(panel.isVisible());self.assertFalse(panel.timer.isActive())
        panel.deleteLater()

    def test_pause_blocks_next_step_resume_and_stop_unblock(self):
        for resume in (lambda:pause_automation(False),stop_automation):
            resume_automation();pause_automation()
            passed=threading.Event()
            def task():wait_automation();passed.set()
            thread=threading.Thread(target=task);thread.start()
            self.assertFalse(passed.wait(.05))
            resume();self.assertTrue(passed.wait(1));thread.join(1)

    def test_chat_minimizes_and_returns_after_work_finishes(self):
        from desktop_ui import Window
        class Host(QMainWindow):
            compact_app_activity=Window.compact_app_activity
            pause_app_activity=Window.pause_app_activity
            reveal_app_chat=Window.reveal_app_chat
            finish_app_activity=Window.finish_app_activity
            end_app_activity=Window.end_app_activity
        host=Host();host.cfg={'windows_apps_compact':True};host.show()
        host.compact_app_activity('Đang thực hiện: windows_open')
        self.assertTrue(host.isMinimized())
        self.assertTrue(host.automation_panel.isVisible())
        host.automation_panel.toggle_pause()
        host.finish_app_activity()
        self.assertFalse(host.isMinimized());self.assertFalse(host.automation_panel.isVisible())
        self.assertFalse(host.app_compact_active)
        host.automation_panel.deleteLater();host.deleteLater()

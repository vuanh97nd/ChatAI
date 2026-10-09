import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QLineEdit
from PySide6.QtCore import QEventLoop, QTimer
from assistant.email_ui import EmailSettingsDialog


class EmailUITests(unittest.TestCase):
    def test_real_worker_loads_masked_configuration(self):
        app = QApplication.instance() or QApplication([])
        def request(*args, **kwargs):
            return {'config': {'enabled': True, 'from': 'test@example.com',
                               'name': 'ChatAI', 'secret_configured': True}}
        with patch('assistant.billing_ui.request_account', side_effect=request):
            dialog = EmailSettingsDialog({'endpoint': 'https://example.com',
                                          'username': 'admin', 'key': 'fixture'})
            loop = QEventLoop()
            timer = QTimer()
            timer.timeout.connect(lambda: loop.quit() if dialog.worker is None else None)
            timer.start(10)
            QTimer.singleShot(3000, loop.quit)
            loop.exec()
            timer.stop()
            try:
                self.assertIsNone(dialog.worker)
                self.assertTrue(dialog.panel.isEnabled())
                self.assertEqual(dialog.sender.text(), 'test@example.com')
                self.assertEqual(dialog.secret.text(), '')
                self.assertEqual(dialog.secret.echoMode(), QLineEdit.EchoMode.Password)
                finished = []
                dialog.finished.connect(finished.append)
                dialog.accept()
                self.assertEqual(finished, [dialog.DialogCode.Accepted.value])
            finally:
                if dialog.worker:
                    dialog.worker.wait(3000)
                    app.processEvents()
                dialog.close()

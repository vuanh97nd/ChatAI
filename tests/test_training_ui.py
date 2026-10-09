import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication,QWidget
from assistant.storage import Store
from assistant.training_ui import TrainingDialog


class TrainingUITests(unittest.TestCase):
    def test_admin_can_toggle_training_without_overriding_finished_signal(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            host=QWidget();host.store=Store(Path(tmp)/'a.db');host.cfg={'procedure_training_enabled':False}
            host.server_session={'username':'admin','endpoint':'https://example.org','key':'fixture'}
            host.set_training_mode=Mock();host.sync_procedures=Mock()
            dialog=TrainingDialog(host)
            try:
                dialog.mode.setChecked(True);host.set_training_mode.assert_called_once_with(True)
                self.assertIn('0 bản ghi',dialog.count.text())
                finished=[];dialog.finished.connect(finished.append);dialog.reject()
                self.assertEqual(finished,[dialog.DialogCode.Rejected.value])
            finally:dialog.close();host.close()

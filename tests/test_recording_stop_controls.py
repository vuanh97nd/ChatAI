import unittest
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication,QCheckBox
from assistant.automation_panel import AutomationPanel

class RecordingControlsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_panel_visibility_changes_never_request_stop(self):
        panel=AutomationPanel();stop=Mock();panel.stopRequested.connect(stop)
        panel.begin('Đang thao tác');panel.showMinimized();panel.hide();panel.showNormal()
        self.app.processEvents();panel.close();panel.end()
        stop.assert_not_called();panel.deleteLater()
    def test_permission_programmatic_refresh_does_not_emit_user_click(self):
        check=QCheckBox();clicked=Mock();check.clicked.connect(clicked)
        check.setChecked(True);check.setChecked(False);clicked.assert_not_called()
        check.setChecked(True);check.click();clicked.assert_called_once();self.assertFalse(check.isChecked())

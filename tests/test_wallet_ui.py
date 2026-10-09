import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QWidget
from assistant.wallet_ui import WalletButton


class WalletTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_balance_free_admin_and_failed_refresh(self):
        window=QWidget();window.server_session={'endpoint':'https://example.org','username':'alice','key':'fixture'}
        button=WalletButton(window);button.timer.stop()
        owner=('https://example.org','alice','fixture')
        button.received(owner,{'wallet':{'balance_vnd':10000}})
        self.assertIn('10.000 đ',button.text());self.assertIn('#ffb74d',button.styleSheet())
        button.received(owner,None)
        self.assertIn('Chưa cập nhật',button.text())
        button.received(owner,{'wallet':{'exempt':True}})
        self.assertIn('Miễn phí',button.text());self.assertEqual(button.styleSheet(),'')
        window.deleteLater()

    def test_old_account_result_is_discarded(self):
        window=QWidget();window.server_session=None
        button=WalletButton(window);button.timer.stop()
        with patch.object(button,'refresh') as refresh:
            button.received(('https://example.org','old','fixture'),{'wallet':{'balance_vnd':10000}})
            refresh.assert_called_once();self.assertIsNone(button.data)
        window.deleteLater()

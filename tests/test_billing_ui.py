import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QLineEdit
from assistant.billing_ui import BillingDialog,money


class BillingUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def dialog(self,admin=False):
        with patch.object(BillingDialog,'refresh'):
            return BillingDialog({'endpoint':'https://example.org','username':'admin' if admin else 'alice','key':'test','is_system':admin})

    def test_admin_form_and_secret_masking(self):
        dialog=self.dialog(True)
        try:
            self.assertEqual(dialog.tabs.count(),4)
            self.assertEqual(dialog.secret.echoMode(),QLineEdit.EchoMode.Password)
            dialog.received('/api/admin/billing/config/get',{'config':{'enabled':True,'bank':'VCB','account':'123456789','name':'Test','secret_configured':True,'webhook_url':'https://example.org/api/billing/webhook'}})
            self.assertEqual(dialog.secret.text(),'')
            self.assertTrue(dialog.enabled.isChecked())
            self.assertEqual(dialog.webhook.text(),'https://example.org/api/billing/webhook')
        finally:dialog.close()

    def test_user_trial_and_manual_retry_id(self):
        dialog=self.dialog()
        try:
            self.assertEqual(dialog.tabs.count(),3)
            dialog.received('/api/billing/status',{'success':True,'enabled':True,'wallet':{'owner':'alice','balance_vnd':20000,'available_vnd':19999.52,'held_vnd':.48,'trial_until':1791504000000,'service_until':0,'service_active':True},'orders':[],'usage':[]})
            self.assertIn('20.000 đ',dialog.summary.text())
            self.assertIn('19.999,52 đ',dialog.summary.text())
            self.assertTrue(dialog.topup.isEnabled())
        finally:dialog.close()
        admin=self.dialog(True)
        try:
            admin.target.setText('alice');admin.reason.setText('Chứng từ 1')
            with patch.object(admin,'send') as send:
                admin.manual_credit();first=send.call_args[0][1]['request_id']
                admin.manual_credit();self.assertEqual(send.call_args[0][1]['request_id'],first)
                admin.reason.setText('Chứng từ 2');admin.manual_credit();self.assertNotEqual(send.call_args[0][1]['request_id'],first)
        finally:admin.close()

    def test_money_keeps_sub_dong_precision(self):
        self.assertEqual(money(20000),'20.000 đ')
        self.assertEqual(money(.48),'0,48 đ')

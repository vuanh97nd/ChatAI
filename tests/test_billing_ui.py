import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QLineEdit
from PySide6.QtCore import QEventLoop,QTimer
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

    def test_real_worker_loads_admin_config_and_preserves_dialog_finished_signal(self):
        calls=[]
        def request(endpoint,path,body,timeout):
            calls.append(path)
            if path.endswith('/config/get'):
                return {'success':True,'config':{'enabled':False,'bank':'VCB','account':'123456789','name':'Test','secret_configured':False,'webhook_url':endpoint+'/api/billing/webhook'}}
            return {'success':True,'message':'Loaded'}
        dialog=self.dialog(True)
        loop=QEventLoop();timer=QTimer();timer.setInterval(10)
        def check():
            if dialog.worker is None and len(calls)==2:loop.quit()
        timer.timeout.connect(check)
        try:
            with patch('assistant.billing_ui.request_account',side_effect=request):
                dialog.refresh();timer.start();QTimer.singleShot(3000,loop.quit);loop.exec()
                self.assertIsNone(dialog.worker)
                self.assertEqual(calls,['/api/billing/status','/api/admin/billing/config/get'])
                self.assertTrue(dialog.tabs.isEnabled())
                self.assertEqual(dialog.bank.text(),'VCB')
                finished=[];dialog.finished.connect(finished.append)
                dialog.accept();self.assertEqual(finished,[dialog.DialogCode.Accepted.value])
        finally:
            timer.stop()
            if dialog.worker:
                dialog.worker.wait(3000);self.app.processEvents()
            dialog.close()

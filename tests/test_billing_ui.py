import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QLineEdit
from PySide6.QtCore import QEventLoop,QTimer
from assistant.billing_ui import BillingDialog,money


class BillingUITests(unittest.TestCase):
    def test_unknown_price_never_shows_default_and_zero_fee_disables_renewal(self):
        dialog=self.dialog()
        try:
            self.assertNotIn('100.000',dialog.plan_note.text())
            self.assertFalse(dialog.renew.isEnabled())
            dialog.failed('Server unavailable')
            self.assertNotIn('100.000',dialog.plan_note.text())
            dialog.received('/api/billing/status',{'service_fee':0,'price_per_million':4000})
            self.assertIn('Miễn phí duy trì',dialog.plan_note.text())
            self.assertEqual(dialog.renew.text(),'Miễn phí duy trì')
            self.assertFalse(dialog.renew.isEnabled())
        finally:dialog.close()

    def test_month_summary_switches_month_without_using_recent_request_list(self):
        dialog=self.dialog()
        try:
            dialog.received('/api/billing/status',{'monthly_usage':[
                {'month':'2026-10','tokens':2500000,'fee_vnd':10000,'unknown_requests':1},
                {'month':'2026-09','tokens':100,'fee_vnd':0,'unknown_requests':0}],
                'current_month':'2026-10','usage_updated_at':1791504000000})
            self.assertIn('2.500.000 token',dialog.month_summary.text())
            self.assertIn('10.000 đ',dialog.month_summary.text())
            self.assertIn('1 lượt',dialog.month_summary.text())
            dialog.usage_month.setCurrentIndex(1)
            self.assertIn('100 token',dialog.month_summary.text())
            self.assertIn('0 đ',dialog.month_summary.text())
        finally:dialog.close()

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

    def test_admin_pricing_can_waive_maintenance_and_raise_token_rate(self):
        admin=self.dialog(True)
        try:
            admin.fee_field.setValue(0);admin.token_price_field.setValue(12000)
            self.assertEqual(admin.fee_field.value(),0)
            with patch.object(admin,'send') as send:
                admin.save_config()
                config=send.call_args[0][1]['config']
                self.assertEqual(config['service_fee'],0);self.assertEqual(config['token_price'],12000)
            admin.received('/api/admin/billing/fee/save',{'success':True,'service_fee':0,'token_price':12000})
            self.assertIn('12.000 đ/triệu token',admin.plan_note.text())
            self.assertEqual(admin.renew.text(),'Miễn phí duy trì')
        finally:admin.close()
        user=self.dialog()
        try:
            user.received('/api/billing/status',{'enabled':True,'service_fee':0,'price_per_million':12000,'wallet':{'owner':'alice','balance_vnd':20000,'available_vnd':20000,'held_vnd':0,'trial_until':0,'service_until':0,'service_active':True,'maintenance_waived':True}})
            self.assertTrue(user.topup.isEnabled());self.assertFalse(user.renew.isEnabled())
        finally:user.close()

    def test_admin_user_table_shows_recorded_totals_and_waived_maintenance(self):
        from PySide6.QtWidgets import QWidget,QTabWidget,QPushButton
        from assistant.admin_ui import AdminMixin
        class AdminHarness(AdminMixin,QWidget):
            def __init__(self):
                super().__init__();self.tabs=QTabWidget(self);self.server_session={'role':'system'}
            def button(self,layout,label,callback):
                button=QPushButton(label);button.clicked.connect(callback);layout.addWidget(button)
            def add_scroll_page(self,page,label):self.tabs.addTab(page,label)
            def admin_request(self,action,body,callback):
                callback({'users':[{'fullname':'Alice','username':'alice','account_status':'active','expires_at':'Vĩnh viễn','billing':{'month_tokens':1300,'total_tokens':1800,'month_token_fee':8,'balance_vnd':19992,'pending_count':1,'maintenance_waived':True,'paid_total_tokens':1700,'free_total_tokens':100}}],'total':1})
        page=AdminHarness()
        try:
            page.open_user_admin()
            self.assertEqual(page.admin_table.columnCount(),14)
            self.assertEqual(page.admin_table.item(0,8).text(),'1,300')
            self.assertEqual(page.admin_table.item(0,9).text(),'1,800')
            self.assertEqual(page.admin_table.item(0,10).text(),'8 đ')
            self.assertEqual(page.admin_table.item(0,11).text(),'19.992 đ')
            self.assertEqual(page.admin_table.item(0,12).text(),'Miễn phí')
            self.assertEqual(page.admin_table.item(0,13).text(),'1')
        finally:page.close()

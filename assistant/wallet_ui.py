"""Small wallet summary in the chat toolbar, loaded without blocking Qt."""
from threading import Thread
from PySide6.QtCore import QTimer,Signal
from PySide6.QtWidgets import QPushButton,QMenu
from .accounts import request_account
from .billing_ui import money


class WalletButton(QPushButton):
    loaded=Signal(object,object)

    def __init__(self,window):
        super().__init__('Ví AI',window);self.window=window;self.data=None;self.owner=None;self.loading=False;self.error=False
        self.clicked.connect(self.show_wallet);self.loaded.connect(self.received)
        self.timer=QTimer(self);self.timer.setInterval(60000);self.timer.timeout.connect(self.refresh);self.timer.start()
        QTimer.singleShot(0,self.refresh)

    def refresh(self):
        session=getattr(self.window,'server_session',None)
        if not session:
            self.data=None;self.owner=None;self.setText('Ví AI');self.setStyleSheet('');return
        owner=(session['endpoint'],session['username'],session['key'])
        if owner!=self.owner:
            self.owner=owner;self.data=None;self.error=False;self.setText('Ví AI · Đang tải…');self.setStyleSheet('')
        if self.loading:return
        self.loading=True;session=dict(session)
        def load():
            try:result=request_account(session['endpoint'],'/api/billing/status',{'username':session['username'],'key':session['key']},timeout=15)
            except Exception:result=None
            finally:session.clear()
            try:self.loaded.emit(owner,result)
            except RuntimeError:pass
        Thread(target=load,daemon=True).start()

    def received(self,owner,result):
        self.loading=False
        session=getattr(self.window,'server_session',None)
        current=(session['endpoint'],session['username'],session['key']) if session else None
        if current!=owner:self.refresh();return
        self.error=result is None
        if self.error:
            self.setText('Ví AI · Chưa cập nhật');self.setToolTip('Không kết nối được server. Bấm để thử lại.');return
        self.data=result;wallet=result['wallet']
        self.setText('Ví AI · Miễn phí' if wallet.get('exempt') else 'Ví AI · '+money(wallet['balance_vnd']))
        self.setStyleSheet('color:#ffb74d;' if not wallet.get('exempt') and wallet['balance_vnd']<20000 else '')
        self.setToolTip('Xem số dư, sử dụng tháng này và nạp tiền')

    def show_wallet(self):
        if not getattr(self.window,'server_session',None):self.window.login_dialog();return
        self.refresh();menu=QMenu(self)
        if self.data:
            wallet=self.data['wallet'];menu.addAction('Admin miễn phí' if wallet.get('exempt') else 'Số dư: '+money(wallet['balance_vnd'])).setEnabled(False)
            month=self.data['current_month'];record=next((m for m in self.data['monthly_usage'] if m['month']==month),{'tokens':0,'fee_vnd':0})
            menu.addAction('Tháng '+month[5:]+'/'+month[:4]+f": {int(record['tokens']):,} token · "+money(record['fee_vnd'])).setEnabled(False)
        if self.error:menu.addAction('Chưa kết nối được; số liệu cũ chưa cập nhật').setEnabled(False)
        menu.addSeparator();menu.addAction('Nạp tiền',lambda:self.window.open_billing(topup=True));menu.addAction('Chi tiết sử dụng',self.window.open_billing)
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

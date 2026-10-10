"""Exercise production navigation methods with real Qt tab removal signals."""
import ast
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication,QTabWidget,QWidget,QStackedWidget,QPushButton,QSplitter

class SidebarNavigationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        tree=ast.parse((Path(__file__).parents[1]/'desktop_ui.py').read_text())
        window=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Window')
        methods=[n for n in window.body if isinstance(n,ast.FunctionDef) and n.name in ('balance_panels','remove_dynamic_page')]
        klass=ast.ClassDef(name='Navigation',bases=[],keywords=[],body=methods,decorator_list=[])
        ns={};exec(compile(ast.fix_missing_locations(ast.Module(body=[klass],type_ignores=[])),'navigation','exec'),ns)
        cls.Navigation=ns['Navigation']
    def setUp(self):
        self.ui=u=self.Navigation();u.tabs=QTabWidget()
        for i in range(9):u.tabs.addTab(QWidget(),str(i))
        u.sidebar=QWidget();u.sidebar_stack=QStackedWidget()
        for i in range(2):u.sidebar_stack.addWidget(QWidget())
        u.settings_button=QPushButton();u.settings_button.setCheckable(True)
        u.main_splitter=QSplitter();u.settings_last_tab=0
        u.profile_page_index=4;u.memory_page_index=5;u.work_support_page_index=6;u.help_page_index=7;u.admin_page_index=8
        u.tabs.setTabText(1,'Tải mô hình');u.tabs.setTabText(5,'Bộ nhớ cá nhân')
        u.active_settings_section='Nâng cao'
        u.settings_nav_buttons={}
        for title,section in [('Chung',None),('Nâng cao','Nâng cao')]:
            button=QPushButton();button.setCheckable(True);u.settings_nav_buttons[title]=(button,section)
            self.addCleanup(button.deleteLater)
        u.settings_page_buttons={}
        for title in ['Bộ nhớ cá nhân','Tải mô hình']:
            button=QPushButton();button.setCheckable(True);u.settings_page_buttons[title]=button
            self.addCleanup(button.deleteLater)
        u.tabs.currentChanged.connect(u.balance_panels)
        self.addCleanup(u.tabs.deleteLater);self.addCleanup(u.sidebar.deleteLater)
        self.addCleanup(u.sidebar_stack.deleteLater);self.addCleanup(u.settings_button.deleteLater);self.addCleanup(u.main_splitter.deleteLater)
    def test_sidebar_matches_all_page_types(self):
        u=self.ui
        for index in range(9):
            u.tabs.setCurrentIndex(index);u.balance_panels()
            self.assertEqual(u.sidebar_stack.currentIndex(),int(index in (1,3,4,5)))
            self.assertEqual(u.settings_button.isChecked(),index==3)
    def test_rebuilding_profile_or_memory_keeps_other_pages_reachable(self):
        u=self.ui;work=u.tabs.widget(6);help_page=u.tabs.widget(7);admin=u.tabs.widget(8)
        u.tabs.setCurrentIndex(6)
        u.remove_dynamic_page('profile_page_index')
        self.assertIsNone(u.profile_page_index)
        self.assertIs(u.tabs.widget(u.work_support_page_index),work)
        self.assertEqual(u.sidebar_stack.currentIndex(),0)

        u.remove_dynamic_page('memory_page_index')
        self.assertIs(u.tabs.widget(u.work_support_page_index),work)
        self.assertIs(u.tabs.widget(u.help_page_index),help_page)
        self.assertIs(u.tabs.widget(u.admin_page_index),admin)
        u.remove_dynamic_page('work_support_page_index')
        self.assertIsNone(u.work_support_page_index)
        self.assertIs(u.tabs.widget(u.help_page_index),help_page)
        self.assertIs(u.tabs.widget(u.admin_page_index),admin)
        u.balance_panels()
        self.assertEqual(u.sidebar_stack.currentIndex(),0)

    def test_highlight_follows_actual_memory_and_model_page(self):
        u=self.ui
        u.tabs.setCurrentIndex(3)
        self.assertTrue(u.settings_nav_buttons['Nâng cao'][0].isChecked())
        for index,title in [(5,'Bộ nhớ cá nhân'),(1,'Tải mô hình')]:
            u.tabs.setCurrentIndex(index)
            self.assertTrue(u.settings_page_buttons[title].isChecked())
            self.assertFalse(u.settings_nav_buttons['Nâng cao'][0].isChecked())
            self.assertEqual(sum(b.isChecked() for b in u.settings_page_buttons.values()),1)
        u.tabs.setCurrentIndex(3)
        self.assertTrue(u.settings_nav_buttons['Nâng cao'][0].isChecked())
        self.assertFalse(any(b.isChecked() for b in u.settings_page_buttons.values()))

"""Paint regression: a visible input must actually be drawn beneath its shadow."""
import ast
import unittest
from pathlib import Path
from unittest.mock import Mock
from PySide6.QtCore import QPoint,QPropertyAnimation,QEasingCurve
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QPlainTextEdit,QPushButton,QGraphicsDropShadowEffect,QGraphicsOpacityEffect
from PySide6.QtTest import QTest
from assistant.themes import style_sheet,recolor


class ComposerRenderingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        tree=ast.parse((Path(__file__).parents[1]/'desktop_ui.py').read_text())
        window=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Window')
        method=next(n for n in window.body if isinstance(n,ast.FunctionDef) and n.name=='apply_theme')
        namespace={'QWidget':QWidget,'QGraphicsOpacityEffect':QGraphicsOpacityEffect,'QPropertyAnimation':QPropertyAnimation,
                   'QEasingCurve':QEasingCurve,'style_sheet':style_sheet,'recolor':recolor,'re':__import__('re')}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),'theme-test','exec'),namespace)
        cls.apply_theme=staticmethod(namespace['apply_theme'])

    def setUp(self):
        self.win=QMainWindow();self.win.cfg={'font_size':13};self.win.html_cache={};self.win.apply_font=Mock()
        central=QWidget();self.win.setCentralWidget(central);root=QVBoxLayout(central);root.addStretch()
        composer=QWidget();composer.setObjectName('composer');composer.setGraphicsEffect(QGraphicsDropShadowEffect(composer))
        row=QVBoxLayout(composer)
        self.input=QPlainTextEdit();self.input.setObjectName('prompt');self.input.viewport().setObjectName('promptViewport')
        self.input.setFixedHeight(130);row.addWidget(self.input)
        self.send=QPushButton('↑');self.send.setObjectName('send');row.addWidget(self.send);root.addWidget(composer)
        self.apply_theme(self.win,'dark',13);self.win.resize(900,550);self.win.show();QTest.qWait(50)

    def tearDown(self):
        self.win.close();self.win.deleteLater();self.app.processEvents()

    def check_pixels(self,color):
        self.assertTrue(self.input.isVisible());self.assertTrue(self.send.isVisible())
        point=self.input.viewport().mapTo(self.win,QPoint(self.input.viewport().width()//2,self.input.viewport().height()//2))
        painted=self.win.grab().toImage()
        self.assertEqual(painted.pixelColor(point).name(),color)

    def test_input_is_painted_and_can_send_after_theme_transition_and_resize(self):
        self.input.setPlainText('Kiểm tra ô nhập')
        self.check_pixels('#303030')
        for theme,size,color in [('light',(760,480),'#ffffff'),('dark',(1500,850),'#303030')]:
            self.apply_theme(self.win,theme,16)
            self.assertIsNotNone(self.win._theme_animation) # transition retained
            self.assertEqual(self.win._theme_animation.propertyName(),b'windowOpacity')
            self.win.resize(*size);QTest.qWait(400)
            self.assertAlmostEqual(self.win.windowOpacity(),1.0,places=2)
            self.check_pixels(color)
            self.assertEqual(self.input.toPlainText(),'Kiểm tra ô nhập')
        clicked=Mock();self.send.clicked.connect(clicked);self.send.click();clicked.assert_called_once()

    def test_rapid_theme_changes_finish_on_last_requested_theme(self):
        self.apply_theme(self.win,'light',13)
        self.apply_theme(self.win,'dark',16)
        self.apply_theme(self.win,'light',18)
        QTest.qWait(400)
        self.assertEqual(self.win.preview_theme,'light');self.assertEqual(self.win.preview_font_size,18)
        self.assertAlmostEqual(self.win.windowOpacity(),1.0,places=2)
        self.check_pixels('#ffffff')

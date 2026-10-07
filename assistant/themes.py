"""Shared light/dark palettes for Qt widgets and rendered chat HTML.

Bản 2026-10-06: bảng màu trung tính kiểu ChatGPT (xám than, chữ sáng, nút gửi tròn
trắng), bo góc lớn, khoảng cách thoáng hơn. Giữ nguyên tên hàm và objectName cũ.
"""
import re

# Màu chế độ Tối -> màu tương ứng chế độ Sáng (mỗi màu tối dùng cho một vai trò).
LIGHT_COLORS = {
    '#212121':'#ffffff',  # nền chính
    '#ececec':'#0d0d0d',  # chữ chính
    '#171717':'#f9f9f9',  # thanh bên, nền code
    '#3d3d3d':'#e5e5e5',  # viền mảnh
    '#262626':'#ffffff',  # nền hộp nhóm/thẻ
    '#b4b4b4':'#5d5d5d',  # chữ phụ
    '#2a2a2a':'#ffffff',  # nền ô nhập
    '#454545':'#d9d9d9',  # viền ô nhập
    '#343434':'#ececec',  # mục đang chọn
    '#f5f5f5':'#0d0d0d',  # chữ mục đang chọn
    '#2c2c2c':'#f3f3f3',  # hover
    '#2f2f2f':'#f4f4f4',  # nền nút
    '#6b6b6b':'#a3a3a3',  # chữ bị vô hiệu
    '#1c1c1c':'#f1f1f1',  # nền bị vô hiệu
    '#7ab7ff':'#0b6bcb',  # liên kết / nhấn
    '#ededed':'#0d0d0d',  # nền nút gửi
    '#121212':'#ffffff',  # chữ nút gửi
    '#303030':'#ffffff',  # khung soạn tin
    '#4a4a4a':'#d0d0d0',  # viền khung soạn tin
    '#3b3b3b':'#e3e3e3',  # nút đang bật
    '#ffffff':'#0d0d0d',  # chữ nút đang bật
    '#323232':'#f4f4f4',  # bong bóng tin nhắn người dùng
    '#8f8f8f':'#8f8f8f',  # chữ mờ
    # Màu của giao diện cũ vẫn còn trong một số màn hình phụ (Hỗ trợ, Hồ sơ, Quản trị...).
    '#131314':'#fafaf8', '#e3e3e3':'#202124', '#1e1f20':'#f1f3f4', '#3c4043':'#dadce0',
    '#191a1c':'#ffffff', '#c4c7c5':'#3c4043', '#232426':'#ffffff', '#444746':'#dadce0',
    '#304159':'#dce8fc', '#d3e3fd':'#174ea6', '#303134':'#e8eaed', '#282a2c':'#e8f0fe',
    '#70757a':'#80868b', '#202124':'#f1f3f4', '#a8c7fa':'#1a73e8', '#062e6f':'#ffffff',
    '#2b3545':'#e8f0fe', '#9aa0a6':'#5f6368',
}

BASE_STYLE = """
QWidget {background:#212121;color:#ececec;font:14px "Segoe UI Variable Text","Segoe UI";}
QMainWindow, QDialog {background:#212121;}
QWidget#sidebar {background:#171717;border-right:1px solid #171717;}
QWidget#sidebar QLabel {background:transparent;color:#b4b4b4;}
QWidget#sidebar QPushButton {background:transparent;text-align:left;padding:9px 12px;border-radius:10px;color:#ececec;}
QWidget#sidebar QPushButton:hover {background:#2c2c2c;}
QWidget#sidebar QPushButton:checked {background:#343434;color:#f5f5f5;}

QLabel {background:transparent;}
QGroupBox {border:1px solid #3d3d3d;border-radius:16px;margin-top:20px;padding:20px 16px 16px 16px;background:#262626;}
QGroupBox::title {subcontrol-origin:margin;subcontrol-position:top left;padding:0 8px;color:#b4b4b4;font-weight:600;}

QLineEdit,QSpinBox,QDoubleSpinBox {background:#2a2a2a;border:1px solid #454545;border-radius:12px;padding:8px 10px;min-height:20px;selection-background-color:#7ab7ff;}
QLineEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus,QComboBox:focus,QPlainTextEdit:focus {border:1px solid #8f8f8f;}

QMenu {background:#2a2a2a;border:1px solid #3d3d3d;border-radius:14px;padding:6px;}
QMenu::item {padding:8px 18px;border-radius:8px;}
QMenu::item:selected {background:#343434;}
QMenu::separator {height:1px;background:#3d3d3d;margin:4px 8px;}

QTextBrowser#chatView {background:#212121;border:0;padding:12px 18px;font-size:16px;}
QPlainTextEdit,QTextBrowser,QListWidget,QComboBox {background:#2a2a2a;border:1px solid #3d3d3d;border-radius:12px;padding:8px 10px;}
QComboBox::drop-down {border:0;width:24px;}
QComboBox QAbstractItemView {background:#2a2a2a;color:#ececec;border:1px solid #3d3d3d;border-radius:10px;padding:4px;selection-background-color:#343434;selection-color:#f5f5f5;outline:0;}

QListWidget#history {background:transparent;border:0;outline:0;padding:4px 6px;}
QListWidget::item {padding:8px 10px;border-radius:10px;margin:1px 0;}
QListWidget::item:selected {background:#343434;color:#f5f5f5;}
QListWidget::item:hover {background:#2c2c2c;}

QPushButton {background:#2f2f2f;border:1px solid #3d3d3d;border-radius:18px;padding:8px 16px;color:#ececec;}
QPushButton:hover {background:#343434;}
QPushButton:pressed {background:#3b3b3b;}
QPushButton:checked {background:#3b3b3b;color:#ffffff;border:1px solid #8f8f8f;}
QPushButton:disabled {color:#6b6b6b;background:#1c1c1c;border:1px solid #1c1c1c;}
QPushButton#send {background:#ededed;color:#121212;border:0;border-radius:18px;font-weight:700;min-width:36px;max-width:36px;min-height:36px;max-height:36px;padding:0;}
QPushButton#send:hover {background:#b4b4b4;}
QPushButton#send:disabled {background:#3d3d3d;color:#6b6b6b;}

QWidget#composer {background:#303030;border:1px solid #4a4a4a;border-radius:26px;}
QWidget#composer QPushButton {background:transparent;border:1px solid #4a4a4a;border-radius:16px;padding:6px 12px;color:#b4b4b4;}
QWidget#composer QPushButton:hover {background:#3b3b3b;color:#ececec;}
QWidget#composer QPushButton:checked {background:#3b3b3b;color:#7ab7ff;border:1px solid #7ab7ff;}
QWidget#composer QPushButton#send {background:#ededed;color:#121212;border:0;}
QWidget#composer QPushButton#send:hover {background:#b4b4b4;}
QWidget#composer QPushButton#send:disabled {background:#4a4a4a;color:#6b6b6b;}
QPlainTextEdit#prompt {background:#303030;border:0;border-radius:0;font-size:16px;padding:2px 4px;}
QWidget#promptViewport {background:#303030;border:0;border-radius:0;padding:0;}

QTabBar::tab {padding:9px 16px;background:transparent;border-radius:12px;margin:4px;color:#b4b4b4;}
QTabBar::tab:selected {background:#343434;color:#f5f5f5;}
QTabBar::tab:hover {background:#2c2c2c;}
QTabWidget::pane {border:0;}
QSplitter::handle {background:#212121;width:1px;}

QScrollBar:vertical {background:transparent;width:10px;margin:2px;}
QScrollBar::handle:vertical {background:#454545;border-radius:4px;min-height:32px;}
QScrollBar::handle:vertical:hover {background:#6b6b6b;}
QScrollBar:horizontal {background:transparent;height:10px;margin:2px;}
QScrollBar::handle:horizontal {background:#454545;border-radius:4px;min-width:32px;}
QScrollBar::add-line,QScrollBar::sub-line {width:0;height:0;}
QScrollBar::add-page,QScrollBar::sub-page {background:transparent;}

QCheckBox {spacing:8px;background:transparent;}
QCheckBox::indicator {width:18px;height:18px;border-radius:5px;border:1px solid #6b6b6b;background:#2a2a2a;}
QCheckBox::indicator:checked {background:#7ab7ff;border:1px solid #7ab7ff;}

QProgressBar {border:1px solid #3d3d3d;border-radius:6px;background:#2a2a2a;text-align:center;}
QProgressBar::chunk {background:#7ab7ff;border-radius:5px;}
QToolTip {background:#2a2a2a;color:#ececec;border:1px solid #3d3d3d;border-radius:8px;padding:6px 8px;}
"""


def recolor(css, theme):
    if theme not in ('light', 'dark'):
        raise ValueError('Giao diện chỉ hỗ trợ Sáng hoặc Tối.')
    if theme == 'dark':return css
    return re.sub(r'#[0-9a-fA-F]{6}\b', lambda m: LIGHT_COLORS.get(m.group().lower(), m.group()), css)


def style_sheet(theme):
    return recolor(BASE_STYLE, theme)


def bubble_color(theme):
    return recolor('#323232', theme)


def chat_style(theme, font_size):
    css = ('body {color:#ececec;font-family:"Segoe UI Variable Text","Segoe UI";font-size:%dpx;line-height:1.6;} '
           'p, td, li, span {font-size:%dpx;} p {margin:10px 0;} li {margin:4px 0;} a {color:#7ab7ff;text-decoration:none;} '
           'h1 {font-size:%dpx;font-weight:600;} h2 {font-size:%dpx;font-weight:600;} h3, h4, h5, h6 {font-size:%dpx;font-weight:600;} '
           'code {font-family:"Cascadia Code","Consolas";background:#2f2f2f;} '
           'pre {background:#171717;font-family:"Cascadia Code","Consolas";white-space:pre-wrap;padding:12px;} '
           'th {background:#2f2f2f;} '
           'blockquote {color:#b4b4b4;margin-left:12px;}') % (font_size,font_size,font_size+5,font_size+3,font_size+1)
    return recolor(css, theme)


def normalize_chat_html(body):
    """Remove Qt-exported point sizes so saved chat size governs all messages."""
    return re.sub(r'font-size\s*:\s*[^;"\']+;?', '', body, flags=re.I)

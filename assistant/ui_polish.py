"""Tinh chỉnh nhỏ cho giao diện mà không sửa desktop_ui.py.

Bọc các hàm đặt chữ của Qt để tự sửa lỗi dính chữ-số (ví dụ "tối đa500" -> "tối đa 500").
Mọi lỗi đều được bỏ qua để không ảnh hưởng app.
"""
import re

FIXES = [
    (re.compile(r'tối đa(\d)'), r'tối đa \1'),
    (re.compile(r'Mỗi lượt(\d)'), r'Mỗi lượt \1'),
    (re.compile(r'tối thiểu(\d)'), r'tối thiểu \1'),
]


def fix_text(text):
    if not isinstance(text, str) or not text:
        return text
    for pattern, repl in FIXES:
        text = pattern.sub(repl, text)
    return text


def _wrap(cls, name):
    original = getattr(cls, name, None)
    if original is None or getattr(original, '_ui_polish', False):
        return

    def wrapper(self, text, *args, **kwargs):
        return original(self, fix_text(text), *args, **kwargs)

    wrapper._ui_polish = True
    setattr(cls, name, wrapper)


def install():
    try:
        from PySide6 import QtWidgets
    except Exception:
        return
    targets = [
        (QtWidgets.QPlainTextEdit, 'setPlaceholderText'),
        (QtWidgets.QLineEdit, 'setPlaceholderText'),
        (QtWidgets.QTextEdit, 'setPlaceholderText'),
        (QtWidgets.QLabel, 'setText'),
        (QtWidgets.QPushButton, 'setText'),
    ]
    for cls, name in targets:
        try:
            _wrap(cls, name)
        except Exception:
            pass

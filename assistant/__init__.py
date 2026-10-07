"""Chat AI: trợ lý local với module tùy chọn và tải dưới nền."""
from .vi_guard import install as _install_vi_guard
from .ui_polish import install as _install_ui_polish
from .ui_layout import install as _install_ui_layout

_install_vi_guard()
_install_ui_polish()
_install_ui_layout()

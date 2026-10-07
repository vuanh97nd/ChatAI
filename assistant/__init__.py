"""Chat AI: keep package imports light until the desktop runtime is ready."""
_initialized=False


def initialize_runtime():
    global _initialized
    if _initialized:return
    from .vi_guard import install as install_vi_guard
    from .ui_polish import install as install_ui_polish
    from .ui_layout import install as install_ui_layout
    install_vi_guard();install_ui_polish();install_ui_layout()
    _initialized=True

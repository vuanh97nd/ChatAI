"""Persist one task execution choice, independent of selected AI or conversation."""
def bind_checkbox(owner):
    box = owner.task_autonomy_check
    box.setToolTip('Quyền chung cho mọi AI, trong thư mục và công cụ đã cấp phép. Đổi AI hoặc hội thoại không làm mất quyền. Có thể tắt và dừng bất kỳ lúc nào.')
    def changed(enabled):
        from .config import save_config
        proposed = dict(owner.cfg, ai_tools_auto_execute=bool(enabled),
                        windows_apps_auto_execute=bool(enabled))
        try:
            saved = save_config(proposed)
        except Exception:
            previous = box.blockSignals(True)
            box.setChecked(owner.cfg.get('ai_tools_auto_execute',False))
            box.blockSignals(previous)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(owner,'Quyền tự thực hiện','Không lưu được quyền chung. Cấu hình trước được giữ nguyên; xem lại thư mục cấu hình.')
            return
        owner.cfg = saved
        for name in ('ai_tools_auto_check','windows_auto_execute_check'):
            control = getattr(owner,name,None)
            if control is not None:
                previous = control.blockSignals(True)
                control.setChecked(bool(enabled));control.blockSignals(previous)
    box.toggled.connect(changed)

"""AI self-repair tools: read logs, read/edit source code, check PLAXIS status.

All write operations require user approval and auto-backup before committing.
Only .py files inside the assistant/ directory can be edited.
"""
import difflib
import os
import shutil
import socket
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from .excel import digest

_SRC_ROOT = Path(__file__).resolve().parent
_SRC_SUFFIXES = {'.py'}
_SRC_MAX_SIZE = 200_000   # 200 KB per source file
_LOG_MAX_LINES = 500


def _src_path(raw: str) -> Path:
    """Validate and resolve a path that must be inside assistant/."""
    if not isinstance(raw, str) or not raw or len(raw) > 500:
        raise ValueError("Đường dẫn không hợp lệ.")
    p = Path(raw)
    if not p.is_absolute():
        p = (_SRC_ROOT / p).resolve()
    else:
        p = p.resolve()
    if not p.is_relative_to(_SRC_ROOT):
        raise PermissionError("Chỉ được đọc/sửa file trong thư mục assistant/.")
    if p.suffix.lower() not in _SRC_SUFFIXES:
        raise ValueError("Chỉ hỗ trợ file .py trong assistant/.")
    return p


class SourceTools:
    def __init__(self, backups_dir: Path, audit):
        self.backups = Path(backups_dir)
        self.backups.mkdir(parents=True, exist_ok=True)
        self.audit = audit

    # ── Read-only (no approval) ───────────────────────────────────────────────

    def log_read(self, lines: int = 50) -> dict:
        """Return last N lines from data/crash.log."""
        if not isinstance(lines, int) or not 1 <= lines <= _LOG_MAX_LINES:
            raise ValueError(f"lines phải trong khoảng 1–{_LOG_MAX_LINES}.")
        log_path = _SRC_ROOT.parent / 'data' / 'crash.log'
        if not log_path.exists():
            return {"path": str(log_path), "lines": [], "note": "Chưa có log lỗi."}
        text = log_path.read_text(encoding='utf-8', errors='replace')
        all_lines = text.splitlines()
        tail = all_lines[-lines:]
        return {
            "path": str(log_path),
            "total_lines": len(all_lines),
            "showing": len(tail),
            "lines": tail,
        }

    def source_read(self, path: str, start: int = 0, limit: int = 200) -> dict:
        """Read source file inside assistant/ (read-only, 1-indexed friendly)."""
        if not isinstance(start, int) or start < 0:
            raise ValueError("start phải là số nguyên không âm.")
        if not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("limit phải trong khoảng 1–500 dòng.")
        p = _src_path(path)
        if not p.is_file():
            raise ValueError(f"Không tìm thấy file: {p.name}")
        if p.stat().st_size > _SRC_MAX_SIZE:
            raise ValueError(f"File vượt {_SRC_MAX_SIZE // 1000} KB; đọc range nhỏ hơn.")
        content = p.read_text(encoding='utf-8-sig')
        all_lines = content.splitlines()
        chunk = all_lines[start:start + limit]
        return {
            "path": str(p.relative_to(_SRC_ROOT.parent)),
            "total_lines": len(all_lines),
            "start": start,
            "lines": chunk,
            "has_more": start + limit < len(all_lines),
            "next_start": start + limit,
        }

    def plaxis_status(self) -> dict:
        """Check whether Plaxis 2D Remote Scripting Server is reachable on localhost:10000."""
        reachable = False
        try:
            with socket.create_connection(('localhost', 10000), timeout=2):
                reachable = True
        except OSError:
            pass
        return {
            "reachable": reachable,
            "host": "localhost",
            "port": 10000,
            "note": (
                "PLAXIS 2D Remote Scripting Server đang chạy — có thể dùng tool plaxis_run_problem ngay."
                if reachable else
                "PLAXIS chưa bật. Mở PLAXIS 2D → Expert → Configure remote scripting server → Start (port 10000)."
            ),
        }

    # ── Write with approval ───────────────────────────────────────────────────

    def prepare_edit(self, path: str, search: str, replacement: str) -> dict:
        """Validate and prepare a source_edit plan for user approval."""
        p = _src_path(path)
        if not p.is_file():
            raise ValueError(f"Không tìm thấy file: {p.name}")
        if p.stat().st_size > _SRC_MAX_SIZE:
            raise ValueError("File quá lớn để sửa an toàn qua tool này.")
        if not isinstance(search, str) or not search.strip():
            raise ValueError("search không được rỗng.")
        if not isinstance(replacement, str):
            raise ValueError("replacement phải là chuỗi.")
        old = p.read_text(encoding='utf-8-sig')
        count = old.count(search)
        if count == 0:
            raise ValueError("Chuỗi cần sửa không tìm thấy trong file. Dùng source_read để xem nội dung trước.")
        if count > 1:
            raise ValueError(f"Chuỗi xuất hiện {count} lần; cần xuất hiện đúng 1 lần để sửa an toàn.")
        new_content = old.replace(search, replacement, 1)
        diff = "".join(difflib.unified_diff(
            old.splitlines(True), new_content.splitlines(True),
            fromfile=f"Trước: {p.name}", tofile=f"Sau: {p.name}",
        ))[:16000]
        return {
            "action": "source_edit",
            "path": str(p),
            "sha256": digest(p),
            "content": new_content,
            "diff": diff,
            "approval_id": uuid.uuid4().hex,
            "warning": "⚠️ Thao tác này sửa mã nguồn ứng dụng. Backup tự động trước khi ghi. Cần khởi động lại app sau khi sửa.",
        }

    def prepare_restore(self, path: str) -> dict:
        """Prepare source_restore: restore latest backup for user approval."""
        p = _src_path(path)
        stem = p.stem
        candidates = sorted(
            (f for f in self.backups.iterdir()
             if f.name.startswith(stem + '_') and f.suffix == '.py'),
            reverse=True,
        )[:5]
        if not candidates:
            raise ValueError(f"Không tìm thấy backup nào cho {p.name}.")
        latest = candidates[0]
        content = latest.read_text(encoding='utf-8-sig')
        old = p.read_text(encoding='utf-8-sig') if p.exists() else ""
        diff = "".join(difflib.unified_diff(
            old.splitlines(True), content.splitlines(True),
            fromfile=f"Hiện tại: {p.name}", tofile=f"Khôi phục từ: {latest.name}",
        ))[:16000]
        return {
            "action": "source_restore",
            "path": str(p),
            "sha256": digest(p) if p.exists() else None,
            "backup_used": str(latest),
            "content": content,
            "diff": diff,
            "approval_id": uuid.uuid4().hex,
            "available_backups": [f.name for f in candidates],
            "warning": "⚠️ Khôi phục sẽ ghi đè file hiện tại. Cần khởi động lại app sau khi khôi phục.",
        }

    def commit(self, plan: dict) -> dict:
        """Execute an approved source_edit or source_restore plan."""
        action = plan["action"]
        p = _src_path(plan["path"])
        current_sha = digest(p) if p.exists() else None
        if current_sha != plan["sha256"]:
            raise RuntimeError("File đã thay đổi sau khi preview; hãy xin duyệt lại.")
        self.audit("source_edit_started", {"action": action, "path": str(p)})
        # Auto-backup before write
        backup = None
        if p.exists():
            backup_name = f"{p.stem}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}{p.suffix}"
            backup = self.backups / backup_name
            shutil.copy2(p, backup)
            if digest(backup) != plan["sha256"]:
                raise RuntimeError("Backup không khớp; hủy thao tác.")
        # Atomic write via temp file
        fd, raw = tempfile.mkstemp(prefix=".source_edit_", dir=p.parent)
        temp = Path(raw)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
                f.write(plan["content"])
            if plan["sha256"] is None:
                with p.open("xb") as out, temp.open("rb") as inp:
                    shutil.copyfileobj(inp, out)
                temp.unlink(missing_ok=True)
            else:
                os.replace(temp, p)
            temp = None
        finally:
            if temp is not None and temp.exists():
                temp.unlink(missing_ok=True)
        self.audit("source_edit_done", {"action": action, "path": str(p),
                                        "backup": str(backup) if backup else None})
        return {
            "ok": True,
            "action": action,
            "path": str(p),
            "backup": str(backup) if backup else None,
            "note": "✅ Đã sửa thành công. Cần khởi động lại ứng dụng để áp dụng thay đổi.",
        }

import difflib
import os
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from .excel import digest

TEXT_SUFFIXES = {".txt", ".md", ".csv", ".tsv", ".json", ".yaml", ".yml", ".py", ".log", ".html", ".css", ".js"}


class FileTools:
    def __init__(self, roots, backups, audit):
        self.roots = [Path(p).resolve() for p in roots]
        self.backups, self.audit = Path(backups), audit
        self.backups.mkdir(parents=True, exist_ok=True)

    def path(self, raw, exists=True):
        if not isinstance(raw, str) or not raw or len(raw) > 1000:
            raise ValueError("Đường dẫn không hợp lệ.")
        p = Path(raw)
        if not p.is_absolute():
            p = self.roots[0] / p
        p = p.resolve(strict=exists)
        if not any(p.is_relative_to(r) for r in self.roots):
            raise PermissionError("Đường dẫn ngoài whitelist.")
        if any(part.startswith(".") for r in self.roots if p.is_relative_to(r)
               for part in p.relative_to(r).parts):
            raise PermissionError("Không thao tác file/thư mục ẩn trong bản này.")
        return p

    def file_list(self, path="."):
        p = self.path(path)
        if not p.is_dir():
            raise ValueError("Cần đường dẫn thư mục.")
        items = []
        for child in sorted(p.iterdir()):
            try:
                checked = self.path(str(child))
            except (OSError, PermissionError):
                continue
            items.append({"name": child.name, "path": str(checked),
                          "type": "directory" if checked.is_dir() else "file"})
            if len(items) == 100:
                break
        return {"path": str(p), "items": items, "limit": 100}

    def file_read(self, path):
        p = self.path(path)
        if not p.is_file() or p.suffix.lower() not in TEXT_SUFFIXES:
            raise ValueError("Chỉ đọc file text được hỗ trợ; Excel dùng tool riêng.")
        if p.stat().st_size > 1024**2:
            raise ValueError("File text tối đa 1 MiB.")
        content = p.read_text(encoding="utf-8-sig")
        return {"path": str(p), "content": content[:8000], "truncated": len(content) > 8000}

    def prepare(self, name, args):
        p = self.path(args["path"], exists=name != "file_write")
        if p in self.roots or (p.exists() and not p.is_file()):
            raise ValueError("Chỉ thao tác file, không sửa/xóa thư mục whitelist.")
        if p.exists() and p.stat().st_size > 20*1024**2:
            raise ValueError("File tối đa 20 MiB cho backup.")
        plan = {"action": name, "path": str(p), "sha256": digest(p) if p.exists() else None,
                "approval_id": uuid.uuid4().hex}
        if name in {"file_write", "file_edit"}:
            if p.suffix.lower() not in TEXT_SUFFIXES:
                raise ValueError("Ghi/sửa chỉ hỗ trợ file text.")
            old = p.read_text(encoding="utf-8-sig") if p.exists() else ""
            if len(old) > 200000:
                raise ValueError("Nội dung quá lớn để preview sửa.")
            if name == "file_write":
                content = args["content"]
            else:
                search, replacement = args["search"], args["replacement"]
                if not search or old.count(search) != 1:
                    raise ValueError("Chuỗi cần sửa phải xuất hiện đúng một lần.")
                content = old.replace(search, replacement, 1)
            if not isinstance(content, str) or len(content) > 100000:
                raise ValueError("Nội dung ghi tối đa 100000 ký tự.")
            if not p.parent.is_dir():
                raise ValueError("Thư mục cha phải có sẵn.")
            plan["content"] = content
            plan["diff"] = "".join(difflib.unified_diff(old.splitlines(True), content.splitlines(True),
                                                       fromfile="Trước", tofile="Sau"))[:16000]
        elif name == "file_move":
            dest = self.path(args["destination"], exists=False)
            if dest.exists() or not dest.parent.is_dir():
                raise ValueError("Đích phải chưa tồn tại và có thư mục cha.")
            plan["destination"] = str(dest)
        elif name != "file_delete":
            raise ValueError("Thao tác không được hỗ trợ.")
        return plan

    def commit(self, plan):
        action = plan["action"]
        p = self.path(plan["path"], exists=plan["sha256"] is not None)
        actual = digest(p) if p.exists() else None
        if actual != plan["sha256"]:
            raise RuntimeError("File thay đổi sau preview; hãy xin duyệt lại.")
        backup = None
        self.audit("file_started", {"action": action, "path": str(p)})
        if p.exists():
            backup = self.backups / f"{p.stem}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}{p.suffix}"
            shutil.copy2(p, backup)
            if digest(backup) != plan["sha256"]:
                raise RuntimeError("Backup không khớp; hủy thao tác.")
        temp = None
        try:
            if action in {"file_write", "file_edit"}:
                fd, raw = tempfile.mkstemp(prefix=".assistant_", dir=p.parent)
                temp = Path(raw)
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as output:
                    output.write(plan["content"])
                # Kiểm tra lại trước ghi để phát hiện thay đổi phổ biến từ bên ngoài.
                if (digest(p) if p.exists() else None) != plan["sha256"]:
                    raise RuntimeError("File thay đổi trước khi ghi.")
                if plan["sha256"] is None:
                    # Exclusive create: không đè file xuất hiện sau preview.
                    with p.open("xb") as output, temp.open("rb") as inp:
                        shutil.copyfileobj(inp, output)
                else:
                    os.replace(temp, p)
            elif action == "file_move":
                dest = self.path(plan["destination"], exists=False)
                if dest.exists():
                    raise RuntimeError("Đích đã xuất hiện; không ghi đè.")
                # Exclusive copy rồi xóa nguồn, dùng được giữa các ổ Windows.
                with dest.open("xb") as output, p.open("rb") as inp:
                    shutil.copyfileobj(inp, output)
                if digest(dest) != plan["sha256"] or digest(p) != plan["sha256"]:
                    raise RuntimeError("File thay đổi khi di chuyển. Kiểm tra cả nguồn và đích.")
                p.unlink()
            else:
                if digest(p) != plan["sha256"]:
                    raise RuntimeError("File thay đổi trước khi xóa.")
                p.unlink()
            result = {"ok": True, "action": action, "path": str(p),
                      "backup": str(backup) if backup else None,
                      "destination": plan.get("destination")}
            self.audit("file_success", result)
            return result
        except Exception as exc:
            self.audit("file_failed", {"path": str(p), "error": str(exc), "backup": str(backup)})
            raise
        finally:
            if temp:
                temp.unlink(missing_ok=True)

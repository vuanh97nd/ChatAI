import hashlib
import math
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from datetime import date, datetime
from pathlib import Path

def load_workbook(*args, **kwargs):
    try:
        from openpyxl import load_workbook as load
    except ImportError as error:
        raise RuntimeError('Chưa có thư viện Excel. Bật/Tải module Office trước.') from error
    return load(*args, **kwargs)


def coordinate_to_tuple(*args):
    from openpyxl.utils.cell import coordinate_to_tuple as convert
    return convert(*args)


def range_boundaries(*args):
    from openpyxl.utils.cell import range_boundaries as convert
    return convert(*args)

MAX_FILE = __import__('sys').maxsize
MAX_EXPANDED = 100 * 1024 * 1024
MAX_CELLS = 50_000_000


def scalar(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return scalar(value.item())
    return value


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class ExcelTools:
    def __init__(self, roots, backups, audit):
        self.roots = [Path(p).resolve() for p in roots]
        self.backups = Path(backups).resolve()
        self.backups.mkdir(parents=True, exist_ok=True)
        self.audit = audit

    def path(self, raw):
        if not isinstance(raw, str) or not raw or len(raw) > 1000:
            raise ValueError("Đường dẫn không hợp lệ.")
        p = Path(raw)
        if not p.is_absolute():
            p = self.roots[0] / p
        # resolve() theo symlink/junction trước khi kiểm tra containment.
        p = p.resolve(strict=True)
        if not any(p.is_relative_to(root) for root in self.roots):
            raise PermissionError("File nằm ngoài whitelist.")
        if not p.is_file() or p.suffix.lower() != ".xlsx":
            raise ValueError("Giai đoạn 1 chỉ hỗ trợ file .xlsx có sẵn.")
        if p.stat().st_size > MAX_FILE:
            raise ValueError("File vượt giới hạn 20 MiB.")
        with zipfile.ZipFile(p) as archive:
            if sum(i.file_size for i in archive.infolist()) > MAX_EXPANDED:
                raise ValueError("Workbook giải nén vượt 100 MiB.")
        return p

    def excel_list_files(self):
        """Liệt kê tối đa 100 file XLSX ở cấp đầu tiên của mỗi thư mục whitelist."""
        files = []
        for root in self.roots:
            for p in sorted(root.glob("*.xlsx")):
                try:
                    checked = self.path(str(p))
                except (ValueError, PermissionError, OSError, zipfile.BadZipFile):
                    continue
                files.append(str(checked))
                if len(files) >= 100:
                    return {"files": files, "truncated": True}
        return {"files": files, "truncated": False}

    def excel_list_sheets(self, path):
        p = self.path(path)
        wb = load_workbook(p, read_only=True, data_only=False, keep_links=False)
        try:
            return {"path": str(p), "sheets": wb.sheetnames}
        finally:
            wb.close()

    def excel_read(self, path, sheet, cell_range="A1:J20"):
        if not isinstance(cell_range, str) or not re.fullmatch(
                r"[A-Za-z]{1,3}[1-9][0-9]*:[A-Za-z]{1,3}[1-9][0-9]*", cell_range):
            raise ValueError("Range phải có dạng A1:D20.")
        left, top, right, bottom = range_boundaries(cell_range.upper())
        if (right < left or bottom < top or right > 16384 or bottom > 100000
                or (right-left+1) * (bottom-top+1) > 5000):
            raise ValueError("Range tối đa 5000 ô, không quá hàng 100000.")
        p = self.path(path)
        wb = load_workbook(p, read_only=True, data_only=False, keep_links=False)
        try:
            ws = wb[sheet]
            rows = [[scalar(c) for c in row] for row in ws.iter_rows(
                min_row=top, max_row=bottom, min_col=left, max_col=right, values_only=True)]
            return {"path": str(p), "sheet": sheet, "range": cell_range,
                    "rows": rows, "note": "Ô công thức trả biểu thức, không tự tính Excel."}
        finally:
            wb.close()

    def excel_summary(self, path, sheet):
        import pandas as pd
        p = self.path(path)
        wb = load_workbook(p, read_only=True, data_only=True, keep_links=False)
        try:
            ws = wb[sheet]
            height, width = ws.max_row or 0, ws.max_column or 0
            if height * width > MAX_CELLS or width > 200 or height > 100000:
                raise ValueError("Sheet quá lớn để tóm tắt: tối đa 200000 ô / 200 cột.")
            # Giới hạn số ô thực tế kể cả khi dimension trong XLSX sai.
            rows = []
            count = 0
            for row in ws.iter_rows(values_only=True):
                count += len(row)
                if count > MAX_CELLS or len(row) > 200:
                    raise ValueError("Dữ liệu thực tế vượt giới hạn tóm tắt.")
                rows.append([scalar(c) for c in row])
        finally:
            wb.close()
        if not rows:
            return {"path": str(p), "sheet": sheet, "rows": 0, "columns": []}
        # Giả định hàng 1 là header; label theo vị trí tránh header trùng tên.
        frame = pd.DataFrame(rows[1:], columns=list(range(len(rows[0]))))
        columns = []
        for i in frame.columns:
            series = frame[i]
            result = {"position": int(i)+1, "header": scalar(rows[0][i]),
                      "missing": int(series.isna().sum()), "dtype": str(series.dtype)}
            if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
                result["stats"] = {k: scalar(v) for k, v in series.describe().to_dict().items()}
            columns.append(result)
        return {"path": str(p), "sheet": sheet, "data_rows": len(frame),
                "columns": columns, "note": "Hàng 1 là tiêu đề. Công thức dùng cache Excel; "
                "cache có thể thiếu hoặc cũ. Không tính lại công thức."}

    def prepare_from_template(self, template, output_name, fills):
        """Validate inputs và trả plan; UI gọi commit_from_template sau khi người dùng duyệt."""
        import json as _json
        tmpl = self.path(template)
        # output_name chỉ là tên file, không chứa path separator
        if not isinstance(output_name, str) or not output_name:
            raise ValueError("output_name không hợp lệ.")
        clean_name = Path(output_name).name
        if not clean_name or clean_name != output_name or clean_name.startswith('.'):
            raise ValueError("output_name phải là tên file đơn, không chứa thư mục.")
        if not clean_name.lower().endswith('.xlsx'):
            clean_name = clean_name + '.xlsx'
        output_path = tmpl.parent / clean_name
        if output_path.exists():
            raise FileExistsError(f"File đích đã tồn tại: {output_path}. Chọn tên khác.")
        # Validate fills JSON
        if not isinstance(fills, str) or len(fills) > 200_000:
            raise ValueError("fills phải là chuỗi JSON tối đa 200000 ký tự.")
        try:
            rows = _json.loads(fills)
        except Exception:
            raise ValueError("fills không phải JSON hợp lệ.")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
            raise ValueError("fills cần 1–500 phần tử.")
        validated = []
        for item in rows:
            if not isinstance(item, dict):
                raise ValueError("Mỗi phần tử fills phải là đối tượng JSON.")
            sheet_name = item.get('sheet')
            cell_ref = item.get('cell')
            value = item.get('value')
            if not isinstance(sheet_name, str) or not sheet_name:
                raise ValueError("Mỗi fill cần 'sheet' là chuỗi.")
            if not isinstance(cell_ref, str) or not re.fullmatch(r"[A-Za-z]{1,3}[1-9][0-9]*", cell_ref):
                raise ValueError(f"Ô phải có dạng B2, nhận được: {cell_ref!r}.")
            cell_ref = cell_ref.upper()
            row_idx, col_idx = coordinate_to_tuple(cell_ref)
            if row_idx > 100_000 or col_idx > 16384:
                raise ValueError(f"Ô {cell_ref} ngoài giới hạn.")
            if type(value) not in (str, int, float, bool, type(None)):
                raise ValueError("Giá trị phải là text, số, boolean hoặc null.")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("Số không hữu hạn.")
            if isinstance(value, str) and (len(value) > 32767 or re.search(
                    r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value)):
                raise ValueError("Text quá dài hoặc chứa ký tự Excel không hợp lệ.")
            validated.append({'sheet': sheet_name, 'cell': cell_ref, 'value': value})
        return {'action': 'excel_create_from_template', 'template': str(tmpl),
                'output': str(output_path), 'fills': validated,
                'sha256': digest(tmpl), 'approval_id': uuid.uuid4().hex}

    def commit_from_template(self, plan):
        """Chỉ UI sau xác nhận mới được gọi."""
        tmpl = self.path(plan['template'])
        if digest(tmpl) != plan['sha256']:
            raise RuntimeError("File template đã thay đổi sau khi xin duyệt. Hãy thử lại.")
        output_path = Path(plan['output'])
        if output_path.exists():
            raise FileExistsError(f"File đích đã tồn tại: {output_path}.")
        if not any(output_path.parent.resolve() == root for root in self.roots):
            raise PermissionError("Thư mục đích nằm ngoài whitelist.")
        self.audit('excel_from_template_started', {'template': str(tmpl), 'output': str(output_path),
                                                    'fills': len(plan['fills'])})
        temp_path = None
        try:
            fd, temp = tempfile.mkstemp(prefix='.tmpl_', suffix='.xlsx', dir=output_path.parent)
            os.close(fd)
            temp_path = Path(temp)
            shutil.copy2(tmpl, temp_path)
            wb = load_workbook(temp_path, keep_links=True)
            try:
                if sum((s.max_row or 0) * (s.max_column or 0) for s in wb) > MAX_CELLS:
                    raise ValueError("Workbook template vượt 200000 ô.")
                for item in plan['fills']:
                    if item['sheet'] not in wb.sheetnames:
                        raise ValueError(f"Sheet không tồn tại trong template: {item['sheet']!r}.")
                    ws = wb[item['sheet']]
                    target = ws[item['cell']]
                    target.value = item['value']
                    if isinstance(item['value'], str):
                        target.data_type = 's'
                wb.calculation.fullCalcOnLoad = True
                saved = Path(temp_path.parent / (temp_path.name + '_v2.xlsx'))
                wb.save(saved)
            finally:
                wb.close()
            os.replace(saved, output_path)
            temp_path.unlink(missing_ok=True)
            temp_path = None
        except Exception as exc:
            self.audit('excel_from_template_failed', {'error': str(exc)})
            raise
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        result = {'ok': True, 'output': str(output_path), 'template': str(tmpl),
                  'fills_applied': len(plan['fills'])}
        self.audit('excel_from_template_success', result)
        return result

    def prepare_edit(self, path, sheet, cell, value):
        p = self.path(path)
        if not isinstance(cell, str) or not re.fullmatch(r"[A-Za-z]{1,3}[1-9][0-9]*", cell):
            raise ValueError("Ô phải có dạng B2.")
        cell = cell.upper()
        row, col = coordinate_to_tuple(cell)
        if row > 100000 or col > 16384:
            raise ValueError("Ô ngoài giới hạn hỗ trợ.")
        if type(value) not in (str, int, float, bool, type(None)):
            raise ValueError("Giá trị phải là text, số, boolean hoặc null.")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Số không hữu hạn.")
        if isinstance(value, str) and (len(value) > 32767 or re.search(
                r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value)):
            raise ValueError("Text quá dài hoặc chứa ký tự Excel không hợp lệ.")
        before = digest(p)
        wb = load_workbook(p, read_only=True, data_only=False, keep_links=False)
        try:
            ws = wb[sheet]
            if (ws.max_row or 0) * (ws.max_column or 0) > MAX_CELLS:
                raise ValueError("Workbook/sheet quá lớn để sửa trong giai đoạn 1.")
            old = scalar(ws[cell].value)
        finally:
            wb.close()
        if digest(p) != before:
            raise RuntimeError("File thay đổi trong khi đọc. Hãy thử lại.")
        return {"path": str(p), "sheet": sheet, "cell": cell, "old_value": old,
                "value": value, "sha256": before, "approval_id": uuid.uuid4().hex}

    def commit_edit(self, plan):
        """Chỉ UI sau xác nhận mới được gọi; không đăng ký hàm này làm model tool."""
        p = self.path(plan["path"])
        if digest(p) != plan["sha256"]:
            raise RuntimeError("File đã thay đổi sau khi xin duyệt. Hãy yêu cầu sửa lại.")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup = self.backups / f"{p.stem}_{stamp}_{uuid.uuid4().hex[:8]}.xlsx"
        self.audit("edit_started", {"plan": plan, "backup": str(backup)})
        temp_path = None
        try:
            shutil.copy2(p, backup)
            if digest(backup) != plan["sha256"]:
                raise RuntimeError("File thay đổi trong lúc backup; không sửa.")
            wb = load_workbook(backup, keep_links=True)
            try:
                if sum((s.max_row or 0) * (s.max_column or 0) for s in wb) > MAX_CELLS:
                    raise ValueError("Tổng workbook vượt 200000 ô; không sửa.")
                target = wb[plan["sheet"]][plan["cell"]]
                target.value = plan["value"]
                # Text luôn là literal, tránh biến text của model thành công thức.
                if isinstance(plan["value"], str):
                    target.data_type = "s"
                wb.calculation.fullCalcOnLoad = True
                fd, temp = tempfile.mkstemp(prefix=".assistant_", suffix=".xlsx", dir=p.parent)
                os.close(fd)
                temp_path = Path(temp)
                wb.save(temp_path)
            finally:
                wb.close()
            # Phát hiện việc người dùng/Excel thay đổi file trong lúc chuẩn bị.
            if self.path(plan["path"]) != p or digest(p) != plan["sha256"]:
                raise RuntimeError("File thay đổi trước khi ghi; thao tác đã hủy.")
            os.replace(temp_path, p)
            result = {"ok": True, "path": str(p), "sheet": plan["sheet"],
                      "cell": plan["cell"], "value": plan["value"], "backup": str(backup)}
            self.audit("edit_success", result)
            return result
        except Exception as exc:
            self.audit("edit_failed", {"error": str(exc), "backup": str(backup)})
            raise
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

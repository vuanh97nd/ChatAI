"""Tests for foxit_ocr_automation and its integration in documents.read_local."""
import io
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Unit tests for foxit_ocr_automation module
# ---------------------------------------------------------------------------

class TestIsReadable(unittest.TestCase):
    def _make_pdf_bytes(self, text="hello"):
        """Build a minimal in-memory PDF with extractable text via pypdf."""
        try:
            from pypdf import PdfWriter
        except ImportError:
            return None  # pypdf unavailable – skip
        writer = PdfWriter()
        page = writer.add_blank_page(width=595, height=842)
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()

    def test_returns_false_for_scan_only_pdf(self):
        """A PDF with no text layer is not readable."""
        from assistant.foxit_ocr_automation import is_readable
        import tempfile, struct

        # Minimal valid-enough PDF shell that pypdf can parse (0 pages)
        minimal_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<</Type /Catalog /Pages 2 0 R>>\nendobj\n"
            b"2 0 obj\n<</Type /Pages /Kids [] /Count 0>>\nendobj\n"
            b"xref\n0 3\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"trailer\n<</Size 3 /Root 1 0 R>>\nstartxref\n116\n%%EOF\n"
        )
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(minimal_pdf)
            tmp = Path(f.name)
        try:
            result = is_readable(tmp)
            self.assertFalse(result)
        finally:
            tmp.unlink(missing_ok=True)

    def test_returns_false_for_nonexistent_file(self):
        from assistant.foxit_ocr_automation import is_readable
        self.assertFalse(is_readable("/nonexistent/path/file.pdf"))

    def test_returns_false_for_corrupt_file(self):
        from assistant.foxit_ocr_automation import is_readable
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"not a pdf at all")
            tmp = Path(f.name)
        try:
            self.assertFalse(is_readable(tmp))
        finally:
            tmp.unlink(missing_ok=True)


class TestAvailable(unittest.TestCase):
    def test_returns_false_on_non_windows(self):
        from assistant.foxit_ocr_automation import available
        if sys.platform != "win32":
            self.assertFalse(available())

    def test_returns_false_when_pywinauto_missing(self):
        import importlib.util
        with patch.object(importlib.util, "find_spec", return_value=None):
            from assistant import foxit_ocr_automation as mod
            # Patch os.name to simulate Windows
            with patch.object(mod.os, "name", "nt"):
                self.assertFalse(mod.available())


class TestFoxitOcrRaisesWhenUnavailable(unittest.TestCase):
    def test_raises_runtime_error_when_not_available(self):
        from assistant import foxit_ocr_automation as mod
        with patch.object(mod, "available", return_value=False):
            with self.assertRaises(RuntimeError) as cm:
                mod.foxit_ocr("/some/file.pdf")
            self.assertIn("pywinauto", str(cm.exception))

    def test_raises_runtime_error_for_missing_file(self):
        from assistant import foxit_ocr_automation as mod
        with patch.object(mod, "available", return_value=True):
            with self.assertRaises(RuntimeError) as cm:
                mod.foxit_ocr("/nonexistent/path.pdf")
            self.assertIn("Không tìm thấy file", str(cm.exception))


class TestFindFoxitExe(unittest.TestCase):
    def test_returns_none_when_no_foxit_installed(self):
        from assistant.foxit_ocr_automation import _find_foxit_exe
        # On non-Windows CI, none of the Windows paths exist
        if sys.platform != "win32":
            result = _find_foxit_exe()
            self.assertIsNone(result)


class TestOcrSkippedWhenOutputAlreadyReadable(unittest.TestCase):
    def test_returns_existing_output_without_launching_foxit(self):
        """If <stem>_OCR.pdf already exists and is readable, skip UI automation."""
        import tempfile, os
        from assistant import foxit_ocr_automation as mod

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "doc.pdf"
            src.write_bytes(b"%PDF-dummy")
            out = Path(tmp) / "doc_OCR.pdf"
            out.write_bytes(b"%PDF-dummy-ocr")

            # Patch is_readable so the existing output is considered readable
            with patch.object(mod, "is_readable", side_effect=lambda p: Path(p) == out):
                with patch.object(mod, "available", return_value=True):
                    result = mod.foxit_ocr(src)
            self.assertEqual(result, out)


# ---------------------------------------------------------------------------
# Integration: documents.read_local with foxit_ocr fallback
# ---------------------------------------------------------------------------

_OCR_ERROR = ValueError("PDF không có lớp chữ trích xuất; cần OCR.")


def _stub_read_bytes_scan(raw, kind="", name="document", pdf_ocr=None):
    """Simulate read_bytes for a scan-only PDF."""
    raise _OCR_ERROR


class TestReadLocalFoxitFallback(unittest.TestCase):
    def _write_pdf(self, directory: Path, name: str = "scan.pdf") -> Path:
        p = directory / name
        p.write_bytes(b"dummy")
        return p

    def test_fallback_not_triggered_without_foxit_ocr_flag(self):
        """read_local raises ValueError without foxit_ocr=True."""
        import tempfile
        from assistant import documents

        with tempfile.TemporaryDirectory() as tmp:
            src = self._write_pdf(Path(tmp))
            with patch.object(documents, "read_bytes", side_effect=_stub_read_bytes_scan):
                with self.assertRaises(ValueError):
                    documents.read_local(str(src), foxit_ocr=False)

    def test_fallback_not_triggered_when_foxit_unavailable(self):
        """foxit_ocr=True but Foxit not available → original ValueError re-raised."""
        import tempfile
        from assistant import documents
        from assistant import foxit_ocr_automation as mod

        with tempfile.TemporaryDirectory() as tmp:
            src = self._write_pdf(Path(tmp))
            with patch.object(documents, "read_bytes", side_effect=_stub_read_bytes_scan), \
                 patch.object(mod, "available", return_value=False):
                with self.assertRaises(ValueError):
                    documents.read_local(str(src), foxit_ocr=True)

    def test_fallback_calls_foxit_and_returns_result(self):
        """foxit_ocr=True + Foxit available → foxit_ocr called, result returned."""
        import tempfile
        from assistant import documents
        from assistant import foxit_ocr_automation as mod

        with tempfile.TemporaryDirectory() as tmp:
            src = self._write_pdf(Path(tmp))
            ocr_out = Path(tmp) / "scan_OCR.pdf"
            ocr_out.write_bytes(b"dummy-content")

            _ocr_result = {
                "text": "[trang 1]\nhello world",
                "units": [{"location": "trang 1", "text": "hello world"}],
                "title": "",
                "format": "pdf",
                "ocr_pages": [],
                "full_text": True,
                "truncated": False,
                "issues": [],
                "coverage": "full_text",
                "coverage_note": "ok",
            }

            def fake_read_bytes(raw, kind="", name="document", pdf_ocr=None):
                if "scan_OCR" in name:
                    return _ocr_result
                raise _OCR_ERROR

            with patch.object(mod, "available", return_value=True), \
                 patch.object(mod, "foxit_ocr", return_value=ocr_out) as mock_foxit, \
                 patch.object(documents, "read_bytes", side_effect=fake_read_bytes):
                result = documents.read_local(str(src), foxit_ocr=True)

            mock_foxit.assert_called_once_with(src)
            self.assertTrue(result.get("foxit_ocr"))
            self.assertIn("hello world", result["text"])

    def test_non_pdf_error_not_intercepted(self):
        """A non-OCR ValueError from a non-PDF is re-raised unchanged."""
        import tempfile
        from assistant import documents

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "data.txt"
            p.write_bytes(b"x" * (documents.MAX_BYTES + 1))
            with self.assertRaises(ValueError):
                documents.read_local(str(p), foxit_ocr=True)


if __name__ == "__main__":
    unittest.main()

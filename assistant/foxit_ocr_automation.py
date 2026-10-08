"""Automate Foxit PDF Editor to OCR unreadable (scan-only) PDFs via UI automation.

Requires pywinauto and Windows. The function `foxit_ocr` opens the target PDF
in Foxit, runs OCR with English language / Searchable-PDF output, saves the
result as <stem>_OCR.pdf next to the original, and returns that path.

Call `is_readable(path)` first; it returns False for scan-only PDFs.

Integration point: `documents.py` calls `foxit_ocr` as a fallback when
`read_local` raises the "cần OCR" error.
"""
from __future__ import annotations

import os
import sys
import time
import importlib.util
from pathlib import Path

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

OCR_TIMEOUT = 300  # seconds to wait for Foxit OCR to finish
FOXIT_EXE_DEFAULT = r"C:\Program Files (x86)\Foxit Software\Foxit PDF Editor\FoxitPDFEditor.exe"


def available() -> bool:
    """Return True when pywinauto is importable and we are on Windows."""
    return os.name == "nt" and importlib.util.find_spec("pywinauto") is not None


def is_readable(path: str | Path) -> bool:
    """Return False when the PDF has no extractable text on any page."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        for page in reader.pages:
            if (page.extract_text() or "").strip():
                return True
        return False
    except Exception:
        return False


def foxit_ocr(
    path: str | Path,
    *,
    foxit_exe: str | None = None,
    language: str = "English",
    timeout: int = OCR_TIMEOUT,
) -> Path:
    """OCR *path* with Foxit PDF Editor and return the path to the OCR'd file.

    The output file is placed beside the original with ``_OCR`` appended to the
    stem (e.g. ``Plaxis.pdf`` → ``Plaxis_OCR.pdf``).  If the output already
    exists and is readable the function returns it without re-running OCR.

    Raises
    ------
    RuntimeError
        When pywinauto is unavailable, Foxit cannot be found/launched, or OCR
        fails within *timeout* seconds.
    """
    if not available():
        raise RuntimeError(
            "foxit_ocr yêu cầu Windows và thư viện pywinauto. "
            "Cài: pip install pywinauto"
        )

    src = Path(path).resolve()
    if not src.is_file():
        raise RuntimeError(f"Không tìm thấy file: {src}")

    out = src.with_name(src.stem + "_OCR" + src.suffix)
    if out.exists() and is_readable(out):
        return out

    exe = foxit_exe or _find_foxit_exe()
    if not exe:
        raise RuntimeError(
            "Không tìm thấy Foxit PDF Editor. Cài Foxit hoặc truyền foxit_exe= "
            f"(mặc định: {FOXIT_EXE_DEFAULT})"
        )

    from pywinauto import Application, timings
    from pywinauto.keyboard import send_keys

    timings.Timings.fast()

    # ------------------------------------------------------------------
    # Launch Foxit (or attach to a running instance)
    # ------------------------------------------------------------------
    app = _launch_or_attach(exe)

    # ------------------------------------------------------------------
    # Open the PDF
    # ------------------------------------------------------------------
    _open_file(app, str(src))

    # ------------------------------------------------------------------
    # Invoke OCR: Tools → OCR Text Recognition (or Home → OCR)
    # ------------------------------------------------------------------
    _run_ocr_dialog(app, language=language)

    # ------------------------------------------------------------------
    # Wait for OCR to finish
    # ------------------------------------------------------------------
    _wait_for_ocr(app, timeout=timeout)

    # ------------------------------------------------------------------
    # Save As → output path
    # ------------------------------------------------------------------
    _save_as(app, str(out))

    # ------------------------------------------------------------------
    # Close the document (leave Foxit running to avoid re-launch overhead)
    # ------------------------------------------------------------------
    _close_document(app)

    if not out.exists():
        raise RuntimeError(
            f"OCR hoàn thành nhưng không tìm thấy file đầu ra: {out}"
        )
    if not is_readable(out):
        raise RuntimeError(
            f"File OCR tạo ra ({out.name}) vẫn không có layer text. "
            "Kiểm tra lại cài đặt OCR trong Foxit."
        )
    return out


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_foxit_exe() -> str | None:
    candidates = [
        FOXIT_EXE_DEFAULT,
        r"C:\Program Files\Foxit Software\Foxit PDF Editor\FoxitPDFEditor.exe",
        r"C:\Program Files (x86)\Foxit Software\Foxit PDF Reader\FoxitPDFReader.exe",
        r"C:\Program Files\Foxit Software\Foxit PDF Reader\FoxitPDFReader.exe",
    ]
    for c in candidates:
        if Path(c).is_file():
            return c
    # Check PATH
    import shutil
    found = shutil.which("FoxitPDFEditor") or shutil.which("FoxitPDFReader")
    return found


def _launch_or_attach(exe: str):
    """Return a pywinauto Application connected to Foxit."""
    from pywinauto import Application, findwindows

    # Try attaching to an existing Foxit window first
    for title_re in (r"Foxit PDF Editor", r"Foxit PDF Reader"):
        try:
            handles = findwindows.find_windows(title_re=title_re, visible_only=True)
            if handles:
                app = Application(backend="uia").connect(handle=handles[0])
                return app
        except Exception:
            pass

    # Launch fresh
    print(f'Chat AI Foxit: launching {exe}', flush=True)
    try:
        app = Application(backend="uia").start(exe)
    except Exception as err:
        raise RuntimeError(f'Không khởi động được Foxit: {err}') from err
    # Wait for main window
    _wait_for_main_window(app, timeout=30)
    # Dismiss any startup dialogs (license, update, tip of the day)
    _dismiss_startup_dialogs(app)
    return app


def _wait_for_main_window(app, timeout: int = 30):
    from pywinauto import timings

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            wins = app.windows()
            for w in wins:
                title = w.window_text()
                if "Foxit" in title:
                    w.wait("visible", timeout=5)
                    return w
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("Foxit PDF Editor không khởi động trong thời gian chờ.")


_STARTUP_DIALOG_KEYWORDS = (
    "tip", "update", "trial", "activate", "welcome",
    "register", "subscription", "license", "agreement", "eula",
    "renew", "notification", "what's new", "new feature",
)
_DISMISS_BTN_TITLES = ("Close", "Cancel", "No", "Later", "Skip", "Remind me later",
                       "Đóng", "Hủy", "Không", "Bỏ qua", "X")


def _dismiss_startup_dialogs(app, wait: float = 3.0):
    """Close common startup popups (license reminder, update nag, tip of day)."""
    time.sleep(wait)
    for _attempt in range(3):
        try:
            for w in app.windows():
                title = (w.window_text() or "").lower()
                if not any(kw in title for kw in _STARTUP_DIALOG_KEYWORDS):
                    continue
                print(f'Chat AI Foxit: dismissing startup dialog "{w.window_text()}"', flush=True)
                dismissed = False
                for btn_title in _DISMISS_BTN_TITLES:
                    try:
                        btn = w.child_window(title=btn_title, control_type="Button")
                        if btn.exists() and btn.is_enabled():
                            btn.click_input()
                            dismissed = True
                            break
                    except Exception:
                        pass
                if not dismissed:
                    try:
                        w.close()
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(1.0)


def _main_window(app):
    """Return the primary Foxit window."""
    from pywinauto import findwindows

    for title_re in (r"Foxit PDF Editor", r"Foxit PDF Reader"):
        try:
            handles = findwindows.find_windows(title_re=title_re, visible_only=True)
            if handles:
                return app.window(handle=handles[0])
        except Exception:
            pass
    # Fallback: largest window
    wins = [w for w in app.windows() if w.is_visible()]
    if not wins:
        raise RuntimeError("Không tìm thấy cửa sổ Foxit.")
    return max(wins, key=lambda w: w.rectangle().width())


def _open_file(app, path: str):
    """Use Ctrl+O to open a file in Foxit."""
    from pywinauto.keyboard import send_keys

    win = _main_window(app)
    win.set_focus()
    time.sleep(0.3)
    send_keys("^o")  # Ctrl+O
    _fill_open_dialog(app, path)
    # Wait for the document to load (title changes)
    stem = Path(path).stem
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            win = _main_window(app)
            if stem in win.window_text():
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Foxit không mở được file trong thời gian chờ: {path}")


def _fill_open_dialog(app, path: str):
    """Type the path into the Windows Open-file common dialog and confirm."""
    from pywinauto import Application, timings
    from pywinauto.keyboard import send_keys

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            # Common dialog has class "#32770"
            dlg = app.window(class_name="#32770")
            dlg.wait("visible", timeout=5)
            # Find the filename combo/edit
            try:
                fn = dlg.child_window(auto_id="1148")  # "File name" edit
            except Exception:
                fn = dlg.child_window(title_re=".*", control_type="Edit")
            fn.set_focus()
            fn.set_edit_text(path)
            send_keys("{ENTER}")
            return
        except Exception:
            pass
        time.sleep(0.3)
    raise RuntimeError("Hộp thoại Mở file không xuất hiện.")


def _run_ocr_dialog(app, language: str = "English"):
    """Navigate to the OCR command and configure it."""
    from pywinauto.keyboard import send_keys

    win = _main_window(app)
    win.set_focus()
    time.sleep(0.3)

    # Try menu path: Tools → OCR Text Recognition → Current File…
    opened = False
    try:
        menu = win.menu()
        menu.get_menu_path("Tools->OCR Text Recognition->Current File...")[0].click_input()
        opened = True
    except Exception:
        pass

    if not opened:
        # Alt-key fallback: Alt+T O
        send_keys("%t")  # Alt+T → Tools menu
        time.sleep(0.4)
        send_keys("o")   # OCR
        time.sleep(0.4)

    # Interact with the OCR dialog
    _configure_ocr_dialog(app, language=language)


def _configure_ocr_dialog(app, language: str = "English"):
    """Set language and output mode, then start OCR."""
    from pywinauto.keyboard import send_keys

    deadline = time.monotonic() + 20
    dlg = None
    while time.monotonic() < deadline:
        for w in app.windows():
            title = (w.window_text() or "").lower()
            if "ocr" in title:
                dlg = w
                break
        if dlg:
            break
        time.sleep(0.5)

    if dlg is None:
        raise RuntimeError("Hộp thoại OCR không xuất hiện trong thời gian chờ.")

    dlg.set_focus()
    time.sleep(0.3)

    # Set language
    try:
        lang_combo = dlg.child_window(title_re=".*", control_type="ComboBox")
        lang_combo.select(language)
    except Exception:
        pass  # Language might already be correct or combo not found

    # Set output type to "Searchable PDF" (keep PDF, add text layer)
    for label in ("Searchable PDF", "PDF with hidden text", "PDF (Searchable)"):
        try:
            rb = dlg.child_window(title=label, control_type="RadioButton")
            if rb.exists():
                rb.click_input()
                break
        except Exception:
            pass

    # Click OK / Run
    for btn_title in ("OK", "Run", "Start", "Nhận dạng", "Start OCR"):
        try:
            btn = dlg.child_window(title=btn_title, control_type="Button")
            if btn.exists() and btn.is_enabled():
                btn.click_input()
                return
        except Exception:
            pass

    # Final fallback: Enter
    send_keys("{ENTER}")


def _wait_for_ocr(app, timeout: int = OCR_TIMEOUT):
    """Block until the OCR progress dialog disappears or timeout."""
    deadline = time.monotonic() + timeout
    # Give OCR a moment to start
    time.sleep(2.0)

    while time.monotonic() < deadline:
        progress_visible = False
        try:
            for w in app.windows():
                title = (w.window_text() or "").lower()
                if any(kw in title for kw in ("progress", "ocr", "nhận dạng", "processing")):
                    progress_visible = True
                    break
        except Exception:
            pass

        if not progress_visible:
            # No progress window → OCR done (or never started a separate window)
            time.sleep(1.0)
            return

        time.sleep(1.0)

    raise RuntimeError(
        f"OCR không hoàn thành trong {timeout}s. File PDF có thể rất lớn; "
        "thử tăng timeout hoặc chạy OCR thủ công trong Foxit."
    )


def _save_as(app, out_path: str):
    """File → Save As → type path → confirm."""
    from pywinauto.keyboard import send_keys

    win = _main_window(app)
    win.set_focus()
    time.sleep(0.3)

    # Ctrl+Shift+S  or  File > Save As
    send_keys("^+s")
    time.sleep(0.5)

    # If that didn't open a dialog, try menu
    dlg = _wait_for_dialog(app, title_re=r"Save As|Lưu thành", timeout=8)
    if dlg is None:
        try:
            menu = win.menu()
            menu.get_menu_path("File->Save As...")[0].click_input()
        except Exception:
            send_keys("%f")
            time.sleep(0.4)
            send_keys("a")
            time.sleep(0.4)
        dlg = _wait_for_dialog(app, title_re=r"Save As|Lưu thành", timeout=10)

    if dlg is None:
        raise RuntimeError("Hộp thoại Lưu thành không xuất hiện.")

    # Fill the filename
    try:
        fn = dlg.child_window(auto_id="1148")
    except Exception:
        fn = dlg.child_window(title_re=".*", control_type="Edit")
    fn.set_focus()
    fn.set_edit_text(out_path)
    send_keys("{ENTER}")
    time.sleep(1.0)

    # Confirm overwrite if asked
    confirm = _wait_for_dialog(app, title_re=r"Confirm|Xác nhận|Replace", timeout=4)
    if confirm:
        try:
            confirm.child_window(title="Yes", control_type="Button").click_input()
        except Exception:
            send_keys("{ENTER}")


def _close_document(app):
    """Close the active document (Ctrl+W) without closing Foxit."""
    from pywinauto.keyboard import send_keys

    try:
        win = _main_window(app)
        win.set_focus()
        send_keys("^w")
        time.sleep(0.5)
        # Dismiss "save changes?" if it appears
        dlg = _wait_for_dialog(app, title_re=r"Save|Lưu", timeout=4)
        if dlg:
            # Click "No" / "Không" – we already saved with Save As
            for title in ("No", "Không", "Don't Save"):
                try:
                    btn = dlg.child_window(title=title, control_type="Button")
                    if btn.exists():
                        btn.click_input()
                        return
                except Exception:
                    pass
            send_keys("{ENTER}")
    except Exception:
        pass


def _wait_for_dialog(app, title_re: str, timeout: float = 10.0):
    """Return the first window matching *title_re*, or None on timeout."""
    import re

    pattern = re.compile(title_re, re.IGNORECASE)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            for w in app.windows():
                if pattern.search(w.window_text() or ""):
                    return w
        except Exception:
            pass
        time.sleep(0.3)
    return None

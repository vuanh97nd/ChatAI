"""Installer dưới nền. Chỉ UI gọi sau khi người dùng xác nhận; model không có tool cài đặt."""
import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
import hashlib
from pathlib import Path

from .locking import execution_lock
from .storage import now

MODULES = {
    "office": {"label": "Word / PowerPoint", "packages": ["python-docx>=1.1,<2", "python-pptx>=1,<2", "pandas>=2.2,<3", "openpyxl>=3.1.5,<4"],
               "imports": ["docx", "pptx", "pandas", "openpyxl"], "models": [],
               "note": "Đọc DOCX/PPTX, tạo Word/slide và sửa text Word sau duyệt. Bản cài gọn tải thư viện Excel XLSX khi bật Office. Không hỗ trợ DOC/PPT cũ, macro, OCR."},
    "web": {"label":"Tìm kiếm Bing","packages":[],"imports":[],"models":[],
            "note":"Dùng Bing trực tiếp, không cài module. Cần Internet khi tìm kiếm."},
    "files": {"label": "Quản lý file", "packages": [], "imports": [], "models": [],
              "note": "Không cần tải thêm. Ghi/sửa/di chuyển/xóa đều cần duyệt."},
    "python": {"label": "Python và lệnh cách ly", "packages": [], "imports": [], "models": [],
               "note": "Cần Docker Desktop chạy Linux containers. Runtime cài sẵn pandas, Excel/PDF/Word, Pillow, imageio, imageio-ffmpeg và OpenCV. AI có thể dùng các thư viện này trong sandbox; file kết quả lưu vào workspace/outputs sau khi duyệt chạy code."},
    "media_basic": {"label": "Thư viện ảnh / video cơ bản",
                    "packages": ["Pillow>=10,<13", "imageio>=2.34,<3", "imageio-ffmpeg>=0.5,<1",
                                 "opencv-python-headless>=4.10,<5", "numpy>=1.26,<3"],
                    "imports": ["PIL", "imageio", "imageio_ffmpeg", "cv2", "numpy"], "models": [],
                    "note": "Tự cài nền khi thiếu. Dùng để đọc/đổi kích thước ảnh, xử lý khung hình và xuất slideshow MP4. Không tải model tạo ảnh/video nặng."},
    "rag": {"label": "RAG tài liệu cá nhân", "packages": ["chromadb>=1,<2", "pypdf>=5,<7", "python-docx>=1.1,<2"],
            "imports": ["chromadb", "pypdf", "docx"], "models": ["bge-m3"],
            "note": "Index TXT/MD/PDF/DOCX local; embedding bge-m3 CPU, không tải thêm model LLM lớn."},
    "media": {"label": "Tạo ảnh AI nâng cao", "packages": ["diffusers>=0.35,<0.37", "transformers>=4.44,<5",
              "accelerate>=1,<2", "safetensors>=0.4,<1", "huggingface-hub>=0.34,<1"],
              "imports": ["torch", "diffusers", "transformers", "huggingface_hub"],
              "models": [], "note": "Chọn SD-Turbo (nhanh) hoặc SDXL-Turbo (chất lượng cao) ở bên dưới. Model sẽ tải riêng theo lựa chọn; cả hai tạo PNG 512×512. SDXL-Turbo lớn hơn và có thể chậm hơn trên GPU 8 GB. Slideshow MP4 cơ bản có sẵn bằng thư viện Python; đây chưa phải video diffusion."},
}
MEDIA_VARIANTS = {
    "sd-turbo": {"label": "SD-Turbo · nhanh", "repo": "stabilityai/sd-turbo", "folder": "sd-turbo",
                 "display": "SD-Turbo FP16", "disk_gb": 12,
                 "quality_note": "Model nhỏ, tạo nhanh; chất lượng và độ bám prompt thấp hơn SDXL-Turbo."},
    "sdxl-turbo": {"label": "SDXL-Turbo · chất lượng cao", "repo": "stabilityai/sdxl-turbo", "folder": "sdxl-turbo",
                   "display": "SDXL-Turbo FP16", "disk_gb": 14,
                   "quality_note": "Model khoảng 7 GB tải. RTX 3070 8 GB dùng FP16; nếu VRAM thiếu sẽ tự chuyển sang tiết kiệm bộ nhớ và chậm hơn."},
}
CHAT_MODELS = {
    'qwen3:8b': {'tools': True, 'label': 'Qwen3 8B · chat, code và suy luận', 'disk_gb': 8},
    'gemma3:4b': {'tools': False, 'vision': True, 'label': 'Gemma 3 4B · đọc ảnh (~3.3 GB tải)', 'disk_gb': 6},
    'deepseek-r1:8b': {'tools': False, 'label': 'DeepSeek R1 8B · suy luận (~5.2 GB tải)', 'disk_gb': 8},
    'qwen2.5:7b': {'tools': True, 'label': 'Qwen 7B · chất lượng', 'disk_gb': 8},
    'qwen2.5-coder:7b': {'tools': True, 'label': 'Qwen Coder 7B', 'disk_gb': 8},
    'qwen2.5:3b': {'tools': True, 'label': 'Qwen 3B · nhẹ, đa năng (~1.9 GB tải)', 'disk_gb': 4},
    'qwen2.5:1.5b': {'tools': True, 'label': 'Qwen 1.5B · rất nhẹ (~986 MB tải)', 'disk_gb': 3},
    'qwen2.5-coder:3b': {'tools': True, 'label': 'Qwen Coder 3B · code nhẹ (~1.9 GB tải)', 'disk_gb': 4},
    'deepseek-r1:1.5b': {'tools': False, 'label': 'DeepSeek R1 1.5B · chat/suy luận (~1.1 GB tải)', 'disk_gb': 3},
    'deepseek-coder-v2:16b': {'tools': False, 'label': 'DeepSeek-Coder-V2 Lite 16B · code (~8.9 GB tải)',
        'disk_gb': 15, 'large': True, 'download_gb': 8.9,
        'warning': 'Bản Lite 16B (không phải bản 236B). Trọng số đã lớn hơn VRAM 8 GB; có thể chạy kết hợp CPU/GPU nhưng chậm. RAM 16 GB còn phải dành cho Windows và ngữ cảnh.'},
    'qwen2.5-coder:32b': {'tools': True, 'label': 'Qwen2.5-Coder 32B · AI lớn (~20 GB tải)',
        'disk_gb': 30, 'large': True, 'download_gb': 20,
        'warning': 'Bản Q4_K_M khoảng 20 GB. Máy RAM 16 GB / VRAM 8 GB có thể thiếu bộ nhớ hoặc trả lời rất chậm; không bảo đảm chạy được. Giữ Qwen Coder 7B để dùng ổn định hơn trên cấu hình này.'},
    'codestral:22b': {'tools': False, 'label': 'Codestral 22B · AI lớn (~13 GB tải)',
        'disk_gb': 22, 'large': True, 'download_gb': 13,
        'warning': 'Khoảng 13 GB trọng số, chưa gồm bộ nhớ ngữ cảnh và Windows. Không nạp toàn bộ vào VRAM 8 GB; có thể thiếu RAM hoặc chạy chậm. Chỉ chat/code, không hỗ trợ tool calling trong bản này.'},
    'deepseek-coder:33b': {'tools': False, 'label': 'DeepSeek-Coder 33B · AI lớn (~19 GB tải)',
        'disk_gb': 30, 'large': True, 'download_gb': 19,
        'warning': 'Khoảng 19 GB trọng số. Máy RAM 16 GB / VRAM 8 GB có thể thiếu bộ nhớ hoặc trả lời rất chậm; không bảo đảm chạy được. Chỉ chat/code, không hỗ trợ tool calling trong bản này.'},
}
ALLOWED_MODELS = set(CHAT_MODELS) | {'nomic-embed-text', 'bge-m3'}
BASE_IMAGE = "python:3.11-slim"
IMAGE = "chat-ai-python-tools:2"


def media_model_dir(root, variant="sd-turbo"):
    """Keep each image model separate beside the project so users can switch safely."""
    if variant not in MEDIA_VARIANTS:
        raise ValueError("Phiên bản model ảnh không hợp lệ.")
    return Path(root) / "data" / "models" / MEDIA_VARIANTS[variant]["folder"]


class DownloadStopped(Exception):
    pass


class ModuleManager:
    def __init__(self, store, client, root):
        self.store, self.client, self.root = store, client, Path(root)
        # Google Drive virtual disks không phù hợp với file khóa dùng bởi
        # installer đa tiến trình; giữ khóa trên ổ cục bộ của người dùng.
        app_data = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
        project_key = hashlib.sha256(str(self.root.resolve()).casefold().encode("utf-8")).hexdigest()[:16]
        self.installer_lock = app_data / "ChatAI" / "locks" / (project_key + ".lock")
        self.installer_lock.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.busy = False
        self.stop_event=threading.Event();self.stop_action=None;self.active_target=None
        with store.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,target TEXT NOT NULL,
                    status TEXT NOT NULL,progress REAL,message TEXT NOT NULL,updated TEXT NOT NULL);
            """)
        # Dấu interrupted chỉ ghi khi khởi tạo manager; không tự resume download/cài đặt.
        try:
            with execution_lock(self.installer_lock):
                with store.connection() as db:
                    db.execute("UPDATE jobs SET status='interrupted',message=?,updated=? "
                               "WHERE status IN ('queued','running')",
                               ("Ứng dụng đã dừng. Bấm tải lại nếu muốn tiếp tục.", now()))
        except RuntimeError:
            pass
        # Thư viện ảnh/video cơ bản được tự tải nền nếu bản cài còn thiếu.
        # Không tự tải model sinh ảnh/video nặng; mô-đun đó vẫn cần người dùng chọn.
        try:
            self.ensure_basic_media_libraries()
        except Exception as exc:
            self.store.audit("installer", "media_libraries_auto_start_failed", {"error": str(exc)})

    def enabled(self, module):
        if module=='web':return True  # Ignore old disabled-module preferences for built-in Bing.
        with self.store.connection() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (module,)).fetchone()
        if row:
            return row[0] == "1"
        if module == "media":
            return not self.missing("media")
        return module in {"web", "media_basic"}

    def ensure_basic_media_libraries(self):
        """Start one background install when the bundled basic media libraries are absent."""
        if not self.enabled("media_basic") or not self.missing("media_basic"):
            return None
        with self.store.connection() as db:
            row = db.execute("SELECT status FROM jobs WHERE target='media_basic' ORDER BY updated DESC LIMIT 1").fetchone()
        if row and row[0] in {"queued", "running"}:
            return None
        return self.request("media_basic", automatic=True)

    def set_enabled(self, module, value):
        if module=='web':return  # Search permission is controlled per turn by the chat button.
        if module not in MODULES:
            raise ValueError("Module không được hỗ trợ.")
        with self.store.connection() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (module, "1" if value else "0"))

    def installed_models(self):
        names = {m.model for m in self.client.list().models}
        return names | {name.removesuffix(":latest") for name in names}

    def media_variant(self):
        with self.store.connection() as db:
            row=db.execute("SELECT value FROM settings WHERE key='media_variant'").fetchone()
        return row[0] if row and row[0] in MEDIA_VARIANTS else "sd-turbo"

    def set_media_variant(self, variant):
        if variant not in MEDIA_VARIANTS:
            raise ValueError("Phiên bản model ảnh không hợp lệ.")
        with self.store.connection() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES ('media_variant',?)",(variant,))

    def missing(self, module):
        spec = MODULES[module]
        importlib.invalidate_caches()
        missing = [f"Thư viện {p}" for p in spec["imports"] if importlib.util.find_spec(p) is None]
        if spec["models"]:
            try:
                models = self.installed_models()
                missing += [f"Model {m}" for m in spec["models"] if m not in models]
            except Exception:
                missing += ["Không kết nối được Ollama để kiểm tra embedding"]
        if module == "media":
            variant=self.media_variant()
            local_ready = (media_model_dir(self.root,variant) / "ready.json").is_file()
            if not local_ready:
                missing.append("Model "+MEDIA_VARIANTS[variant]["display"])
        if module == "python":
            docker = shutil.which("docker")
            if not docker:
                return missing + ["Docker Desktop (cài thủ công)"]
            try:
                result = subprocess.run([docker, "image", "inspect", IMAGE], capture_output=True, timeout=10)
                if result.returncode:
                    missing.append(f"Docker image {IMAGE} hoặc Docker chưa chạy")
            except (OSError, subprocess.TimeoutExpired):
                missing.append("Docker chưa sẵn sàng")
        return missing

    def ready(self, module):
        return self.enabled(module) and not self.missing(module)

    def jobs(self):
        with self.store.connection() as db:
            rows = db.execute("SELECT id,target,status,progress,message FROM jobs ORDER BY updated DESC LIMIT 12").fetchall()
        return [dict(zip(("id", "target", "status", "progress", "message"), row)) for row in rows]

    def update(self, jid, status, message, progress=None):
        with self.store.connection() as db:
            db.execute("UPDATE jobs SET status=?,message=?,progress=?,updated=? WHERE id=?",
                       (status, message[-4000:], progress, now(), jid))

    def request(self, target, automatic=False):
        # Không nhận package name, pip flags hoặc URL từ model/người dùng.
        if target not in MODULES and target not in ALLOWED_MODELS:
            raise ValueError("Gói tải không nằm trong danh mục cố định.")
        with self.lock:
            if self.busy:
                raise RuntimeError("Đang tải một module/model khác. Đợi tác vụ đó hoàn tất.")
            self.busy = True
            self.stop_event.clear();self.stop_action=None;self.active_target=target
        jid = uuid.uuid4().hex
        if automatic and target == "media":
            message = "Model ảnh đã có trên Google Drive; đang chuẩn bị thư viện trong môi trường riêng, không tải lại model."
        elif automatic:
            message = "Thiếu thư viện ảnh/video; đang tự tải và cài đặt nền."
        else:
            message = "Người dùng đã duyệt; đang chờ tải."
        with self.store.connection() as db:
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?)",
                       (jid, target, "queued", None, message, now()))
        self.store.audit("installer", "download_started_automatic" if automatic else "download_approved",
                         {"target": target, "job": jid})
        threading.Thread(target=self.worker, args=(jid, target), daemon=True).start()
        return jid

    def remove_model(self, model):
        if model not in ALLOWED_MODELS:raise ValueError('AI không có trong danh mục hỗ trợ.')
        with self.lock:
            if self.busy:raise RuntimeError('Đợi tác vụ tải/cài hiện tại kết thúc trước khi gỡ AI.')
            self.busy=True;self.active_target=None;self.stop_event.clear();self.stop_action=None
        jid=uuid.uuid4().hex
        try:
            with self.store.connection() as db:
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?)',(jid,model,'queued',None,'Đã xác nhận; đang chờ gỡ AI.',now()))
            self.store.audit('installer','model_remove_approved',{'model':model,'job':jid})
            threading.Thread(target=self.remove_worker,args=(jid,model),daemon=True).start()
        except Exception:
            with self.lock:self.busy=False
            raise
        return jid

    def remove_worker(self, jid, model):
        try:
            with execution_lock(self.root/'data/installer.lock'):
                self.update(jid,'running','Đang gỡ AI '+model+'…')
                installed=self.installed_models()
                if model not in installed:raise RuntimeError('AI này chưa được cài trong Ollama.')
                self.client.delete(model)
                if model in self.installed_models():raise RuntimeError('Ollama chưa xác nhận AI đã được gỡ.')
                self.update(jid,'removed','Đã gỡ '+model+'. Lịch sử chat được giữ nguyên.',1.0)
                self.store.audit('installer','model_removed',{'model':model,'job':jid})
        except Exception as error:
            self.update(jid,'failed','Không gỡ được AI: '+str(error))
            self.store.audit('installer','model_remove_failed',{'model':model,'error':str(error)})
        finally:
            with self.lock:self.busy=False;self.active_target=None

    def stop_download(self, action):
        if action not in ('paused','cancelled'):raise ValueError('Thao tác tải không hợp lệ.')
        with self.lock:
            if not self.busy or self.active_target not in ALLOWED_MODELS:
                raise RuntimeError('Chỉ tạm dừng/hủy tác vụ tải AI đang chạy.')
            self.stop_action=action;self.stop_event.set()

    def check_stopped(self):
        if self.stop_event.is_set():raise DownloadStopped()

    def resume_download(self):
        paused=next((job for job in self.jobs() if job['status']=='paused'),None)
        if not paused:raise RuntimeError('Không có AI đang tạm dừng.')
        jid=self.request(paused['target'])
        self.update(paused['id'],'resumed','Đã tiếp tục bằng tác vụ mới: '+jid)
        return jid

    def process(self, jid, args, timeout=1200):
        log_folder=Path(os.environ['LOCALAPPDATA'])/'ChatAI'/'install-logs' if os.name=='nt' and os.environ.get('LOCALAPPDATA') else self.root/'data'
        log_folder.mkdir(parents=True,exist_ok=True)
        log=log_folder/f'install_{jid}.log'
        self.update(jid,'running','Đang khởi chạy bộ cài. Log: '+str(log))
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        # Cache pip mặc định nằm ngoài Drive; giữ cache để retry không tải lại từ đầu.
        env=os.environ.copy()
        env['PYTHONUNBUFFERED']='1'
        env.setdefault('PIP_PROGRESS_BAR','on')
        env.setdefault('PIP_VERBOSE','1')
        env.setdefault('PIP_DEFAULT_TIMEOUT','120'); env.setdefault('PIP_RETRIES','3')
        env.setdefault('HF_HUB_DOWNLOAD_TIMEOUT','120'); env.setdefault('HF_HUB_ETAG_TIMEOUT','30')
        with log.open("ab") as output:
            child = subprocess.Popen(args, stdout=output, stderr=subprocess.STDOUT,
                                     shell=False, creationflags=flags, env=env)
            start = time.monotonic()
            last, previous_tail = 0, None
            reported_quiet_bucket = -1
            last_output=time.monotonic()
            previous_size=log.stat().st_size
            try:
                while child.poll() is None:
                    if time.monotonic() - start > timeout:
                        child.kill()
                        child.wait()
                        raise TimeoutError("Tải/cài đặt quá thời gian; có thể tải lại từ giao diện.")
                    size=log.stat().st_size
                    if size!=previous_size:last_output=time.monotonic();previous_size=size
                    quiet=time.monotonic()-last_output
                    if time.monotonic() - last > 2:
                        with log.open("rb") as inp:
                            inp.seek(max(0, log.stat().st_size - 2500))
                            tail = inp.read().decode("utf-8", errors="replace")
                        quiet_bucket = int(quiet // 30)
                        if tail != previous_tail or quiet_bucket != reported_quiet_bucket:
                            progress=None
                            message=tail or f'Bộ cài chưa trả dữ liệu · {int(time.monotonic()-start)}s. Chưa xác nhận tải được byte nào.\nLog: {log}'
                            for line in reversed(tail.splitlines()):
                                if line.startswith('CHAT_AI_PROGRESS '):
                                    try:
                                        info=json.loads(line[len('CHAT_AI_PROGRESS '):]);total=info['total'];completed=info['completed']
                                        progress=min(.99,completed/total) if total else None
                                        model_label=MEDIA_VARIANTS[self.media_variant()]['display'] if self.active_target=='media' else 'Tải xuống'
                                        message=f"{model_label}: {completed/1e6:.1f} / {total/1e6:.1f} MB (các tệp đang tải) · {info['rate']/1e6:.2f} MB/s"
                                    except (ValueError,KeyError,TypeError):pass
                                    break
                            if quiet>=30:
                                message+=f'\nChưa có log mới {int(quiet)} giây; tác vụ vẫn đang chạy. Tự dừng khi chạm giới hạn thời gian cài đặt.'
                            self.update(jid, "running", message,progress)
                            previous_tail=tail
                            reported_quiet_bucket=quiet_bucket
                        last = time.monotonic()
                    time.sleep(0.25)
                if child.returncode:
                    with log.open("rb") as inp:
                        inp.seek(max(0, log.stat().st_size - 2500))
                        raise RuntimeError(inp.read().decode("utf-8", errors="replace"))
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()

    def installer_python(self):
        """Prefer the bundled console interpreter so background pip logs are captured on Windows."""
        bundled = self.root / "runtime" / "python" / "python.exe"
        marker = self.root / "runtime" / "python" / "chat-ai-runtime.json"
        if bundled.is_file() and marker.is_file():
            return str(bundled)
        return sys.executable

    def pull(self, jid, model):
        self.update(jid, "running", f"Đang tải model {model}…")
        last_write, last_status, last_digest = 0.0, None, None
        baseline, started = 0, time.monotonic()
        last_event = None
        self.check_stopped()
        stream=self.client.pull(model, stream=True)
        try:
            for event in stream:
                self.check_stopped()
                last_event = event
                current=time.monotonic()
                digest=getattr(event,'digest',None)
                total, completed = event.total or 0, event.completed or 0
                if digest != last_digest:
                    baseline, started = completed, current
                progress = min(completed / total, 1.0) if total else None
                # Tránh commit SQLite mỗi chunk, đặc biệt khi dự án nằm trên Google Drive.
                if current-last_write >= 1 or event.status != last_status or digest != last_digest:
                    rate=max(0,completed-baseline)/max(.001,current-started)
                    detail=f'{model}: {event.status}'
                    if total:
                        detail+=f' · {completed/1e6:.0f}/{total/1e6:.0f} MB (layer hiện tại)'
                        if rate>0:
                            detail+=f' · {rate/1e6:.1f} MB/s · còn khoảng {max(0,total-completed)/rate:.0f}s'
                    self.update(jid,'running',detail,progress)
                    last_write=current
                last_status,last_digest=event.status,digest
        finally:
            if hasattr(stream,'close'):stream.close()
        self.check_stopped()
        if model not in self.installed_models():
            raise RuntimeError("Ollama chưa báo model đã cài sau khi tải.")

    def worker(self, jid, target):
        try:
            with execution_lock(self.installer_lock):
                media_variant=self.media_variant() if target=="media" else "sd-turbo"
                need_gb = MEDIA_VARIANTS[media_variant]["disk_gb"] if target=="media" else 4 if target == "python" else CHAT_MODELS.get(target, {}).get("disk_gb", 2)
                disk_path = self.root
                if shutil.disk_usage(disk_path).free < need_gb * 1024**3:
                    location = "ổ cục bộ" if target == "media" else "ổ dự án"
                    raise RuntimeError(f"Cần ít nhất {need_gb} GiB trống trên {location}. Kiểm tra thêm ổ chứa AI của Ollama.")
                if target in ALLOWED_MODELS or (target in MODULES and MODULES[target]['models']):
                    from .ollama_setup import ensure_ollama
                    ensure_ollama(self.client,self.root,lambda message,progress=None:(self.check_stopped(),self.update(jid,'running',message,progress)))
                if target in ALLOWED_MODELS:
                    self.pull(jid, target)
                else:
                    spec = MODULES[target]
                    if spec["packages"] and any(importlib.util.find_spec(name) is None for name in spec["imports"]):
                        if sys.prefix == sys.base_prefix and not ((self.root/'runtime/python/python.exe').is_file() and Path(sys.executable).resolve().parent==(self.root/'runtime/python').resolve() and (self.root/'runtime/python/chat-ai-runtime.json').is_file()):
                            raise RuntimeError("Chat AI chưa chạy trong môi trường riêng. Hãy đóng ứng dụng rồi mở lại run.bat để tự tạo .venv; không cài module vào Python hệ thống.")
                        if target == "media_basic":
                            self.update(jid, "running", "Đang tự cài thư viện ảnh/video vào runtime nền; bạn vẫn có thể chat.")
                        else:
                            self.update(jid, "running", "Đang cài thư viện vào .venv. Module sẽ cần khởi động lại app.")
                        installer_python = self.installer_python()
                        if target == "media":
                            self.process(jid, [installer_python, "-m", "pip", "install", "--disable-pip-version-check",
                                "--only-binary=:all:", "--index-url", "https://download.pytorch.org/whl/cu126",
                                "torch==2.6.0+cu126"])
                        self.process(jid, [installer_python, "-m", "pip", "install", "--disable-pip-version-check",
                            "--only-binary=:all:", "--index-url", "https://pypi.org/simple", *spec["packages"]])
                        importlib.invalidate_caches()
                    if target == "media":
                        folder = media_model_dir(self.root,media_variant)
                        if not (folder / "ready.json").is_file():
                            spec=MEDIA_VARIANTS[media_variant]
                            self.update(jid, "running", f"Đang tải {spec['display']} từ Hugging Face…")
                            self.process(jid, [self.installer_python(), str(self.root / 'assistant' / 'download_media.py'), str(folder), media_variant], timeout=10800)
                    for model in spec["models"]:
                        if model not in self.installed_models():
                            self.pull(jid, model)
                    if target == "python":
                        docker = shutil.which("docker")
                        if not docker:
                            raise RuntimeError("Cần cài Docker Desktop và bật Linux containers trước.")
                        self.update(jid, "running", f"Đang tải {IMAGE}…")
                        self.process(jid, [docker, "pull", BASE_IMAGE])
                        self.update(jid, "running", "Đang dựng Python sandbox: PDF, Word, Excel và thư viện ảnh/video…")
                        build_context=self.root / "data" / "python-build"
                        build_context.mkdir(parents=True,exist_ok=True)
                        shutil.copyfile(self.root / "Dockerfile.python-tools",build_context / "Dockerfile")
                        self.process(jid, [docker, "build", "-t", IMAGE, str(build_context)], timeout=1800)
                    self.set_enabled(target, True)
                message = "Hoàn tất. Model/image sẵn sàng."
                if target == "media_basic":
                    message = "Đã cài thư viện ảnh/video cơ bản. Có thể dùng ngay, không cần tải model AI."
                elif target in MODULES and MODULES[target]["packages"]:
                    message = "Đã cài và bật module. Đóng cửa sổ ứng dụng rồi mở lại run.bat để nạp thư viện mới."
                self.update(jid, "succeeded", message, 1.0)
                self.store.audit("installer", "download_success", {"target": target, "job": jid})
        except DownloadStopped:
            action=self.stop_action or 'cancelled'
            message=('Đã tạm dừng. Bấm Tiếp tục tải để yêu cầu Ollama tiếp tục từ cache nếu có.' if action=='paused' else 'Đã hủy tác vụ tải. AI đã cài vẫn được giữ; phần tải dở do Ollama quản lý.')
            self.update(jid,action,message)
            self.store.audit('installer','download_'+action,{'target':target,'job':jid})
        except Exception as exc:
            self.update(jid, "failed", str(exc))
            self.store.audit("installer", "download_failed", {"target": target, "error": str(exc)})
        finally:
            with self.lock:
                self.busy = False
                self.active_target=None

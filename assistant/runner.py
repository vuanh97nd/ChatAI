import os
import json
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from .modules import IMAGE


class Runner:
    def __init__(self, files, audit):
        self.files, self.audit = files, audit

    def prepare(self, name, args):
        if not shutil.which("docker"):
            raise RuntimeError("Cần Docker Desktop. Bật module Python và tải image trước.")
        if name == "python_run":
            code = args["code"]
            if not isinstance(code, str) or not code.strip() or len(code) > 16000:
                raise ValueError("Code Python tối đa 16000 ký tự.")
            inputs=args.get('files',[])
            if not isinstance(inputs,list) or len(inputs)>8:raise ValueError('Tối đa 8 file đầu vào.')
            from .excel import digest
            records=[];names=set();total=0
            for raw in inputs:
                p=self.files.path(raw)
                if not p.is_file():raise ValueError('Đầu vào phải là file trong whitelist.')
                if p.name.casefold() in names:raise ValueError('Tên file đầu vào trùng nhau.')
                names.add(p.name.casefold());total+=p.stat().st_size
                if total>20*1024**2:raise ValueError('File đầu vào vượt 20 MiB.')
                records.append({'path':str(p),'name':p.name,'sha256':digest(p)})
            return {"action": name, "code": code, "inputs":records, "approval_id": uuid.uuid4().hex,
                    "outputs": {"path": "workspace/outputs", "max_files": 10, "max_total_bytes": 50*1024**2},
                    "limits": "Linux container: RAM 512 MiB, 1 CPU, 30 giây, không mạng, không GPU. Ảnh/video tạo trong /output được lưu vào workspace/outputs sau khi duyệt."}
        command = args["command"]
        if not isinstance(command, str) or not command.strip() or len(command) > 2000:
            raise ValueError("Lệnh tối đa 2000 ký tự.")
        folder = self.files.path(args.get("path", "."))
        if not folder.is_dir():
            raise ValueError("Thư mục lệnh phải thuộc whitelist.")
        return {"action": name, "command": command, "path": str(folder),
                "approval_id": uuid.uuid4().hex,
                "limits": "Shell Linux cách ly, mount thư mục whitelist chỉ đọc. Không chạy cmd/PowerShell trên host."}

    def snapshot(self, source, dest):
        """Chỉ copy file canonical trong whitelist; bỏ symlink/junction, tối đa 200 file/20 MiB."""
        dest.mkdir()
        dest.chmod(0o755)
        size, count = 0, 0
        for folder, dirs, files in os.walk(source, followlinks=False):
            rel = Path(folder).relative_to(source)
            if len(rel.parts) > 5:
                dirs[:] = []
                continue
            valid = []
            for name in dirs:
                p = Path(folder) / name
                attributes = getattr(p.lstat(), "st_file_attributes", 0)
                if name.startswith(".") or name.startswith("ai_run_") or p.is_symlink() or attributes & 0x400:
                    continue
                self.files.path(str(p))
                valid.append(name)
            dirs[:] = valid
            target = dest / rel
            target.mkdir(parents=True, exist_ok=True)
            target.chmod(0o755)
            for name in files:
                p = Path(folder) / name
                attributes = getattr(p.lstat(), "st_file_attributes", 0)
                if name.startswith(".") or p.is_symlink() or attributes & 0x400:
                    continue
                checked = self.files.path(str(p))
                count += 1
                size += checked.stat().st_size
                if count > 200 or size > 20*1024**2:
                    raise ValueError("Thư mục lệnh vượt giới hạn snapshot 200 file/20 MiB.")
                shutil.copyfile(checked, target / name)
                (target / name).chmod(0o644)

    def commit(self, plan):
        docker = shutil.which("docker")
        if not docker:
            raise RuntimeError("Docker không còn sẵn sàng.")
        root = self.files.roots[0]
        self.audit("run_started", plan)
        # Thư mục tạm nằm trong whitelist, tự xóa sau chạy; không mount toàn bộ host.
        with tempfile.TemporaryDirectory(prefix="ai_run_", dir=root) as raw:
            temp = Path(raw)
            temp.chmod(0o755)
            if plan["action"] == "python_run":
                (temp / "script.py").write_text(plan["code"], encoding="utf-8")
                (temp / "script.py").chmod(0o644)
                if plan.get('inputs'):
                    from .excel import digest
                    folder=temp/'input';folder.mkdir();folder.chmod(0o755)
                    for record in plan['inputs']:
                        source=self.files.path(record['path'])
                        if digest(source)!=record['sha256']:raise RuntimeError('File đổi sau chuẩn bị; yêu cầu đọc lại.')
                        target=folder/record['name'];shutil.copyfile(source,target);target.chmod(0o644)
                        if digest(target)!=record['sha256']:raise RuntimeError('Snapshot file không khớp.')
                if 'search_data' in plan:
                    (temp/'search-data.json').write_text(json.dumps(plan['search_data'],ensure_ascii=False),encoding='utf-8')
                    (temp/'search-data.json').chmod(0o644)
                output_mount=temp/'output';output_mount.mkdir();output_mount.chmod(0o777)
                mount = temp.resolve()
                program = ["python", "-I", "/workspace/script.py"]
            else:
                source = self.files.path(plan["path"])
                mount = temp / "snapshot"
                self.snapshot(source, mount)
                program = ["sh", "-c", plan["command"]]
            if "," in str(mount):
                raise ValueError("Docker mount không hỗ trợ đường dẫn chứa dấu phẩy trong bản này.")
            name = "local_ai_" + uuid.uuid4().hex
            args = [docker, "run", "--rm", "--pull=never", "--name", name,
                    "--network=none", "--memory=512m", "--memory-swap=512m", "--cpus=1",
                    "--pids-limit=64", "--read-only", "--cap-drop=ALL",
                    "--security-opt=no-new-privileges", "--user=65534:65534",
                    "--ulimit", "fsize=52428800:52428800", "--ulimit", "nofile=128:128",
                    "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m,mode=1777",
                    "--mount", f"type=bind,source={mount},target=/workspace,readonly",
                    "--workdir=/tmp", IMAGE, *program]
            if plan["action"] == "python_run":
                args[args.index("--workdir=/tmp"):args.index("--workdir=/tmp")] = [
                    "--mount", f"type=bind,source={output_mount.resolve()},target=/output"]
            out_path, err_path = temp / "stdout.log", temp / "stderr.log"
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            timed_out, capped = False, False
            with out_path.open("wb") as out, err_path.open("wb") as err:
                child = subprocess.Popen(args, stdout=out, stderr=err, shell=False, creationflags=flags)
                start = time.monotonic()
                try:
                    while child.poll() is None:
                        timed_out = time.monotonic() - start > 30
                        capped = out_path.stat().st_size + err_path.stat().st_size > 1024**2
                        if timed_out or capped:
                            subprocess.run([docker, "rm", "-f", name], capture_output=True, timeout=10)
                            child.kill()
                            child.wait(timeout=10)
                            break
                        time.sleep(0.1)
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.wait(timeout=10)
                    subprocess.run([docker, "rm", "-f", name], capture_output=True, timeout=10)
            def read_output(p):
                with p.open("rb") as file:
                    return file.read(8000).decode("utf-8", errors="replace")
            result = {"ok": child.returncode == 0 and not timed_out and not capped,
                      "exit_code": child.returncode, "stdout": read_output(out_path),
                      "stderr": read_output(err_path), "timed_out": timed_out,
                      "output_limit_exceeded": capped,
                      "note": "File đầu ra Python nằm trong /output và chỉ được lưu trong workspace/outputs sau khi chạy đã được người dùng duyệt."}
            if plan["action"] == "python_run" and result["ok"]:
                candidates=sorted(output_mount.iterdir(),key=lambda p:p.name.casefold())
                if len(candidates)>10:raise RuntimeError("Python tạo quá 10 file đầu ra.")
                total=0
                for candidate in candidates:
                    if candidate.is_symlink() or not candidate.is_file():raise RuntimeError("Đầu ra chỉ được gồm file thường, không gồm symlink/thư mục.")
                    total+=candidate.stat().st_size
                    safe_name=Path(candidate.name).name
                    if not safe_name or safe_name.startswith('.') or len(safe_name)>150:raise RuntimeError("Tên file đầu ra không hợp lệ.")
                if total>50*1024**2:raise RuntimeError("Tổng file đầu ra vượt 50 MiB.")
                destination=self.files.path("outputs",exists=False)
                destination.mkdir(parents=True,exist_ok=True)
                generated=[]
                for candidate in candidates:
                    safe_name=Path(candidate.name).name
                    target=self.files.path(str(destination/(uuid.uuid4().hex[:8]+'_'+safe_name)),exists=False)
                    shutil.copyfile(candidate,target)
                    generated.append(str(target))
                result["artifacts"]=generated
            self.audit("run_result", result)
            return result

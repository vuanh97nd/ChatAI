"""Prepare local Ollama after the user approves an AI download."""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse

INSTALLER_URL = 'https://ollama.com/download/OllamaSetup.exe'
MAX_INSTALLER = 2 * 1024**3
WINDOWS = os.name == 'nt'
NO_WINDOW = getattr(subprocess,'CREATE_NO_WINDOW',0)


def service_ready(host):
    parsed=urlparse(host)
    if parsed.scheme!='http' or parsed.hostname not in ('localhost','127.0.0.1','::1') or parsed.username or parsed.password:
        raise ValueError('Chỉ khởi động Ollama cho địa chỉ loopback local.')
    try:
        with urlopen(host.rstrip('/')+'/api/version',timeout=2) as response:
            return bool(json.loads(response.read(8192)).get('version'))
    except Exception:return False


def find_executable():
    found=shutil.which('ollama')
    candidates=[Path(found)] if found else []
    if os.environ.get('LOCALAPPDATA'):
        candidates.append(Path(os.environ['LOCALAPPDATA'])/'Programs/Ollama/ollama.exe')
    if WINDOWS:
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive,r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{44E83376-CE68-45EB-8FC1-393500EB558C}_is1') as key:
                    folder=winreg.QueryValueEx(key,'InstallLocation')[0]
                    candidates.append(Path(folder)/'ollama.exe')
            except OSError:pass
    return next((p for p in candidates if p.is_file()),None)


def download_installer(path, progress):
    temporary=path.with_suffix('.part')
    started=last=time.monotonic();received=0
    try:
        with urlopen(Request(INSTALLER_URL,headers={'User-Agent':'ChatAI-Installer'}),timeout=60) as response,temporary.open('wb') as output:
            if urlparse(response.geturl()).scheme!='https':raise RuntimeError('Đường dẫn tải Ollama không dùng HTTPS.')
            total=int(response.headers.get('Content-Length') or 0)
            if total>MAX_INSTALLER:raise RuntimeError('Bộ cài Ollama vượt giới hạn tải 2 GiB.')
            while True:
                chunk=response.read(256*1024)
                if not chunk:break
                output.write(chunk);received+=len(chunk)
                if received>MAX_INSTALLER:raise RuntimeError('Bộ cài Ollama vượt giới hạn tải 2 GiB.')
                current=time.monotonic()
                if current-started>3600:raise TimeoutError('Tải Ollama quá 60 phút; thử lại khi kết nối ổn định.')
                if current-last>=1:
                    detail=f'Đang tải Ollama: {received/1e6:.1f} MB'
                    if total:detail+=f' / {total/1e6:.1f} MB'
                    detail+=f' · {received/max(.01,current-started)/1e6:.1f} MB/s'
                    progress(detail,received/total if total else None);last=current
            if not received or (total and received!=total):raise RuntimeError('Bộ cài Ollama tải chưa đầy đủ.')
        temporary.replace(path)
    finally:temporary.unlink(missing_ok=True)


def verify_installer(path):
    # File path is passed as an argument, never interpolated into shell code.
    script="$s=Get-AuthenticodeSignature -LiteralPath $env:CHAT_AI_INSTALLER_VERIFY_PATH; if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch '(^|, )O=Ollama Inc\\.(,|$)') {exit 1}"
    env=os.environ.copy();env['CHAT_AI_INSTALLER_VERIFY_PATH']=str(path)
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],env=env,capture_output=True,timeout=120,creationflags=NO_WINDOW)
    if result.returncode:raise RuntimeError('Không xác minh được chữ ký chính thức của bộ cài Ollama. Chưa thực thi bộ cài.')


def ensure_ollama(client, root, progress):
    if not WINDOWS:
        client.list();return
    host=getattr(client,'host','http://127.0.0.1:11434')
    if service_ready(host):return
    folder=Path(os.environ['LOCALAPPDATA'])/'ChatAI/install-logs'
    folder.mkdir(parents=True,exist_ok=True)
    exe=find_executable()
    if exe is None:
        progress('Chưa có Ollama. Đang tải bộ cài chính thức…',None)
        if shutil.disk_usage(folder).free<3*1024**3:raise RuntimeError('Cần ít nhất 3 GiB trống trên ổ cài Ollama.')
        installer=folder/'OllamaSetup.exe'
        download_installer(installer,progress)
        try:
            progress('Đang xác minh chữ ký bộ cài Ollama…',None)
            verify_installer(installer)
            progress('Đang cài Ollama dưới nền…',None)
            log=folder/'ollama-install.log'
            result=subprocess.run([str(installer),'/VERYSILENT','/NORESTART','/SUPPRESSMSGBOXES',f'/LOG={log}'],timeout=1200,creationflags=NO_WINDOW)
            if result.returncode not in (0,3010):raise RuntimeError(f'Cài Ollama thất bại, mã {result.returncode}. Nhật ký: {log}')
            exe=find_executable()
            if exe is None:raise RuntimeError('Bộ cài đã kết thúc nhưng chưa tìm thấy ollama.exe.')
        finally:installer.unlink(missing_ok=True)
    if service_ready(host):return
    progress('Đang khởi động Ollama…',None)
    env=os.environ.copy();env['OLLAMA_HOST']=host
    env['OLLAMA_MAX_LOADED_MODELS']='1';env['OLLAMA_NUM_PARALLEL']='1'
    env['OLLAMA_NO_CLOUD']='1'
    # Preserve a user-applied GPU workaround rather than modifying global settings.
    if 'GGML_CUDA_PDL' not in env:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as key:
                env['GGML_CUDA_PDL']=str(winreg.QueryValueEx(key,'GGML_CUDA_PDL')[0])
        except OSError:pass
    log=folder/'ollama-service.log'
    with log.open('ab') as output:
        process=subprocess.Popen([str(exe),'serve'],stdout=output,stderr=subprocess.STDOUT,env=env,creationflags=NO_WINDOW)
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        if service_ready(host):return
        if process.poll() is not None:
            if service_ready(host):return
            raise RuntimeError(f'Ollama không khởi động được. Nhật ký: {log}')
        time.sleep(.5)
    raise TimeoutError(f'Ollama chưa sẵn sàng sau 45 giây. Nhật ký: {log}')

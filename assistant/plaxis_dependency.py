"""Diagnostics use the interpreter running ChatAI, never the user's default Python."""
import sys
from pathlib import Path


def missing_scripting_message():
    python=Path(sys.executable)
    if python.name.lower()=='pythonw.exe':python=python.with_name('python.exe')
    quoted=str(python).replace("'","''")
    if getattr(sys,'frozen',False):
        return ('Bản ChatAI đóng gói này thiếu plxscripting. Không chạy pip bằng file EXE của ứng dụng. '
                'Cần cập nhật bộ cài có thư viện Plaxis hoặc chạy script bằng môi trường Python đã cài plxscripting.')
    return ('Python đang chạy ChatAI: '+str(python)+'. Thiếu hoặc không nhập được plxscripting trong môi trường này. '
            'Vào Tải công cụ → Plaxis Remote Scripting → Bật / Tải; hoặc chạy trong PowerShell:\n'
            "& '"+quoted+"' -m pip install 'plxscripting>=1,<2'\n"
            "& '"+quoted+"' -c \"import plxscripting; print(plxscripting.__file__)\"\n"
            'Sau khi cài thành công, đóng hoàn toàn và mở lại ChatAI. '
            'Cài vào Python khác không bổ sung thư viện cho ChatAI.')

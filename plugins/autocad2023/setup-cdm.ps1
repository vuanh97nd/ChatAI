$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (!(Test-Path $python)) {
    & py -3 -m venv (Join-Path $repo '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Cần Python 3.10+ trên Windows (py -3).' }
}
& $python -m pip install 'ezdxf>=1.3,<2'
if ($LASTEXITCODE -ne 0) { throw 'Chưa cài được ezdxf.' }
Write-Host "Đã chuẩn bị bộ tạo CDM. Chọn thư mục $repo trong bảng CHATAI."

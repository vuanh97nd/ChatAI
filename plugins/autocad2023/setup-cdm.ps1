$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (!(Test-Path $python)) {
    & py -3 -m venv (Join-Path $repo '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ is required on Windows (py -3).' }
}
& $python -m pip install 'ezdxf>=1.3,<2'
if ($LASTEXITCODE -ne 0) { throw 'Could not install ezdxf.' }
Write-Host "CDM setup complete. Select $repo in the CHATAI panel."

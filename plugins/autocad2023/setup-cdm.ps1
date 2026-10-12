param([string]$PythonPath = '')
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$venv = Join-Path $repo '.venv'
$python = Join-Path $repo '.venv\Scripts\python.exe'

function Test-Python([string]$Executable, [string[]]$Prefix = @()) {
    try {
        & $Executable @Prefix -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' *> $null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

if (!(Test-Path $python) -or !(Test-Python $python)) {
    # Find a usable base interpreter before touching the existing environment.
    $candidates = @()
    if ($PythonPath) {
        $candidates += @{Executable=$PythonPath; Prefix=@()}
    } else {
        $launcher = Get-Command py -ErrorAction SilentlyContinue
        if ($launcher) {
            foreach ($version in @('-3.13', '-3.12', '-3.11', '-3.10', '-3')) {
                $candidates += @{Executable=$launcher.Source; Prefix=@($version)}
            }
        }
        foreach ($name in @('python', 'python3')) {
            $command = Get-Command $name -ErrorAction SilentlyContinue
            if ($command) { $candidates += @{Executable=$command.Source; Prefix=@()} }
        }
    }
    $base = $null
    foreach ($candidate in $candidates) {
        if (Test-Python $candidate.Executable $candidate.Prefix) { $base = $candidate; break }
    }
    if (!$base) {
        throw 'No working Python 3.10+ found. Install Python or rerun with -PythonPath C:\path\to\python.exe. Existing .venv was preserved.'
    }
    if (Test-Path $venv) {
        $backup = Join-Path $repo ('.venv-backup-' + [guid]::NewGuid().ToString('N'))
        Move-Item $venv $backup
        Write-Host "Broken environment preserved at $backup"
    }
    $exe = $base.Executable
    $prefix = $base.Prefix
    & $exe @prefix -m venv $venv
    if ($LASTEXITCODE -ne 0 -or !(Test-Python $python)) { throw 'Could not create a working .venv. Previous environment is in the backup folder.' }
}
& $python -m pip install 'ezdxf>=1.3,<2'
if ($LASTEXITCODE -ne 0) { throw 'Could not install ezdxf.' }
Write-Host "CDM setup complete. Select $repo in the CHATAI panel."

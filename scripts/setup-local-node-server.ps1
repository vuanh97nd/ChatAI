param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'ChatAI\NodeServer'),
    [switch]$InstallNode,
    [switch]$Start
)
$ErrorActionPreference = 'Stop'
$Revision = '0835d0ddda312935c311393bc922dc690e54fac3'
$Repository = 'https://github.com/danieldev23/chatgpt-nodejs.git'
if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) {
    if (-not $InstallNode) { throw 'Install Node.js LTS, or rerun with -InstallNode.' }
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) { throw 'winget is unavailable. Install Node.js LTS from nodejs.org, then rerun.' }
    & winget.exe install --id OpenJS.NodeJS.LTS --exact --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw 'Node.js installation did not complete.' }
    $env:PATH = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
}
if (-not (Get-Command node.exe -ErrorAction SilentlyContinue) -or -not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Open a new PowerShell window after installing Node.js, then rerun.' }
$NodeMajor = [int]((& node.exe --version).TrimStart('v').Split('.')[0])
if ($NodeMajor -lt 22) { throw 'Node.js 22 or newer is required.' }
if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) { throw 'Git is required. Install Git for Windows, then rerun.' }
$Marker = Join-Path $InstallDir '.chatai-node-revision'
if (Test-Path $InstallDir) {
    if (-not (Test-Path $Marker) -or (Get-Content -LiteralPath $Marker -Raw).Trim() -ne $Revision) {
        throw 'Existing folder is not this managed installation. Choose a new -InstallDir; nothing deleted.'
    }
} else {
    & git.exe clone --no-checkout --depth 1 $Repository $InstallDir
    if ($LASTEXITCODE -ne 0) { throw 'Could not download Node.js server.' }
    & git.exe -C $InstallDir fetch --depth 1 origin $Revision
    if ($LASTEXITCODE -ne 0) { throw 'Could not fetch the pinned revision.' }
    & git.exe -C $InstallDir checkout --detach $Revision
    if ($LASTEXITCODE -ne 0) { throw 'Could not check out the pinned revision.' }
    Set-Content -LiteralPath $Marker -Value $Revision -Encoding ASCII
}
$Index = Join-Path $InstallDir 'src\index.ts'
$Source = Get-Content -LiteralPath $Index -Raw
$Source = $Source.Replace('host: "0.0.0.0"', 'host: "127.0.0.1"').Replace('http://0.0.0.0:', 'http://127.0.0.1:')
if (-not $Source.Contains('host: "127.0.0.1"')) { throw 'Cannot verify loopback listener; installation stopped.' }
Set-Content -LiteralPath $Index -Value $Source -Encoding UTF8
$EnvFile = Join-Path $InstallDir '.env'
if (-not (Test-Path $EnvFile)) {
    $Bytes = New-Object byte[] 32
    $Rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $Rng.GetBytes($Bytes) } finally { $Rng.Dispose() }
    $ServerKey = -join ($Bytes | ForEach-Object { $_.ToString('x2') })
    Set-Content -LiteralPath $EnvFile -Encoding ASCII -Value @(
        'PORT=3040', ('CHATGPT2API_AUTH_KEY=' + $ServerKey), 'STORAGE_BACKEND=json', 'LOG_LEVEL=info'
    )
    $ServerKey = $null
}
Push-Location $InstallDir
try {
    & npm.cmd ci --ignore-scripts --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Existing .env/data are preserved.' }
    & npm.cmd run build:tsc
    if ($LASTEXITCODE -ne 0) { throw 'Build failed; server was not started.' }
} finally { Pop-Location }
$Launcher = Join-Path $InstallDir 'start-local.ps1'
Set-Content -LiteralPath $Launcher -Encoding ASCII -Value @'
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path '.env')) { throw 'Missing .env' }
Write-Host 'Local Node.js server. Keep this window open; Ctrl+C stops it.'
& node.exe '.\dist\index.js'
'@
$Desktop = [Environment]::GetFolderPath('Desktop')
if ($Desktop -and (Test-Path $Desktop)) {
    $Shortcut = Join-Path $Desktop 'ChatAI Node Server.lnk'
    $Shell = New-Object -ComObject WScript.Shell
    $Link = $Shell.CreateShortcut($Shortcut)
    $Link.TargetPath = (Get-Command powershell.exe).Source
    $Link.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $Launcher + '"'
    $Link.WorkingDirectory = $InstallDir
    $Link.Save()
}
Write-Host ('Installed: ' + $InstallDir)
$PortLine = Get-Content -LiteralPath $EnvFile | Where-Object { $_ -match '^PORT=[0-9]+$' } | Select-Object -First 1
if (-not $PortLine) { throw 'Missing or invalid PORT in .env.' }
Write-Host ('API URL: http://127.0.0.1:' + $PortLine.Substring(5))
Write-Host 'Server key is in .env (not printed). Use local-node-server.ps1 -Action CopyKey to copy it.'
Write-Host 'A successful startup/health check is not a successful chat. Configure your own account pool next.'
if ($Start) {
    Start-Process powershell.exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $Launcher + '"'))
}

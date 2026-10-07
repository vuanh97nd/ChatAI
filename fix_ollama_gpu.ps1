$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
function Server-Running {
    try {
        $null = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
        return $true
    } catch { return $false }
}
try {
    Write-Host 'Chat AI - thu cau hinh CUDA: tat PDL, van dung GPU.'
    if (Server-Running) {
        Write-Host 'Ollama dang chay. Hay Quit Ollama o khay he thong.'
        Write-Host 'Neu da Quit ma van chay, dong Ollama trong Task Manager.'
        $null = Read-Host 'Nhan Enter sau khi da thoat Ollama (Ctrl+C de huy)'
        if (Server-Running) { throw 'Ollama van chay. Chua thay doi cau hinh; hay thoat Ollama roi chay lai tep nay.' }
    }
    $command = Get-Command ollama.exe -ErrorAction SilentlyContinue
    $exe = if ($command) { $command.Source } else { Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe' }
    if (-not (Test-Path -LiteralPath $exe)) { throw 'Khong tim thay ollama.exe. Hay cai/kiem tra Ollama tren may.' }
    $previous = [Environment]::GetEnvironmentVariable('GGML_CUDA_PDL','User')
    $data = Join-Path $PSScriptRoot 'data'
    New-Item -ItemType Directory -Force -Path $data | Out-Null
    $backup = Join-Path $data 'ollama-pdl-before-fix.json'
    if (-not (Test-Path -LiteralPath $backup)) {
        @{ value = $previous; saved_at = (Get-Date).ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath $backup -Encoding UTF8
    }
    [Environment]::SetEnvironmentVariable('GGML_CUDA_PDL','0','User')
    $env:GGML_CUDA_PDL = '0'
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $stdout = Join-Path $data "ollama-pdl-$stamp.stdout.log"
    $stderr = Join-Path $data "ollama-pdl-$stamp.stderr.log"
    $process = Start-Process -FilePath $exe -ArgumentList 'serve' -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $ready = $false
    for ($i=0; $i -lt 20; $i++) {
        $process.Refresh()
        if ($process.HasExited) { throw "Ollama khong khoi dong duoc. Xem: $stderr" }
        if (Server-Running) { $ready=$true; break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "Chua ket noi duoc Ollama. Xem: $stderr" }
    Write-Host 'Ollama da mo voi GGML_CUDA_PDL=0. Dang mo Chat AI...'
    Write-Host "Nhat ky Ollama cua lan nay: $stderr"
    Write-Host 'Day la cau hinh thu; chua xac nhan AI chay thanh cong cho den khi gui tin nhan.'
    exit 0
} catch {
    Write-Host ('Loi: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}

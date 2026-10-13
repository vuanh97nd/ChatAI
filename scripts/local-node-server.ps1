param(
    [ValidateSet('Health','CopyKey','AddAccount','Models','Test')][string]$Action = 'Health',
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'ChatAI\NodeServer'),
    [string]$Model = ''
)
$ErrorActionPreference = 'Stop'
$EnvFile = Join-Path $InstallDir '.env'
if (-not (Test-Path $EnvFile)) { throw 'Run setup-local-node-server.ps1 first.' }
$Settings = @{}
foreach ($Line in Get-Content -LiteralPath $EnvFile) {
    if ($Line -match '^([A-Z0-9_]+)=(.*)$') { $Settings[$Matches[1]] = $Matches[2].Trim() }
}
$ServerKey = $Settings['CHATGPT2API_AUTH_KEY']
if (-not $ServerKey) { throw 'Server key is missing from .env.' }
$Port = [int]$Settings['PORT']
$BaseUrl = 'http://127.0.0.1:' + $Port
if ($Action -eq 'CopyKey') {
    Set-Clipboard -Value $ServerKey
    Write-Host 'Server key copied. Paste into Chat AI > Custom backup API > Server key.'
    return
}
$Headers = @{ Authorization = 'Bearer ' + $ServerKey }
try {
    switch ($Action) {
        'Health' {
            $null = Invoke-RestMethod -Uri ($BaseUrl + '/health') -TimeoutSec 10
            Write-Host ('Server is responding at ' + $BaseUrl + '. Chat/account access is not yet verified.')
        }
        'Models' {
            $Result = Invoke-RestMethod -Uri ($BaseUrl + '/v1/models') -Headers $Headers -TimeoutSec 30
            $Result.data | Select-Object id
        }
        'AddAccount' {
            Write-Host 'Use only your own ChatGPT account. Never paste its token into chat or a shared log.'
            $Secret = Read-Host 'Paste your accessToken locally (input is hidden)' -AsSecureString
            $Ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secret)
            try {
                $Token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Ptr)
                if (-not $Token) { throw 'Empty token.' }
                $Body = @{ tokens = @($Token) } | ConvertTo-Json -Compress
                $Result = Invoke-RestMethod -Method Post -Uri ($BaseUrl + '/api/accounts') -Headers $Headers -ContentType 'application/json' -Body $Body -TimeoutSec 30
                Write-Host ('Accounts added/updated: ' + $Result.count + '. Upstream chat is not yet verified.')
            } finally {
                [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Ptr)
                $Token = $null; $Body = $null; $Secret.Dispose()
            }
        }
        'Test' {
            if (-not $Model) { throw 'Pass -Model with a model returned by -Action Models.' }
            $Body = @{ model = $Model; messages = @(@{ role='user'; content='Reply only OK.' }); max_tokens=64; stream=$false } | ConvertTo-Json -Depth 8
            $Result = Invoke-RestMethod -Method Post -Uri ($BaseUrl + '/v1/chat/completions') -Headers $Headers -ContentType 'application/json' -Body $Body -TimeoutSec 60
            $Answer = $Result.choices[0].message.content
            if (-not $Answer) { throw 'No chat content returned.' }
            Write-Host ('Chat response: ' + $Answer)
        }
    }
} catch {
    Write-Host 'Request did not complete. Check the server window, URL/port, account status and selected model. Credentials are not printed.'
    exit 1
}

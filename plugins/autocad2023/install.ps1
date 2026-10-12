param([string]$AutoCADPath = 'C:\Program Files\Autodesk\AutoCAD 2023')
$ErrorActionPreference = 'Stop'
if (Get-Process acad -ErrorAction SilentlyContinue) { throw 'Đóng AutoCAD trước khi cài/cập nhật plugin.' }
$compiler = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (!(Test-Path $compiler)) { throw 'Cần Windows và .NET Framework 4.8.' }
$refs = @('AcCoreMgd.dll', 'AcDbMgd.dll', 'AcMgd.dll')
foreach ($ref in $refs) { if (!(Test-Path (Join-Path $AutoCADPath $ref))) { throw "Không tìm thấy $ref tại $AutoCADPath" } }
$output = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Force $output | Out-Null
$arguments = @('/nologo', '/target:library', '/platform:x64', '/utf8output', "/out:$output\ChatAI.AutoCAD2023.dll",
    '/reference:System.dll', '/reference:System.Core.dll', '/reference:System.Drawing.dll',
    '/reference:System.Windows.Forms.dll', '/reference:System.Net.Http.dll', '/reference:System.Web.Extensions.dll')
foreach ($ref in $refs) { $arguments += "/reference:$AutoCADPath\$ref" }
$arguments += (@('ChatClient.cs', 'CadTools.cs', 'ChatPalette.cs', 'CdmBridge.cs') | ForEach-Object { Join-Path $PSScriptRoot $_ })
& $compiler @arguments
if ($LASTEXITCODE -ne 0) { throw 'Biên dịch thất bại; chưa cài plugin.' }
$bundle = Join-Path $env:APPDATA 'Autodesk\ApplicationPlugins\ChatAI2023.bundle'
if (Test-Path $bundle) {
    $backup = Join-Path $env:LOCALAPPDATA ('ChatAI\PluginBackups\ChatAI2023-' + [guid]::NewGuid().ToString('N') + '.bundle')
    New-Item -ItemType Directory -Force (Split-Path $backup) | Out-Null
    Move-Item $bundle $backup
    Write-Host "Đã giữ plugin cũ tại $backup"
}
New-Item -ItemType Directory (Join-Path $bundle 'Contents') -Force | Out-Null
Copy-Item "$output\ChatAI.AutoCAD2023.dll" (Join-Path $bundle 'Contents')
Copy-Item (Join-Path $PSScriptRoot 'PackageContents.xml') $bundle
Write-Host "Đã cài $bundle. Khởi động lại AutoCAD 2023 và gõ CHATAI."

param([string]$AutoCADPath = 'C:\Program Files\Autodesk\AutoCAD 2023')
$ErrorActionPreference = 'Stop'
if (Get-Process acad -ErrorAction SilentlyContinue) { throw 'Close AutoCAD before installing/updating this plugin.' }
$compiler = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (!(Test-Path $compiler)) { throw 'Windows and .NET Framework 4.8 are required.' }
$refs = @('AcCoreMgd.dll', 'AcDbMgd.dll', 'AcMgd.dll')
foreach ($ref in $refs) { if (!(Test-Path (Join-Path $AutoCADPath $ref))) { throw "Missing $ref in $AutoCADPath" } }
$framework = Split-Path $compiler
$wpfReferences = @()
foreach ($name in @('PresentationCore.dll', 'PresentationFramework.dll', 'WindowsBase.dll')) {
    $reference = Join-Path $framework "WPF\$name"
    if (!(Test-Path $reference)) { $reference = Join-Path $framework $name }
    if (!(Test-Path $reference)) { throw "Missing .NET WPF reference: $name. Install/repair .NET Framework 4.8." }
    $wpfReferences += "/reference:$reference"
}
$output = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Force $output | Out-Null
$arguments = @('/nologo', '/target:library', '/platform:x64', '/utf8output', '/codepage:65001', "/out:$output\ChatAI.AutoCAD2023.dll",
    '/reference:System.dll', '/reference:System.Core.dll', '/reference:System.Drawing.dll',
    '/reference:System.Windows.Forms.dll', '/reference:System.Net.Http.dll', '/reference:System.Web.Extensions.dll', '/reference:System.Security.dll')
$arguments += $wpfReferences
foreach ($ref in $refs) { $arguments += "/reference:$AutoCADPath\$ref" }
$arguments += (@('ChatClient.cs', 'CadTools.cs', 'ChatPalette.cs', 'CdmBridge.cs', 'SessionStore.cs') | ForEach-Object { Join-Path $PSScriptRoot $_ })
& $compiler @arguments
if ($LASTEXITCODE -ne 0) { throw 'Compilation failed; plugin was not installed.' }
$bundle = Join-Path $env:APPDATA 'Autodesk\ApplicationPlugins\ChatAI2023.bundle'
if (Test-Path $bundle) {
    $backup = Join-Path $env:LOCALAPPDATA ('ChatAI\PluginBackups\ChatAI2023-' + [guid]::NewGuid().ToString('N') + '.bundle')
    New-Item -ItemType Directory -Force (Split-Path $backup) | Out-Null
    Move-Item $bundle $backup
    Write-Host "Previous plugin preserved at $backup"
}
New-Item -ItemType Directory (Join-Path $bundle 'Contents') -Force | Out-Null
Copy-Item "$output\ChatAI.AutoCAD2023.dll" (Join-Path $bundle 'Contents')
Copy-Item (Join-Path $PSScriptRoot 'PackageContents.xml') $bundle
Write-Host "Installed $bundle. Restart AutoCAD 2023 and run CHATAI."

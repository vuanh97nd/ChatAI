; Full runtime installer. Build on Windows using Build-Setup.bat.
#define AppName "Chat AI"
#define AppVersion "2.6.6"
#define SourceRoot SourcePath
#if !FileExists(SourceRoot + "\runtime\python\chat-ai-runtime.json")
  #error Run Build-Setup.bat first to build the bundled Python runtime.
#endif
#if !FileExists(SourceRoot + "\installer-assets\chat_ai.ico")
  #error Missing robot icon. Run Build-Setup.bat.
#endif
#if !FileExists(SourceRoot + "\assistant\media_basic.py")
  #error Missing assistant\media_basic.py; the image/video tools will not work in the installed application.
#endif
[Setup]
AppId={{B4EE6C12-BA44-4F5D-9D18-570316F70791}
AppName={#AppName}
AppVersion={#AppVersion}
; Bundled runtime includes Pillow, imageio, imageio-ffmpeg and OpenCV.
AppPublisher=Chat AI
AppPublisherURL=https://github.com/vuanh97nd/ChatAI
AppSupportURL=https://github.com/vuanh97nd/ChatAI/issues
AppUpdatesURL=https://github.com/vuanh97nd/ChatAI/releases
VersionInfoVersion=2.6.6.0
VersionInfoDescription=Chat AI desktop installer with bundled Python and image/video processing libraries
DefaultDirName={localappdata}\Programs\Chat-AI
DefaultGroupName=Chat AI
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#SourceRoot}\dist
OutputBaseFilename=Chat-AI-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
DiskSpanning=no
SetupLogging=yes
WizardStyle=modern
SetupIconFile={#SourceRoot}\installer-assets\chat_ai.ico
WizardImageFile={#SourceRoot}\installer-assets\wizard.bmp
WizardSmallImageFile={#SourceRoot}\installer-assets\wizard-small.bmp
WizardImageStretch=yes
UninstallDisplayName=Chat AI
UninstallDisplayIcon={app}\chat_ai.ico
CloseApplications=yes
CloseApplicationsFilter=*.exe,*.dll,*.pyd,*.py
RestartApplications=no
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
[Files]
Source: "{#SourceRoot}\ChatAI.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\app.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\desktop_ui.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\desktop_launcher.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\Launch-ChatAI.vbs"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\run.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\assistant\*.py"; DestDir: "{app}\assistant"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceRoot}\Dockerfile.python-tools"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\requirements*.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\logo_chat_ai.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\installer-assets\chat_ai.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\runtime\python\*"; DestDir: "{app}\runtime\python"; Excludes: "__pycache__\*,*.pyc"; Flags: ignoreversion recursesubdirs createallsubdirs
; Recursively packages the full Python runtime, including bundled Pillow/imageio/ffmpeg/OpenCV wheels.
Source: "{#SourceRoot}\config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#SourceRoot}\glossary.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#SourceRoot}\experts.yaml"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#SourceRoot}\README.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#SourceRoot}\WINDOWS_BUILD.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\fix_ollama_gpu.bat"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#SourceRoot}\fix_ollama_gpu.ps1"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
[Dirs]
Name: "{app}\data"; Flags: uninsneveruninstall
Name: "{app}\workspace"; Flags: uninsneveruninstall
[Icons]
Name: "{group}\Chat AI"; Filename: "{app}\ChatAI.exe"; WorkingDir: "{app}"; IconFilename: "{app}\chat_ai.ico"
Name: "{userdesktop}\Chat AI"; Filename: "{app}\ChatAI.exe"; WorkingDir: "{app}"; IconFilename: "{app}\chat_ai.ico"; Tasks: desktopicon
Name: "{group}\Uninstall Chat AI"; Filename: "{uninstallexe}"; IconFilename: "{app}\chat_ai.ico"
[Run]
Filename: "{app}\ChatAI.exe"; WorkingDir: "{app}"; Description: "Open Chat AI"; Flags: postinstall skipifsilent nowait
; No recursive UninstallDelete of data, workspace, user memory or Ollama models.

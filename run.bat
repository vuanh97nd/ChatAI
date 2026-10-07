@echo off
setlocal
cd /d "%~dp0"

rem Use the packaged desktop launcher when it exists.
if exist "%~dp0ChatAI.exe" (
  start "" /D "%~dp0" "%~dp0ChatAI.exe"
  exit /b 0
)

rem Source mode uses the bundled runtime/.venv or a Python found directly by
rem Launch-ChatAI.vbs; it deliberately does not invoke py.exe/Python Launcher.
if not exist "%~dp0Launch-ChatAI.vbs" (
  echo Missing Launch-ChatAI.vbs. Please sync the full Chat-AI folder.
  pause
  exit /b 1
)
start "" "%SystemRoot%\System32\wscript.exe" "%~dp0Launch-ChatAI.vbs"
exit /b 0

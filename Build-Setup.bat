@echo off
setlocal
chcp 65001 >nul
title Build Chat AI - Bundled Python
pushd "%~dp0"
if errorlevel 1 exit /b 1
if not exist "build-logs" mkdir "build-logs"
set "PYTHONHOME="
set "PYTHONPATH="
set "PYTHONUTF8=1"
set "CHAT_ISCC="
for %%V in (7 6) do (
  call :try_inno "%LOCALAPPDATA%\Programs\Inno Setup %%V\ISCC.exe"
  call :try_inno "%ProgramFiles(x86)%\Inno Setup %%V\ISCC.exe"
  call :try_inno "%ProgramFiles%\Inno Setup %%V\ISCC.exe"
)
for /f "delims=" %%P in ('where.exe ISCC.exe 2^>nul') do call :try_inno "%%P"
if not defined CHAT_ISCC goto missing_inno
set "CHAT_PY="
call :try_python "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
call :try_python "%ProgramFiles%\Python312\python.exe"
call :try_python "%ProgramFiles(x86)%\Python312\python.exe"
for /f "delims=" %%P in ('where.exe python.exe 2^>nul') do call :try_python "%%P"
if not defined CHAT_PY goto missing_python
echo Python: "%CHAT_PY%"
echo Inno Setup: "%CHAT_ISCC%"
echo [1/2] Bundling Python 3.12, PDF/Office and basic image/video libraries, icon and wizard images...
echo This downloads packages on the BUILD machine only. See build-logs\runtime.log.
"%CHAT_PY%" -X utf8 "build_runtime.py" >"build-logs\runtime.log" 2>&1
if errorlevel 1 goto runtime_failed
echo [2/2] Compiling Inno Setup...
"%CHAT_ISCC%" "Chat-AI-Setup.iss" >"build-logs\setup.log" 2>&1
if errorlevel 1 goto setup_failed
if not exist "dist\Chat-AI-Setup-2.6.5.exe" goto setup_failed
echo Build successful: dist\Chat-AI-Setup-2.6.5.exe
start "" explorer.exe /select,"%CD%\dist\Chat-AI-Setup-2.6.5.exe"
popd
pause
exit /b 0
:missing_inno
echo Install Inno Setup 6.3 or 7 on the BUILD machine: https://jrsoftware.org/isdl.php
goto failed
:missing_python
echo Install full Python 3.12.10 or newer in the 3.12 branch, x64, on the BUILD machine.
echo End users do not need Python installed separately.
goto failed
:runtime_failed
type "build-logs\runtime.log"
goto failed
:setup_failed
type "build-logs\setup.log"
:failed
popd
pause
exit /b 1

:try_inno
if defined CHAT_ISCC exit /b 0
if exist "%~1" set "CHAT_ISCC=%~1"
exit /b 0
:try_python
if defined CHAT_PY exit /b 0
if not exist "%~1" exit /b 0
echo(%~1| "%SystemRoot%\System32\findstr.exe" /i /l /c:"\WindowsApps\" >nul
if not errorlevel 1 exit /b 0
"%~1" -X utf8 -c "import sys,struct; sys.exit(0 if sys.version_info[:2]==(3,12) and sys.version_info[:3]>=(3,12,10) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if errorlevel 1 exit /b 0
set "CHAT_PY=%~1"
exit /b 0


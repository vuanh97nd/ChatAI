@echo off
setlocal
chcp 65001 >nul
pushd "%~dp0"
if errorlevel 1 exit /b 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0fix_ollama_gpu.ps1"
if errorlevel 1 goto failed
call "%~dp0run.bat"
popd
exit /b
:failed
echo Chua sua/khoi dong duoc Ollama. Xem thong bao ben tren.
pause
popd
exit /b 1

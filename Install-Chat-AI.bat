@echo off
setlocal
chcp 65001 >nul
call "%~dp0run.bat" --install-only
exit /b %errorlevel%

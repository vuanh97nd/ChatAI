@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONHOME="
set "PYTHONPATH="
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "PY="

rem An existing venv executable may point to a deleted base Python.
call :try_python "%~dp0runtime\python\python.exe"
call :try_python "%~dp0.venv\Scripts\python.exe"
for %%V in (314 313 312 311) do call :try_python "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
for %%V in (314 313 312 311) do call :try_python "%ProgramFiles%\Python%%V\python.exe"
for %%V in (314 313 312 311) do call :try_python "%ProgramFiles(x86)%\Python%%V\python.exe"
for /f "delims=" %%P in ('where.exe python.exe 2^>nul') do call :try_python "%%P"
if not defined PY (
  echo LOI: Khong tim thay Python 3.11 tro len chay duoc.
  echo .venv co the dang tro toi Python da bi xoa. Can cai Python hoac sua lai .venv.
  pause
  exit /b 1
)
echo Python: "%PY%"
if not exist "evaluation\run_baseline.py" (
  echo LOI: Thieu evaluation\run_baseline.py. Hay doi dong bo du thu muc Chat-AI.
  pause
  exit /b 1
)
"%PY%" -c "import ollama; from assistant.agent import Agent; from assistant.config import load_config; from assistant.storage import Store"
if errorlevel 1 (
  echo LOI: Python da chay duoc nhung thieu thu vien hoac ma nguon Chat-AI.
  echo Cai thu vien bang lenh sau, roi chay lai:
  echo "%PY%" -m pip install -r requirements.txt
  pause
  exit /b 1
)
if not exist "data" mkdir "data"
if not exist "data" (
  echo LOI: Khong tao duoc thu muc data.
  pause
  exit /b 1
)
echo Dang danh gia Chat AI tren 24 cau hoi. Vui long doi, co the mat 10-20 phut...
echo Hay mo Ollama truoc khi chay.
echo.
"%PY%" evaluation\run_baseline.py --label after > "data\danh-gia-ket-qua.txt" 2>&1
set "RESULT=%ERRORLEVEL%"
type "data\danh-gia-ket-qua.txt"
echo.
if not "%RESULT%"=="0" (
  echo LOI: Danh gia that bai. Xem chi tiet tai data\danh-gia-ket-qua.txt.
  pause
  exit /b %RESULT%
)
echo Xong. Ket qua da luu tai data\danh-gia-ket-qua.txt.
pause
exit /b 0

:try_python
if defined PY exit /b 0
if not exist "%~1" exit /b 0
rem Skip Windows Store aliases, which can open the Store instead of Python.
echo(%~1| "%SystemRoot%\System32\findstr.exe" /i /l /c:"\WindowsApps\" >nul
if not errorlevel 1 exit /b 0
"%~1" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 exit /b 0
set "PY=%~1"
exit /b 0

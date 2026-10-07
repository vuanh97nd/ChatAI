@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=runtime\python\python.exe
if not exist "%PY%" set PY=.venv\Scripts\python.exe
if not exist "%PY%" (
  echo Khong tim thay Python cua Chat AI. Hay chay run.bat mot lan truoc.
  pause
  exit /b 1
)
echo Danh gia Chat AI voi model Qwen3 8B tren 24 cau hoi. Co the mat 15-30 phut...
echo Can mo Ollama va da tai qwen3:8b trong Chat AI - Module / Tai xuong.
echo.
"%PY%" evaluation\run_baseline.py --label qwen3 --model qwen3:8b > data\danh-gia-qwen3.txt 2>&1
type data\danh-gia-qwen3.txt
echo.
echo Xong. Hay gui file data\danh-gia-qwen3.txt va file data\baseline-qwen3-*.json cho Claude.
pause

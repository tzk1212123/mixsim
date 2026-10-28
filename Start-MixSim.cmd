@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please install first. See README.md for setup instructions.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:8765 in your browser.
echo Keep this terminal open. Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m mixsim serve
pause

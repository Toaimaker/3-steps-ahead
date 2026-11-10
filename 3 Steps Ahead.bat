@echo off
rem 3 Steps Ahead: starts the app (run Install.bat once before).
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Run Install.bat first.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -I -X utf8 "Companion\App\avvio_pubblico.py"

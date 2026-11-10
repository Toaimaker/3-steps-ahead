@echo off
rem 3 Steps Ahead: starts the app. Installed with the setup: its private Python (runtime). From the zip: run Install.bat once before.
cd /d "%~dp0"
if exist "runtime\pythonw.exe" (
  start "" "runtime\pythonw.exe" -I -X utf8 "Companion\App\avvio_pubblico.py"
  exit /b 0
)
if not exist ".venv\Scripts\pythonw.exe" (
  echo Run Install.bat first, or install with 3 Steps Ahead-Setup.exe.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -I -X utf8 "Companion\App\avvio_pubblico.py"

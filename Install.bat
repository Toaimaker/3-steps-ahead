@echo off
rem 3 Steps Ahead: prepares a private Python environment in this folder (run once, and again after an update).
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3.11) || (set PY=python)
%PY% --version >nul 2>nul || (
  echo Python 3.11 was not found. Install it from https://www.python.org/downloads/ with "Add python.exe to PATH" ticked, then run this again.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv || (echo Could not create the environment. & pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt || (echo Could not install the packages. Check your connection and run this again. & pause & exit /b 1)
echo.
echo Done. Start the app with 3 Steps Ahead.bat
pause

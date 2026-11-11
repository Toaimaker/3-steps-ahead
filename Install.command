#!/bin/bash
# 3 Steps Ahead for Mac: prepares a private Python environment in this folder (run once, and again after an update).
# Needs Python 3.11 or newer with Tk, from https://www.python.org/downloads/macos/ (the python.org installer includes Tk).
cd "$(dirname "$0")" || exit 1
PY=""
for p in python3.13 python3.12 python3.11 python3; do
  if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import sys, tkinter; tkinter.Tcl(); sys.exit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
    PY="$p"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.11 or newer with Tk was not found."
  echo "Install it from https://www.python.org/downloads/macos/ and run this again."
  read -r -p "Press Enter to close."
  exit 1
fi
echo "Using $($PY --version) at $(command -v $PY)"
[ -x ".venv/bin/python" ] || "$PY" -m venv .venv || { echo "Could not create the environment."; read -r -p "Press Enter to close."; exit 1; }
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -r requirements.txt || { echo "Could not install the packages. Check your connection and run this again."; read -r -p "Press Enter to close."; exit 1; }
chmod +x "3 Steps Ahead.command" 2>/dev/null
echo
echo "Done. Start the app with 3 Steps Ahead.command"
read -r -p "Press Enter to close."

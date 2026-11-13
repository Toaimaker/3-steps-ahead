#!/bin/bash
# 3 Steps Ahead for Mac: starts the app. Run Install.command once before.
cd "$(dirname "$0")" || exit 1
if [ ! -x ".venv/bin/python" ]; then
  echo "Run Install.command first."
  read -r -p "Press Enter to close."
  exit 1
fi
# the app runs on its own: this Terminal window can be closed
nohup .venv/bin/python -I -X utf8 "Companion/App/avvio_pubblico.py" >/dev/null 2>&1 &
disown
echo "3 Steps Ahead started. You can close this window."
exit 0

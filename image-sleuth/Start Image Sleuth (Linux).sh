#!/bin/bash
# Double-click to start Image Sleuth. The first run sets it up (about a minute).
cd "$(dirname "$0")" || exit 1

finish() { echo; read -r -p "Press Enter to close this window." _; exit "$1"; }

PY="$(command -v python3)"
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
  echo "Python 3.10 or newer is needed."
  echo "Download it from https://www.python.org/downloads/ , install it, then double-click this file again."
  finish 1
fi

if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c 'import requests, bs4, PIL, numpy' 2>/dev/null; then
  echo "First run: setting up Image Sleuth (about a minute)..."
  rm -rf .venv
  if ! "$PY" -m venv .venv || ! .venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt; then
    rm -rf .venv
    echo
    echo "Setup failed (see the message above). Check your internet connection and try again."
    finish 1
  fi
fi

echo "Starting Image Sleuth... your browser will open. Keep this window open while you use it."
.venv/bin/python -m imgsleuth --web
finish $?

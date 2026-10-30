#!/bin/bash
# Double-click to start. First run installs it (needs Python 3 from python.org).
cd "$(dirname "$0")"
python3 -m pip install --quiet --user . || { echo "Install Python 3 from https://python.org first"; read -r; exit 1; }
python3 -m imgsleuth --web

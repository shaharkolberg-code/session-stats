#!/bin/bash
cd "$(dirname "$0")"
python3 -m pip install --quiet --user . || python3 -m pip install --quiet --user --break-system-packages .
python3 -m imgsleuth --web

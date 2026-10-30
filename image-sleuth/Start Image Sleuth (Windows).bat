@echo off
REM Double-click to start. First run installs it (needs Python 3 from python.org).
cd /d "%~dp0"
py -m pip install --quiet --user . || (echo Install Python 3 from https://python.org first & pause & exit /b 1)
py -m imgsleuth --web
pause

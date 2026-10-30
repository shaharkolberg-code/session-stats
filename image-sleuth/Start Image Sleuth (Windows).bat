@echo off
REM Double-click to start Image Sleuth. The first run sets it up (about a minute).
title Image Sleuth
cd /d "%~dp0"

set "PY="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python 3.10 or newer is needed.
  echo Download it from https://www.python.org/downloads/ and tick "Add python.exe to PATH" when installing.
  echo Then double-click this file again.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -c "import requests, bs4, PIL, numpy" >nul 2>nul
if errorlevel 1 (
  echo First run: setting up Image Sleuth ^(about a minute^)...
  if exist .venv rmdir /s /q .venv
  %PY% -m venv .venv || goto fail
  ".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt || goto fail
)

echo Starting Image Sleuth... your browser will open. Keep this window open while you use it.
".venv\Scripts\python.exe" -m imgsleuth --web
pause
exit /b 0

:fail
if exist .venv rmdir /s /q .venv
echo.
echo Setup failed (see the message above). Check your internet connection and try again.
pause
exit /b 1

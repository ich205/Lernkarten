@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

if not exist .venv (
  py -3 -m venv .venv
)
call .venv\Scripts\activate.bat

python -m pip install --upgrade pip >NUL 2>&1
if exist installer\requirements.txt (
  pip install -r installer\requirements.txt
)

rem .env laden (einfacher Parser: KEY=VALUE, ohne Quotes)
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    if not "%%a"=="" set "%%a=%%b"
  )
)

python -m app.main


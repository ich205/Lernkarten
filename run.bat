@echo off
setlocal
REM Aktiviert das venv und startet die App
IF NOT EXIST .venv\Scripts\activate.bat (
  echo Virtuelle Umgebung nicht gefunden. Bitte zuerst: python install.py
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m app.main

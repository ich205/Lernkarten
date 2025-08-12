@echo off
setlocal
REM Setup & Start (Windows)

REM Python-Launcher wählen
set "_PY=python"
where %_PY% >nul 2>nul || set "_PY=py -3"

IF NOT EXIST .venv\Scripts\activate.bat (
  echo [Setup] Virtuelle Umgebung nicht gefunden – fuehre Installation aus ...
  %_PY% install.py
  if errorlevel 1 (
    echo [Fehler] Installation fehlgeschlagen.
    pause
    exit /b 1
  )
)

call .venv\Scripts\activate.bat || (
  echo [Fehler] Konnte venv nicht aktivieren.
  pause
  exit /b 1
)

python -m app.main

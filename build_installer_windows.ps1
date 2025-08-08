# Erzeugt ein Windows-Standalone mit PyInstaller
# Voraussetzungen: .\install.py ausgeführt
$ErrorActionPreference = "Stop"

if (!(Test-Path ".venv\Scripts\activate.ps1")) {
  Write-Error "Venv nicht gefunden. Bitte zuerst: python install.py"
}

.\.venv\Scripts\activate.ps1
python -m pip install pyinstaller

pyinstaller --noconfirm ^
  --onefile ^
  --name GSA-Flashcards ^
  --add-data "config.toml;." ^
  --add-data "assets;assets" ^
  app/main.py

Write-Host "Fertig. EXE liegt in dist\GSA-Flashcards.exe"

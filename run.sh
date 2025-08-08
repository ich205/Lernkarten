#!/usr/bin/env bash
set -euo pipefail
if [ ! -d ".venv" ]; then
  echo "Virtuelle Umgebung nicht gefunden. Bitte zuerst: python install.py"
  exit 1
fi
source .venv/bin/activate
python -m app.main

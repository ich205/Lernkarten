#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"

# 1) venv anlegen/aktivieren
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 2) pip aktualisieren & Requirements installieren
python -m pip install --upgrade pip >/dev/null
if [ -f "installer/requirements.txt" ]; then
  pip install -r installer/requirements.txt
fi

# 3) .env laden (falls vorhanden)
if [ -f ".env" ]; then
  set -a; . ./.env; set +a
fi

# 4) App starten
exec python -m app.main


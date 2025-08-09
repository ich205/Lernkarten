"""Export-Helfer zum Schreiben der generierten Karten in eine Excel-Datei.

Wird von `pipeline.export_excel` sowie der GUI verwendet. Das Format der
eingehenden ``rows`` entspricht der Struktur, die `pipeline.generate_cards`
liefert.
"""

from __future__ import annotations
from typing import List, Dict, Any
from pathlib import Path

def to_excel(rows: List[Dict[str, Any]], out_path: str) -> None:
    """Schreibt eine Liste von Karten in ``out_path``.

    ``rows`` ist eine Liste von Dictionaries wie sie `pipeline.generate_cards`
    erzeugt. Die Funktion wandelt sie in ein pandas-DataFrame um und speichert
    dieses als ``.xlsx``.
    """

    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "Das Paket 'pandas' wird zum Export in Excel-Dateien benötigt."
        ) from exc

    df = pd.DataFrame([
        {
            "Original": r.get("original",""),
            "Fragen": "\n\n".join(r.get("fragen",[])),
            "Antworten": "\n\n".join(r.get("antworten",[])),
            "Labels": ", ".join(r.get("labels",[])),
            "Hinweise": r.get("hinweise",""),
        } for r in rows
    ])
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_excel(path, index=False)
    except OSError as exc:
        raise RuntimeError(f"Could not write Excel file {path}: {exc}") from exc

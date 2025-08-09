"""Export-Helfer zum Schreiben der generierten Karten in eine Excel-Datei.

Wird von `pipeline.export_excel` sowie der GUI verwendet. Das Format der
eingehenden ``rows`` entspricht der Struktur, die `pipeline.generate_cards`
liefert.
"""

from __future__ import annotations
from typing import List
from pathlib import Path
try:
    import pandas as pd  # optional
except Exception:  # ImportError + env specifics
    pd = None

from .pipeline_models import CardRow

def to_excel(rows: List[CardRow], out_path: str) -> None:
    """Schreibt eine Liste von Karten in ``out_path``."""

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        # leere Datei anlegen, aber nicht craschen
        path.touch()
        return

    data = [
        {
            "Original": r.original,
            "Frage": q,
            "Antwort": a,
            "Labels": ", ".join(r.labels),
            "Quelle": r.source,
        }
        for r in rows
        for q, a in zip(r.fragen, r.antworten)
    ]

    if pd is not None:
        try:
            pd.DataFrame(data).to_excel(path, index=False)
        except OSError as exc:
            raise RuntimeError(f"Could not write Excel file {path}: {exc}") from exc
    else:
        # Fallback: CSV erzeugen, gleiche Basename
        import csv
        csv_path = path.with_suffix(".csv")
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(
                f, fieldnames=["Original", "Frage", "Antwort", "Labels", "Quelle"]
            )
            w.writeheader()
            w.writerows(data)

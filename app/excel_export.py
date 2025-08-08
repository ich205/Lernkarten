# app/excel_export.py
from __future__ import annotations
import pandas as pd
from typing import List, Dict, Any

def to_excel(rows: List[Dict[str, Any]], out_path: str) -> None:
    """
    rows: [{"original": str, "fragen": List[str], "antworten": List[str], "labels": List[str], "hinweise": str}, ...]
    """
    df = pd.DataFrame([
        {
            "Original": r.get("original",""),
            "Fragen": "\n\n".join(r.get("fragen",[])),
            "Antworten": "\n\n".join(r.get("antworten",[])),
            "Labels": ", ".join(r.get("labels",[])),
            "Hinweise": r.get("hinweise",""),
        } for r in rows
    ])
    df.to_excel(out_path, index=False)

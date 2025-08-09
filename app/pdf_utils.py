"""Low-level PDF-Helfer.

Dieses Modul wird von `pdf_ingest` und der GUI genutzt, um Text aus PDF-Dateien
oder alternativen Quellen zu extrahieren und grob zu bereinigen.
"""

from pypdf import PdfReader
from pypdf.errors import PdfReadError
import re, os, pathlib

from .logging_utils import get_logger

logger = get_logger(__name__)

def extract_text_from_pdf(path):
    reader = PdfReader(path)
    texts = []
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except (PdfReadError, KeyError) as err:
            logger.warning("Text auf Seite %s konnte nicht extrahiert werden: %s", i, err)
            t = ""
        # rudimentäre Bereinigung
        t = _cleanup_page_text(t)
        texts.append(t)
    return "\n\n".join(texts)

def _cleanup_page_text(t: str) -> str:
    # Silbentrennungen auflösen: 'Beispiel-\nhaft' -> 'Beispielhaft'
    t = re.sub(r"(\w+)-\n(\w+)", r"\1\2", t)
    # Zeilenumbrüche normalisieren
    t = t.replace("\r", "")
    # Seitenzahlen/isolierte Zahlenzeilen entfernen
    lines = []
    for line in t.split("\n"):
        if re.fullmatch(r"\s*\d+\s*", line):
            continue
        # Kopf-/Fußzeilen-Heuristik
        if re.search(r"IU Internationale Hochschule|Inhaltsverzeichnis|Abbildungsverzeichnis", line):
            continue
        lines.append(line.strip())
    t = "\n".join(lines)
    # Mehrfache Leerzeichen
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t

def try_extract_text(path):
    path = str(path)
    if path.lower().endswith(".pdf"):
        return extract_text_from_pdf(path)
    else:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

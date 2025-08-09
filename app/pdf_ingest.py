"""Extraktion und grobe Segmentierung von PDF-Dateien.

`extract_text_from_pdf` versucht zunächst ``pdfplumber`` zu verwenden und fällt
bei fehlender Installation auf ``pypdf`` zurück. Die Funktion `segment_text`
nimmt die Rohtexte entgegen und zerlegt sie in Abschnitte, bevor das feinere
Chunking (`app.chunking`) angewendet wird.
"""

from __future__ import annotations
import re
from typing import List, Tuple, Iterable, Optional
import io

# Wir versuchen zuerst pdfplumber; faellt auf pypdf zurueck.
def extract_text_from_pdf(path: str) -> str:
    try:
        import pdfplumber
        full = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ""
                full.append(txt)
        return "\n\n".join(full)
    except Exception:
        # Fallback: pypdf
        from pypdf import PdfReader
        full = []
        reader = PdfReader(path)
        for page in reader.pages:
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            full.append(txt)
        return "\n\n".join(full)

def normalize_whitespace(s: str) -> str:
    s = s.replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

# Grobe Segmentierung: nach Ueberschriften, Leerzeilen, Absatzenden.
HEADING_RE = re.compile(r"^\s*(inhalt|einleitung|vorwort|ueberblick|herzlich willkommen|literaturverzeichnis|anhang|uebergeordnete lernziele|lernziele)\b", re.I)


def segment_text(
    text: str,
    min_len: int = 300,
    max_len: int = 1200,
    keep_headings: bool = True,
) -> List[str]:
    """Segmentieren von Rohtext in Abschnitte.

    Absätze werden gesammelt, bis ``min_len`` erreicht ist, ``max_len`` aber
    nicht überschritten wird. Absätze, die auf ``HEADING_RE`` matchen, werden
    als eigene Segmente behandelt oder – falls ``keep_headings`` ``False`` ist –
    verworfen.
    """
    text = normalize_whitespace(text)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    segments: List[str] = []
    buf: List[str] = []
    cur_len = 0

    def flush():
        nonlocal buf, cur_len, segments
        if buf:
            chunk = "\n\n".join(buf).strip()
            if chunk:
                segments.append(chunk)
        buf, cur_len = [], 0

    for p in paragraphs:
        if HEADING_RE.match(p):
            flush()
            if keep_headings:
                segments.append(p)
            continue

        plen = len(p)
        if cur_len + plen > max_len and cur_len >= min_len:
            flush()
        buf.append(p)
        cur_len += plen
        if cur_len >= min_len:
            flush()

    flush()
    return segments

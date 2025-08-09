"""Utility-Funktionen zur Textsegmentierung.

`split_into_chunks` zerlegt längere Texte in überlappende Abschnitte, die als
"Chunks" an die OpenAI-API gesendet werden. Die Standardwerte orientieren sich
an den Einstellungen in `config.toml` (`[chunking]`). Änderungen dort wirken
sich direkt auf die Parameter `target_tokens`, `overlap_tokens` und
`max_chars_per_chunk` aus.

Dieses Modul wird hauptsächlich von `pipeline.load_and_segment` verwendet.
"""

from .models import count_tokens_rough
import re, math

def split_into_chunks(text: str, target_tokens: int = 600, overlap_tokens: int = 60, max_chars_per_chunk: int = 4000):
    # Vorab: harte Abschnittstrennung an Überschriften (heuristisch)
    # Heuristik: Zeile in GROSS, beginnt mit Ziffern '1.' '2.1' etc., endet mit ':'
    blocks = []
    curr = []
    for line in text.splitlines():
        if is_heading_like(line):
            if curr:
                blocks.append("\n".join(curr).strip())
                curr = []
            blocks.append(line.strip())  # Headline als eigener Block
        else:
            curr.append(line)
    if curr:
        blocks.append("\n".join(curr).strip())

    # Feingranular: Blöcke zu Token-Zielen aggregieren
    chunks = []
    buf = ""
    last_tokens = 0
    for b in blocks:
        if not b.strip():
            continue
        t = count_tokens_rough(b)
        if t > target_tokens*1.3 or len(b) > max_chars_per_chunk:
            # Grob teilen bei Doppelleerzeilen/Satzende
            parts = smart_split(b, target_tokens, max_chars_per_chunk)
            for p in parts: 
                chunks.append(p)
            last_tokens = count_tokens_rough(parts[-1]) if parts else 0
            buf = ""
            continue

        if count_tokens_rough(buf) + t <= target_tokens:
            buf = (buf + "\n\n" + b).strip() if buf else b
            last_tokens = count_tokens_rough(buf)
        else:
            # Buffer schließen
            if buf:
                chunks.append(buf)
            # Overlap (heuristisch: n letzte Sätze)
            overlap = take_last_sentences(buf, approx_tokens=overlap_tokens) if buf else ""
            buf = (overlap + "\n\n" + b).strip() if overlap else b
            last_tokens = count_tokens_rough(buf)

    if buf:
        chunks.append(buf)

    return [c for c in chunks if c.strip()]

def is_heading_like(line: str) -> bool:
    l = line.strip()
    if not l: return False
    if len(l) < 80 and (l.isupper() or re.match(r"^\d+(\.\d+)*\s", l) or l.endswith(":")):
        # keine Satzendepunkte, wenig Kommas → Überschrift-Indiz
        if re.search(r"[\.!?]{2,}", l): 
            return False
        return True
    return False

def smart_split(block: str, target_tokens: int, max_chars: int):
    # Split an Absatz/Satzenden
    paras = re.split(r"\n{2,}", block)
    out, buf = [], ""
    for p in paras:
        if len(p) > max_chars:
            # brutaler Split by Sätze
            out.extend(split_by_sentences(p, target_tokens, max_chars))
            continue
        if count_tokens_rough(buf + "\n\n" + p) <= target_tokens:
            buf = (buf + "\n\n" + p).strip() if buf else p
        else:
            if buf: out.append(buf)
            buf = p
    if buf: out.append(buf)
    return out

def split_by_sentences(text: str, target_tokens: int, max_chars: int):
    sents = re.split(r"(?<=[\.\?!])\s+", text)
    out, buf = [], ""
    for s in sents:
        if len(s) > max_chars:
            # harter Cut
            mid = len(s)//2
            parts = [s[:mid], s[mid:]]
            for p in parts:
                if buf:
                    if count_tokens_rough(buf + " " + p) <= target_tokens:
                        buf = (buf + " " + p).strip()
                    else:
                        out.append(buf); buf = p
                else:
                    buf = p
            continue
        if buf:
            if count_tokens_rough(buf + " " + s) <= target_tokens:
                buf = (buf + " " + s).strip()
            else:
                out.append(buf); buf = s
        else:
            buf = s
    if buf: out.append(buf)
    return out

def take_last_sentences(text: str, approx_tokens: int = 60):
    if not text: return ""
    sents = re.split(r"(?<=[\.\?!])\s+", text.strip())
    acc, out = 0, []
    for s in reversed(sents):
        t = count_tokens_rough(s)
        if acc + t > approx_tokens: break
        out.append(s)
        acc += t
    return " ".join(reversed(out))

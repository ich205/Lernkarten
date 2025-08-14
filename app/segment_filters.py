from __future__ import annotations

from typing import Sequence

OUTLINE_PREFIXES: Sequence[str] = (
    "inhalt",
    "inhaltsverzeichnis",
    "literaturverzeichnis",
    "glossar",
)


def is_outline_segment(text: str) -> bool:
    """Return True if *text* starts with a typical outline heading.

    Leading whitespace is ignored and comparison is case-insensitive.
    """
    return text.strip().lower().startswith(OUTLINE_PREFIXES)


def looks_like_outline_list(text: str, label: str) -> bool:
    """Heuristically detect list-like table of contents segments.

    The OpenAI classifier might label such a segment as ``Aufzaehlung``
    (bullet list). If the majority of lines are short ("chapter titles") and
    there are several of them, we consider it an outline and drop it regardless
    of the ``keep`` flag from the model.
    """
    if label != "Aufzaehlung":
        return False
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) <= 3:
        return False
    short = sum(1 for ln in lines if len(ln) < 50)
    return short / len(lines) > 0.8


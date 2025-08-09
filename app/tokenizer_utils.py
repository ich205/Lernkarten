"""Tokenisierungs-Helfer.

Stellt eine einfache Heuristik sowie eine optionale `tiktoken`-Integration zur
Verfügung. Wird von `pipeline` und anderen Modulen genutzt, um die Größe von
Textabschnitten abzuschätzen.
"""

from __future__ import annotations
from typing import Iterable, Optional

from .logging_utils import get_logger

logger = get_logger(__name__)

def approximate_token_count(text: str) -> int:
    """
    Fallback-Heuristik: durchschnittlich ~4 Zeichen pro Token (Deutsch liegt oft 3.7–4.5).
    """
    if not text:
        return 0
    chars = len(text)
    return max(1, int(round(chars / 4.0)))

class Tokenizer:
    """
    Kapselt optional tiktoken-Nutzung, faellt auf Heuristik zurueck.
    """
    def __init__(self, encoding_name: str = "o200k_base"):
        self._enc = None
        try:
            import tiktoken
            # o200k_base abwaerts-kompatibel; faellt auf cl100k_base zurueck
            try:
                self._enc = tiktoken.get_encoding(encoding_name)
            except Exception:
                try:
                    self._enc = tiktoken.get_encoding("cl100k_base")
                except Exception:
                    self._enc = None
        except ImportError:
            self._enc = None
            logger.warning("tiktoken nicht installiert; heuristische Tokenisierung wird verwendet")
        if self._enc is None:
            logger.warning("tiktoken konnte keine Encoding laden; heuristische Tokenisierung wird verwendet")

    def count(self, text: str) -> int:
        if self._enc is None:
            return approximate_token_count(text)
        try:
            return len(self._enc.encode(text or ""))
        except ValueError:
            logger.warning("Fehler bei der Tokenisierung, falle auf Heuristik zurueck")
            return approximate_token_count(text)

    def count_all(self, texts: Iterable[str]) -> int:
        return sum(self.count(t) for t in texts if t)

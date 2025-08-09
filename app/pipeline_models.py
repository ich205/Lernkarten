from dataclasses import dataclass
from typing import List


@dataclass
class Segment:
    text: str
    keep: bool = True


@dataclass
class QAItem:
    frage: str
    antwort: str
    labels: list[str] | None = None


@dataclass
class CardRow:
    original: str
    fragen: List[str]
    antworten: List[str]
    labels: List[str]
    source: str = ""

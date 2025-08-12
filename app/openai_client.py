"""Höhere Abstraktion der OpenAI-API.

`OpenAIClient` kapselt die eigentlichen API-Aufrufe und kümmert sich um
Initialisierung, Fehlerbehandlung und JSON-Modus. Die Klassen und Methoden
werden von `pipeline.LernkartenPipeline` genutzt und greifen auf Werte aus
``config.toml`` zurück (`DEFAULT_*`).
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
import json
import time

from .pipeline_models import QAItem

try:  # pragma: no cover - optional dependency
    from openai import OpenAIError
except ImportError:  # pragma: no cover
    OpenAIError = Exception  # type: ignore

from .config import (
    DEFAULT_CLASSIFY_MODEL,
    DEFAULT_QA_MODEL,
    DEFAULT_LANGUAGE,
    load_config,
)
from .logging_utils import get_logger

_cfg = load_config()
_REQ_TIMEOUT = int(_cfg["models"].get("request_timeout_sec", 60))
_MAX_RETRIES = int(_cfg["models"].get("max_retries", 5))
_BASE_BACKOFF = float(_cfg["models"].get("base_backoff_seconds", 1.0))


def _is_transient(e: Exception) -> bool:
    code = getattr(e, "status_code", None)
    return isinstance(e, OpenAIError) and code in (429, 500, 502, 503, 504)


def safe_request(call: Callable[..., Any], *args, **kwargs):
    """Wrap OpenAI client calls with timeout and exponential backoff."""

    kwargs.setdefault("timeout", _REQ_TIMEOUT)
    for attempt in range(_MAX_RETRIES):
        try:
            return call(*args, **kwargs)
        except Exception as e:  # pragma: no cover - network errors hard to test
            if _is_transient(e) and attempt < _MAX_RETRIES - 1:
                retry_after = getattr(e, "retry_after", None)
                sleep = float(retry_after or (_BASE_BACKOFF * (2**attempt)))
                time.sleep(min(sleep, 30.0))
                continue
            raise


logger = get_logger(__name__)

@dataclass
class OpenAISettings:
    api_key: str
    classify_model: str = DEFAULT_CLASSIFY_MODEL
    qa_model: str = DEFAULT_QA_MODEL
    temperature: float = 0.2

class OpenAIClient:
    def __init__(self, settings: OpenAISettings):
        self.settings = settings
        # verzögerte Initialisierung, falls Paket fehlt
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise RuntimeError(
                    "Das 'openai'-Paket ist nicht installiert. Bitte fuehre "
                    "'python install.py' aus (oder starte ueber 'run.bat')."
                ) from e
            self._client = OpenAI(api_key=self.settings.api_key)
        return self._client

    def classify_segment(self, text: str) -> Dict[str, Any]:
        """
        Ruft das Nano-Modell auf, um den Segmenttyp zu bestimmen.
        Rueckgabe-Format:
        {"label": "Definition|Fakt|Beispiel|Aufzaehlung|Ueberschrift/Vorwort", "keep": bool, "reason": str}
        """
        client = self._get_client()
        system = (
            "Du bist ein strenger Klassifizierer. "
            "Gib eine kompakte JSON-Antwort mit Schluesseln: label, keep, reason. "
            "Erlaubte label: Definition, Fakt, Beispiel, Aufzaehlung, Ueberschrift/Vorwort"
        )
        user = (
            "Klassifiziere den folgenden deutschen Textausschnitt nach seinem Hauptzweck. "
            "Falls es sich um Gliederung, Kapitelueberschrift, Vorwort, Inhaltsverzeichnis, Literaturverzeichnis "
            "oder aehnliches handelt, setze keep=false. Sonst keep=true.\n\n"
            f"---\n{text}\n---"
        )
        resp = safe_request(
            client.chat.completions.create,
            model=self.settings.classify_model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse classification response: %r", content)
            data = {"label": "Fakt", "keep": True, "reason": "fallback"}
        return data

    def gen_qa_for_chunk(self, text: str, n_questions: int, language: str = DEFAULT_LANGUAGE) -> List[QAItem]:
        """
        Erzeugt n_questions Lernkarten (Frage/Antwort) fuer den gegebenen Text.
        Rueckgabe: [QAItem(frage="...", antwort="..."), ...]
        """
        client = self._get_client()
        system = (
            f"Du erstellst pruefungsreife Lernkarten ({language}). "
            "Sehr praezise, faktenbasiert, konsistent mit dem Eingangstext. "
            "Beziehe dich NICHT auf Quellenangaben im Fließtext; extrahiere nur den Kerninhalt."
        )
        user = (
            f"Erzeuge {n_questions} Lernkarten (Frage/Antwort) zum folgenden Text. "
            "Gib eine JSON-Liste mit Objekten {frage, antwort} zurueck. "
            "Jede Frage sollte atomar sein (ein Fakt pro Frage). "
            "Antworten moeglichst kurz, klar und eindeutig.\n\n"
            f"=== TEXT BEGINN ===\n{text}\n=== TEXT ENDE ==="
        )
        resp = safe_request(
            client.chat.completions.create,
            model=self.settings.qa_model,
            temperature=self.settings.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "items" in data:
                items = data["items"]
            else:
                items = data
            out: List[QAItem] = []
            for it in items:
                q = (it.get("frage") or it.get("question") or "").strip()
                a = (it.get("antwort") or it.get("answer") or "").strip()
                if q and a:
                    out.append(QAItem(frage=q, antwort=a))
            return out
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("Failed to parse QA response: %r", content)
            return []

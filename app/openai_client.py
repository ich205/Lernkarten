"""Höhere Abstraktion der OpenAI-API.

`OpenAIClient` kapselt die eigentlichen API-Aufrufe und kümmert sich um
Initialisierung, Fehlerbehandlung und JSON-Modus. Die Klassen und Methoden
werden von `pipeline.LernkartenPipeline` genutzt und greifen auf Werte aus
``config.toml`` zurück (`DEFAULT_*`).
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import time
import json
import random

from openai import OpenAIError

from .config import DEFAULT_CLASSIFY_MODEL, DEFAULT_QA_MODEL, DEFAULT_LANGUAGE
from .logging_utils import get_logger

logger = get_logger(__name__)


def retry_request(func, *args, **kwargs):
    """Führt *func* mit Wiederholungen und Exponential-Backoff aus.

    Parameter:
        func: Aufzurufende Funktion
        *args: Positionsargumente für func
        **kwargs: Keyword-Argumente für func. Zusätzliche optionale
            Kontrollparameter:
            - n: maximale Anzahl Versuche (Standard: 3)
            - delay: Anfangspause zwischen den Versuchen in Sekunden
              (Standard: 1). Zwischen den Versuchen wird zusätzlich ein
              zufälliger Jitter von 0 bis 1 Sekunde addiert, um
              gleichzeitige Wiederholungen zu entzerren.
            - backoff: Faktor, mit dem die Pause nach jedem Fehlschlag
              multipliziert wird (Standard: 2)
    """

    max_attempts = kwargs.pop("n", 3)
    delay = kwargs.pop("delay", 1)
    backoff = kwargs.pop("backoff", 2)

    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except (OpenAIError, OSError, ValueError) as exc:
            if attempt == max_attempts:
                logger.warning(
                    "API request failed after %s attempts: %s", attempt, exc
                )
                raise RuntimeError(
                    f"Request failed after {max_attempts} attempts"
                ) from exc
            logger.warning(
                "API request failed (attempt %s/%s): %s – retrying in %ss",
                attempt,
                max_attempts,
                exc,
                delay,
            )
            time.sleep(delay + random.uniform(0, 1))
            delay *= backoff

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
                    "Das 'openai'-Paket ist nicht installiert. Bitte fuehre install.bat aus."
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
        resp = retry_request(
            client.chat.completions.create,
            model=self.settings.classify_model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        try:
            data = json.loads(resp.choices[0].message.content)
        except json.JSONDecodeError:
            data = {"label": "Fakt", "keep": True, "reason": "fallback"}
        return data

    def gen_qa_for_chunk(self, text: str, n_questions: int, language: str = DEFAULT_LANGUAGE) -> List[Dict[str, str]]:
        """
        Erzeugt n_questions Lernkarten (Frage/Antwort) fuer den gegebenen Text.
        Rueckgabe: [{"frage": "...", "antwort": "..."}, ...]
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
        resp = retry_request(
            client.chat.completions.create,
            model=self.settings.qa_model,
            temperature=self.settings.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        try:
            content = resp.choices[0].message.content
            data = json.loads(content)
            if isinstance(data, dict) and "items" in data:
                items = data["items"]
            else:
                items = data
            out = []
            for it in items:
                q = (it.get("frage") or it.get("question") or "").strip()
                a = (it.get("antwort") or it.get("answer") or "").strip()
                if q and a:
                    out.append({"frage": q, "antwort": a})
            return out
        except (json.JSONDecodeError, KeyError, TypeError):
            return []

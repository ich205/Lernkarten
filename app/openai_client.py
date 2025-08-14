"""Höhere Abstraktion der OpenAI-API. `OpenAIClient` kapselt die eigentlichen API-Aufrufe
und kümmert sich um Initialisierung, Fehlerbehandlung und JSON-Modus. Die Klassen und
Methoden werden von `pipeline.LernkartenPipeline` genutzt und greifen auf Werte aus
`config.toml` zurück (`DEFAULT_*`)."""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
import json
import time

from .pipeline_models import QAItem

try:  # pragma: no cover - optional dependency
    from openai import (
        OpenAIError,
        BadRequestError,
        APIConnectionError,
        APITimeoutError,
    )
except ImportError:  # pragma: no cover
    OpenAIError = Exception  # type: ignore
    BadRequestError = OpenAIError  # type: ignore

    class APIConnectionError(OpenAIError):  # type: ignore
        """Fallbackklasse bei fehlendem openai-Paket."""

        pass

    class APITimeoutError(OpenAIError):  # type: ignore
        """Fallbackklasse bei fehlendem openai-Paket."""

        pass

# optionale Low-Level-Transport-Errors
try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore
try:
    import httpcore  # type: ignore
except Exception:  # pragma: no cover
    httpcore = None  # type: ignore

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
    """Gibt True zurück, wenn sich ein erneuter Versuch lohnt (temporärer Fehler)."""

    # Netzwerk-/Timeoutfehler vom OpenAI-SDK sind transient
    if isinstance(e, (APIConnectionError, APITimeoutError)):
        return True

    code = getattr(e, "status_code", None)
    if isinstance(e, OpenAIError) and code == 429:
        msg = str(e)
        if "insufficient_quota" in msg or "exceeded your current quota" in msg:
            return False
        return True
    if isinstance(e, OpenAIError) and code in (500, 502, 503, 504):
        return True
    # Tieferliegende Transport-/Protokollfehler (Keep-Alive abgebrochen etc.)
    if httpx and isinstance(
        e,
        (
            httpx.TimeoutException,
            httpx.TransportError,
            getattr(httpx, "RemoteProtocolError", tuple()),
        ),
    ):
        return True
    if httpcore and isinstance(e, getattr(httpcore, "RemoteProtocolError", tuple())):
        return True
    return False


def safe_request(call: Callable[..., Any], *args, **kwargs):
    """Wrap OpenAI client calls with timeout and exponential backoff."""

    kwargs.setdefault("timeout", _REQ_TIMEOUT)
    for attempt in range(_MAX_RETRIES):
        try:
            return call(*args, **kwargs)
        except Exception as e:  # pragma: no cover - network errors hard to test
            # Bekannter, nicht-transienter Fehler: temperature wird vom Modell nicht unterstützt
            # (z. B. o1/o3/o4-mini → nur Standardwert 1 erlaubt).
            # -> verständliche Meldung erzeugen und ggf. einmal ohne temperature neu versuchen.
            try:
                is_bad_req = isinstance(e, BadRequestError)
            except Exception:
                is_bad_req = False
            msg = str(e)
            if is_bad_req and ("unsupported_value" in msg and "temperature" in msg):
                # Einmal automatisch ohne 'temperature' neu versuchen, falls übergeben:
                if "temperature" in kwargs:
                    new_kwargs = dict(kwargs)
                    new_kwargs.pop("temperature", None)
                    try:
                        return call(*args, **new_kwargs)
                    except Exception:
                        pass  # fällt unten auf die aussagekräftige Meldung zurück
                friendly = (
                    "Bekannter Fehlercode: unsupported_value (temperature). "
                    "Dieses Modell akzeptiert keinen frei wählbaren 'temperature'-Wert; "
                    "nur der Standard (1) ist erlaubt. Lösung: 'temperature' nicht setzen "
                    "oder auf 1.0 stellen."
                )
                raise RuntimeError(f"{friendly}\nOriginal: {msg}") from e
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
            # SDK-Retries bleiben 0 (wir steuern sie selbst in safe_request),
            # aber ein sinnvoller Default-Timeout kommt aus der Config.
            self._client = OpenAI(
                api_key=self.settings.api_key,
                max_retries=0,
                timeout=_REQ_TIMEOUT,
            )
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
            # WICHTIG: manche Modelle erlauben nur den Default (1) → temperature nicht setzen
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

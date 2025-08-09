"""Hilfsfunktionen zum Laden der zentralen Konfigurationsdatei.

Das Modul kapselt den Zugriff auf ``config.toml`` und stellt Standardwerte für
Modelle, Preise und Heuristiken bereit. `load_config` wird u.a. von
`app.pipeline`, `app.openai_client` und der GUI verwendet, um Einstellungen wie
Modelle, Sprache oder Chunking-Parameter zu beziehen.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback für Python <3.11
    import tomli as tomllib  # type: ignore

# Modellnamen sind konfigurierbar – passe sie ggf. an deinen Account an.
GPT5 = "gpt-5"            # Hochwertiges Modell
GPT5_MINI = "gpt-5-mini"  # guenstiger/schneller
GPT5_NANO = "gpt-5-nano"  # sehr guenstig fuer Klassifikation

DEFAULT_CLASSIFY_MODEL = GPT5_NANO
DEFAULT_QA_MODEL = GPT5_MINI

@dataclass(frozen=True)
class Price:
    input_per_mtok_usd: float
    cached_input_per_mtok_usd: float
    output_per_mtok_usd: float

PRICES = {
    GPT5: Price(1.250, 0.125, 10.000),
    GPT5_MINI: Price(0.250, 0.025, 2.000),
    GPT5_NANO: Price(0.050, 0.005, 0.400),
}

# Default-Sprache fuer Fragen/Antworten
DEFAULT_LANGUAGE = "de"

# Heuristiken fuer Kostenschaetzung
# (kann in der App per Einstellungen angepasst werden)
ESTIMATE = {
    "classify_prompt_overhead": 120,   # Tokens pro Request (ohne Segment)
    "classify_output_tokens": 24,      # kurze strukturierte Ausgabe
    "qa_prompt_overhead": 180,         # Tokens pro Chunk + Anweisung
    "qa_per_item_output": 220,         # Frage+Antwort gesamt
}


_CFG_CACHE: Dict[str, Any] | None = None

from .logging_utils import get_logger

logger = get_logger(__name__)


def load_config(path: str | None = None) -> Dict[str, Any]:
    """Load configuration from ``config.toml``.

    The result is cached so repeated calls are cheap. If ``path`` is not
    provided, the function looks for ``config.toml`` in the project root
    (one directory above this file). Missing files result in an empty
    dictionary instead of an exception, allowing callers to provide
    sensible defaults.
    """

    global _CFG_CACHE
    if _CFG_CACHE is not None:
        return _CFG_CACHE

    cfg_path = Path(path) if path else Path(__file__).resolve().parent.parent / "config.toml"
    try:
        with cfg_path.open("rb") as f:
            _CFG_CACHE = tomllib.load(f)
    except FileNotFoundError:
        _CFG_CACHE = {}
    except tomllib.TOMLDecodeError as exc:
        logger.warning("Invalid config file %s: %s", cfg_path, exc)
        _CFG_CACHE = {}
    return _CFG_CACHE


def load_api_key(cfg: Dict[str, Any] | None = None) -> tuple[str, str]:
    """Resolve the OpenAI API key from various sources.

    Priority order:
    1. Environment variable ``OPENAI_API_KEY``
    2. ``auth.api_key`` in ``config.toml``
    3. ``auth.api_key_file`` pointing to a text file with the key

    Returns a tuple ``(key, source)`` where ``source`` is one of
    ``"env"``, ``"config"``, ``"file"`` or ``""`` if no key was found.
    When loading from config or file, a warning is logged about the
    security implications.
    """

    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key.strip(), "env"

    if cfg is None:
        cfg = load_config()
    auth = cfg.get("auth", {})

    cfg_key = auth.get("api_key")
    if cfg_key:
        logger.warning(
            "API key loaded from config.toml. Storing secrets on disk is unsafe."
        )
        return str(cfg_key).strip(), "config"

    key_file = auth.get("api_key_file")
    if key_file:
        path = Path(key_file).expanduser()
        try:
            file_key = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            logger.warning("Could not read API key file %s: %s", path, exc)
            return "", ""
        logger.warning(
            "API key loaded from file %s. Plain-text storage poses risks.", path
        )
        return file_key, "file"

    return "", ""

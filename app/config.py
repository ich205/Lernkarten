# app/config.py
from dataclasses import dataclass

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

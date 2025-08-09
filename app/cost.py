"""Kostenabschätzung auf Basis der Konfiguration.

Dieses Modul wird nicht direkt von der Pipeline genutzt, dient jedoch als
Beispiel, wie sich die Modelleinstellungen und Chunking-Parameter auf die
erwarteten API-Kosten auswirken. Es liest die Preise aus ``config.toml`` und
greift für Token-Zählungen auf `app.models` sowie `app.chunking` zurück.
"""

from .models import count_tokens_rough
from .config import load_config
from .chunking import split_into_chunks

def _costs_for_model(model_name: str, in_tokens: int, out_tokens: int, cached_ratio: float = 0.0):
    # Preise aus config.toml
    cfg = load_config()
    c = cfg.get("costs", {})
    key_base = model_name
    # Fallback: ersetze Punkte durch Bindestrich für TOML keys
    key_base = key_base.replace(".", "-")
    in_cost = c.get(f"{key_base}_input_usd_per_mtok", 0) * (in_tokens / 1_000_000.0)
    cached_in_cost = c.get(f"{key_base}_cached_input_usd_per_mtok", 0) * (in_tokens * cached_ratio / 1_000_000.0)
    out_cost = c.get(f"{key_base}_output_usd_per_mtok", 0) * (out_tokens / 1_000_000.0)
    return in_cost + out_cost + 0.0  # cached optional addieren falls genutzt

def estimate_cost_for_text(text: str, model: str, label_model: str, questions_per_chunk: int = 8):
    cfg = load_config()
    chunk_cfg = cfg.get("chunking", {})
    target_tokens = chunk_cfg.get("target_tokens", 600)
    overlap_tokens = chunk_cfg.get("overlap_tokens", 60)
    max_chars = chunk_cfg.get("max_chars_per_chunk", 4000)
    chunks = split_into_chunks(text, target_tokens, overlap_tokens, max_chars)
    # Grobe Annahme: Eingabe-Token = Summe der Chunk-Tokens; Ausgabe ≈ nQ * 30 Tokens
    in_tokens = sum(count_tokens_rough(c) for c in chunks)
    # Labeling (kurze JSON Antworten), grob 60 Tokens Out je Chunk
    out_label_tokens = len(chunks) * 60
    cost_label = _costs_for_model(label_model, in_tokens, out_label_tokens)

    # QA‑Phase: ungefähre Ausgaben je Frage
    out_per_q = 60  # konservativ
    out_tokens = len(chunks) * questions_per_chunk * out_per_q
    cost_qa = _costs_for_model(model, in_tokens, out_tokens)

    return {
        "chunks": len(chunks),
        "in_tokens": in_tokens,
        "out_tokens": out_tokens,
        "cost_label_usd": cost_label,
        "cost_qa_usd": cost_qa,
        "total_cost_usd": cost_label + cost_qa,
    }

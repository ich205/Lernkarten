"""Hilfsfunktionen für die Segment-Klassifikation.

Das Modul verwendet die in `prompts.py` definierten System/User-Prompts und
ruft `models.call_json_chat` auf, um für einen Textausschnitt Labels wie
``definition`` oder ``fact`` zu bestimmen. Dies ist eine niedrigere Ebene der
Pipeline-Klassifikation.
"""

from .prompts import LABEL_SYSTEM, LABEL_USER
from .models import call_json_chat

def classify_chunk(chunk: str, model: str = "gpt-5-nano") -> dict:
    res = call_json_chat(model=model, system_prompt=LABEL_SYSTEM, user_prompt=LABEL_USER.format(chunk=chunk), temperature=0.0, max_output_tokens=300)
    data = res.get("data", {})
    usage = res.get("usage", {})
    # failsafe
    if not isinstance(data, dict) or "content_type" not in data:
        data = {"content_type": "fact", "is_meta": False, "has_questions": True, "signals": ["fallback"], "reason": "fallback"}
    data["_usage"] = usage
    return data

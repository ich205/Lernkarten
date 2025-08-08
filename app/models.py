import os, time, hashlib, json, math
from typing import Dict, Any

def _get_openai_client():
    # Import on demand to avoid hard dependency at import time
    try:
        from openai import OpenAI
    except Exception as ex:
        raise RuntimeError("OpenAI-Python-Client nicht installiert. Bitte 'python install.py' ausführen.") from ex
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY ist nicht gesetzt (wird zur Laufzeit aus GUI übergeben).")
    return OpenAI(api_key=api_key)

def set_api_key_for_process(api_key: str):
    os.environ["OPENAI_API_KEY"] = api_key.strip()

def count_tokens_rough(text: str) -> int:
    # Try tiktoken; fallback: ~4 chars/token heuristic
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, math.ceil(len(text) / 4))

def call_json_chat(model: str, system_prompt: str, user_prompt: str, temperature: float = 0.1, max_output_tokens: int = 600) -> Dict[str, Any]:
    client = _get_openai_client()
    # JSON mode if available:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
        max_tokens=max_output_tokens,
    )
    raw = response.choices[0].message.content
    try:
        data = json.loads(raw)
    except Exception:
        data = {"_raw": raw}
    usage = getattr(response, "usage", None)
    usage_dict = {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    if usage:
        usage_dict = {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens, "total_tokens": usage.total_tokens}
    return {"data": data, "usage": usage_dict}

def call_text_chat(model: str, system_prompt: str, user_prompt: str, temperature: float = 0.2, max_output_tokens: int = 800) -> Dict[str, Any]:
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_output_tokens,
    )
    content = response.choices[0].message.content
    usage = getattr(response, "usage", None)
    usage_dict = {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    if usage:
        usage_dict = {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens, "total_tokens": usage.total_tokens}
    return {"text": content, "usage": usage_dict}

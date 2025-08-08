# app/pipeline.py
from __future__ import annotations
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from .tokenizer_utils import Tokenizer
from .config import PRICES, ESTIMATE
from .openai_client import OpenAIClient, OpenAISettings
from .pdf_ingest import extract_text_from_pdf, segment_text
from .excel_export import to_excel

@dataclass
class Segment:
    text: str
    label: str | None = None
    keep: bool = True

@dataclass
class CostBreakdown:
    total_input_tokens: int
    total_output_tokens: int
    usd: float

class LernkartenPipeline:
    def __init__(self, settings: OpenAISettings):
        self.settings = settings
        self.client = OpenAIClient(settings)
        self.tok = Tokenizer()

    def load_and_segment(self, path: str) -> List[Segment]:
        raw = extract_text_from_pdf(path)
        chunks = segment_text(raw)
        return [Segment(text=c) for c in chunks]

    def classify(self, segments: List[Segment]) -> List[Segment]:
        out = []
        for s in segments:
            data = self.client.classify_segment(s.text[:5000])  # Sicherheit
            s.label = data.get("label","Fakt")
            s.keep = bool(data.get("keep", True))
            out.append(s)
        return out

    def generate_cards(self, segments: List[Segment], questions_per_chunk: int, language: str) -> List[Dict[str, Any]]:
        rows = []
        for s in segments:
            if not s.keep:
                continue
            items = self.client.gen_qa_for_chunk(s.text[:8000], questions_per_chunk, language=language)
            rows.append({
                "original": s.text,
                "fragen": [x["frage"] for x in items],
                "antworten": [x["antwort"] for x in items],
                "labels": [s.label] if s.label else [],
                "hinweise": "",
            })
        return rows

    # === Kosten-Schaetzung ===
    def estimate_cost(
        self,
        full_text: str,
        n_segments: int,
        seg_avg_tokens: int,
        questions_per_chunk: int,
        classify_model: str,
        qa_model: str,
    ) -> Dict[str, Any]:
        """
        Sehr grobe Schaetzung – passt die Konstanten in config.ESTIMATE an.
        """
        prices_c = PRICES[classify_model]
        prices_q = PRICES[qa_model]

        # Klassifikation
        cls_in = n_segments * (ESTIMATE["classify_prompt_overhead"] + seg_avg_tokens)
        cls_out = n_segments * ESTIMATE["classify_output_tokens"]

        # QA: pro Segment 1 Request mit n Fragen
        qa_in = n_segments * (ESTIMATE["qa_prompt_overhead"] + seg_avg_tokens)
        qa_out = n_segments * questions_per_chunk * ESTIMATE["qa_per_item_output"]

        # USD pro 1 Mio Token
        usd_cls = (cls_in/1e6) * prices_c.input_per_mtok_usd + (cls_out/1e6) * prices_c.output_per_mtok_usd
        usd_qa  = (qa_in/1e6) * prices_q.input_per_mtok_usd + (qa_out/1e6) * prices_q.output_per_mtok_usd

        total = {
            "classification": {
                "input_tokens": int(cls_in),
                "output_tokens": int(cls_out),
                "usd": round(usd_cls, 4),
                "model": classify_model,
            },
            "qa": {
                "input_tokens": int(qa_in),
                "output_tokens": int(qa_out),
                "usd": round(usd_qa, 4),
                "model": qa_model,
            },
        }
        total["sum_usd"] = round(total["classification"]["usd"] + total["qa"]["usd"], 4)
        return total

    def tokens_in_text(self, text: str) -> int:
        return self.tok.count(text)

    def export_excel(self, rows: List[Dict[str, Any]], out_path: str) -> None:
        to_excel(rows, out_path)

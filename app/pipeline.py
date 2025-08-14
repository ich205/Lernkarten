"""Zentrale Verarbeitungslogik für PDFs → Lernkarten.

Die `LernkartenPipeline` verbindet alle Einzelmodule: PDF-Einlesung,
Segmentierung, Klassifikation, Frage-Antwort-Erzeugung und Export. Viele
Standardwerte stammen aus ``config.toml`` und werden beim Erstellen der
`OpenAISettings` übergeben.
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple, Callable, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from .tokenizer_utils import Tokenizer
from .logging_utils import get_logger
try:
    from openai import OpenAIError  # type: ignore
except Exception:  # pragma: no cover
    OpenAIError = Exception  # type: ignore
logger = get_logger(__name__)

from .config import PRICES, ESTIMATE
from .openai_client import OpenAIClient, OpenAISettings
from .pdf_ingest import extract_text_from_pdf, segment_text
from .excel_export import to_excel
from .pipeline_models import Segment, QAItem, CardRow

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
        """Liest eine PDF ein und segmentiert sie in grobe Abschnitte.

        Die feine Chunking-Logik (`app.chunking`) wird später angewendet; hier
        erfolgt nur eine heuristische Absatz-Zerlegung über `pdf_ingest.segment_text`.
        """

        raw = extract_text_from_pdf(path)
        chunks = segment_text(raw)
        # Filter obvious table-of-contents segments like "Inhaltsverzeichnis" or
        # "Glossar" early so that they never reach the classifier.  Those
        # headings typically do not contain meaningful learning content.
        from .segment_filters import is_outline_segment

        chunks = [c for c in chunks if not is_outline_segment(c)]
        return [Segment(text=c) for c in chunks]

    def classify(
        self,
        segments: List[Segment],
        progress_cb: Optional[Callable[[int, int], None]] = None,
        stop_cb: Optional[Callable[[], bool]] = None,
        pause_event: Any | None = None,
    ) -> List[Segment]:
        """Klassifiziert Segmente und erlaubt Fortschritts-Callbacks sowie Stop/Pause."""
        out = []
        self._dropped_segments = 0
        bullet_pattern = r'^\s*[-*•0-9]+[\.\)]'
        total = len(segments)
        for i, s in enumerate(segments, 1):
            if stop_cb and stop_cb():
                raise RuntimeError("Abgebrochen")
            if pause_event:
                pause_event.wait()
            got_any = False
            paragraphs = [p for p in s.text.split("\n\n") if p.strip()]
            for para in paragraphs:
                label_seq: List[Tuple[str, str]] = []
                # Split paragraph into sentences (treat bullet list items as separate sentences)
                if "\n" in para:
                    lines = para.splitlines()
                    nonempty = [ln for ln in lines if ln.strip()]
                    if nonempty and all(re.match(bullet_pattern, ln) for ln in nonempty):
                        sentences = [ln.strip() for ln in nonempty]
                    else:
                        para_text = para.replace("\n", " ")
                        sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZÄÖÜ])', para_text)
                else:
                    sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZÄÖÜ])', para)
                for sentence in [sent for sent in sentences if sent.strip()]:
                    try:
                        data = self.client.classify_segment(sentence[:5000])
                    except OpenAIError as e:
                        # Transienter API-/Netzfehler → nicht abbrechen, Satz durchwinken
                        logger.warning(
                            "Klassifikation uebersprungen (API-Fehler): %s", e
                        )
                        data = {
                            "label": "Fakt",
                            "keep": True,
                            "reason": "fallback_after_error",
                        }
                    except Exception as e:
                        logger.warning(
                            "Klassifikation uebersprungen (Fehler): %s", e
                        )
                        data = {
                            "label": "Fakt",
                            "keep": True,
                            "reason": "fallback_after_error",
                        }
                    label = data.get("label", "Fakt")
                    keep_flag = bool(data.get("keep", True))
                    if not keep_flag:
                        continue
                    label_seq.append((label, sentence.strip()))
                if not label_seq:
                    continue
                got_any = True
                # Group consecutive sentences with the same label
                current_label, current_text = label_seq[0]
                for label, text_part in label_seq[1:]:
                    if label == current_label:
                        current_text += " " + text_part
                    else:
                        seg_new = Segment(text=current_text, keep=True)
                        seg_new.label = current_label
                        out.append(seg_new)
                        current_label = label
                        current_text = text_part
                seg_new = Segment(text=current_text, keep=True)
                seg_new.label = current_label
                out.append(seg_new)
            if not got_any:
                self._dropped_segments += 1
            if progress_cb:
                progress_cb(i, total)
        return out

    def generate_cards(
        self,
        segments: List[Segment],
        max_questions_per_chunk: int,
        language: str,
        progress_cb: Optional[Callable[[int, int, int], None]] = None,
        stop_cb: Optional[Callable[[], bool]] = None,
        pause_event: Any | None = None,
        card_cb: Optional[Callable[[str, str, str], None]] = None,
        max_workers: int = 3,
        budget_usd: float | None = None,
        limit_by_budget: bool = False,
        adjust_cb: Optional[Callable[[int], None]] = None,
    ) -> List[CardRow]:
        """Generiert Lernkarten dynamisch je nach Segmentlänge.

        Bei kleinen Inputs wird sequenziell gearbeitet; ab vier Segmenten wird
        standardmäßig parallelisiert (max. ``max_workers`` Threads)."""
        rows: List[CardRow] = []
        card_count = 0
        total = len(segments)

        if limit_by_budget and budget_usd and budget_usd > 0:
            kept = [s for s in segments if s.keep]
            if kept:
                token_counts = [self.tok.count(s.text) for s in kept]
                seg_avg = int(sum(token_counts) / len(token_counts))
                est = self.estimate_cost(
                    "",
                    len(kept),
                    seg_avg,
                    max_questions_per_chunk,
                    self.settings.classify_model,
                    self.settings.qa_model,
                )
                total_cost = est.get("sum_usd", 0.0)
                if total_cost > budget_usd:
                    factor = budget_usd / total_cost
                    scaled = max(1, int(max_questions_per_chunk * factor))
                    if scaled < max_questions_per_chunk:
                        max_questions_per_chunk = scaled
                        if adjust_cb:
                            adjust_cb(scaled)
                        logger.info(
                            "Fragen pro Segment automatisch auf %s reduziert, um Budget einzuhalten.",
                            scaled,
                        )

        # --- Sequenziell: kleine Inputs oder Parallelisierung deaktiviert ---
        if total < 4 or max_workers <= 1:
            for i, s in enumerate(segments, 1):
                if not s.keep:
                    if progress_cb:
                        progress_cb(i, total, card_count)
                    continue
                if stop_cb and stop_cb():
                    raise RuntimeError("Abgebrochen")
                if pause_event:
                    pause_event.wait()
                tokens = self.tok.count(s.text)
                n_questions = max(1, min(max_questions_per_chunk, tokens // 100))
                items: List[QAItem] = self.client.gen_qa_for_chunk(
                    s.text[:8000], n_questions, language=language
                )
                if not items:
                    if progress_cb:
                        progress_cb(i, total, card_count)
                    continue
                fragen: List[str] = []
                antworten: List[str] = []
                for x in items:
                    fragen.append(x.frage)
                    antworten.append(x.antwort)
                    if card_cb:
                        card_cb(s.text, x.frage, x.antwort)
                card_count += len(items)
                rows.append(
                    CardRow(
                        original=s.text,
                        fragen=fragen,
                        antworten=antworten,
                        labels=[s.label] if getattr(s, "label", None) else [],
                    )
                )
                if progress_cb:
                    progress_cb(i, total, card_count)
            return rows

        # --- Parallel: groessere Inputs ---
        indexed_rows: Dict[int, CardRow] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures: Dict[Any, Tuple[int, Segment]] = {}
            for i, s in enumerate(segments, 1):
                if stop_cb and stop_cb():
                    raise RuntimeError("Abgebrochen")
                if not s.keep:
                    if progress_cb:
                        progress_cb(i, total, card_count)
                    continue
                if pause_event:
                    pause_event.wait()
                tokens = self.tok.count(s.text)
                n_questions = max(1, min(max_questions_per_chunk, tokens // 100))
                fut = ex.submit(
                    self.client.gen_qa_for_chunk, s.text[:8000], n_questions, language
                )
                futures[fut] = (i, s)

            for fut in as_completed(futures):
                i, s = futures[fut]
                try:
                    items: List[QAItem] = fut.result()
                except Exception as e:
                    logger.warning("OpenAI-Fehler: %s", e)
                    items = None
                if not items:
                    if progress_cb:
                        progress_cb(i, total, card_count)
                    continue
                fragen: List[str] = []
                antworten: List[str] = []
                for x in items:
                    fragen.append(x.frage)
                    antworten.append(x.antwort)
                    if card_cb:
                        card_cb(s.text, x.frage, x.antwort)
                card_count += len(items)
                indexed_rows[i] = CardRow(
                    original=s.text,
                    fragen=fragen,
                    antworten=antworten,
                    labels=[s.label] if getattr(s, "label", None) else [],
                )
                if progress_cb:
                    progress_cb(i, total, card_count)

        # sortieren nach Ursprungsreihenfolge
        for i in sorted(indexed_rows):
            rows.append(indexed_rows[i])
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

    def export_excel(self, rows: List[CardRow], out_path: str) -> None:
        to_excel(rows, out_path)


# Übergangs-Alias für alte Imports, bitte mittelfristig entfernen:
Pipeline = LernkartenPipeline

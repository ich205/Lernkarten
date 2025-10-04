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
import os
import hashlib
import json
import re
from pathlib import Path
from .tokenizer_utils import Tokenizer
from .logging_utils import get_logger
try:
    from openai import OpenAIError  # type: ignore
except Exception:  # pragma: no cover
    OpenAIError = Exception  # type: ignore
logger = get_logger(__name__)

from .config import PRICES, ESTIMATE, DEFAULT_LANGUAGE, load_config, Price
from .agents import (
    Task,
    TaskQueue,
    SegmentAgent,
    ClassificationAgent,
    QaAgent,
    ExportAgent,
)
from .openai_client import OpenAIClient, OpenAISettings
from .cache import SegmentCache
from .pdf_ingest import extract_text_from_pdf, segment_text
from .excel_export import to_excel
from .pipeline_models import Segment, QAItem, CardRow

@dataclass
class CostBreakdown:
    total_input_tokens: int
    total_output_tokens: int
    usd: float

class LernkartenPipeline:
    def __init__(
        self,
        settings: OpenAISettings,
        *,
        cache: SegmentCache | None = None,
        cache_enabled: bool = True,
    ):
        self.settings = settings
        self.client = OpenAIClient(settings)
        self.tok = Tokenizer()
        self.cache = cache if cache is not None else SegmentCache(
            "qa_results", enabled=cache_enabled
        )

    def load_and_segment(self, path: str) -> List[Segment]:
        """Liest eine PDF ein und segmentiert sie in grobe Abschnitte.

        Die feine Chunking-Logik (`app.chunking`) wird später angewendet; hier
        erfolgt nur eine heuristische Absatz-Zerlegung über `pdf_ingest.segment_text`.
        """

        if path.lower().endswith(".txt"):
            raw = Path(path).read_text(encoding="utf-8", errors="ignore")
        else:
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
                cache_key = self._qa_cache_key(s.text, n_questions, language)
                items = self._cache_get(cache_key)
                if items is None:
                    items = self.client.gen_qa_for_chunk(
                        s.text[:8000], n_questions, language=language
                    )
                    if items:
                        self._cache_set(cache_key, items)
                if not items:
                    if progress_cb:
                        progress_cb(i, total, card_count)
                    continue
                if card_cb:
                    for x in items:
                        card_cb(s.text, x.frage, x.antwort)
                card_count += len(items)
                rows.append(self._build_row(s, items))
                if progress_cb:
                    progress_cb(i, total, card_count)
            return rows

        # --- Parallel: groessere Inputs ---
        indexed_rows: Dict[int, CardRow] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures: Dict[Any, Tuple[int, Segment, str]] = {}
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
                cache_key = self._qa_cache_key(s.text, n_questions, language)
                cached_items = self._cache_get(cache_key)
                if cached_items is not None:
                    if card_cb:
                        for x in cached_items:
                            card_cb(s.text, x.frage, x.antwort)
                    card_count += len(cached_items)
                    indexed_rows[i] = self._build_row(s, cached_items)
                    if progress_cb:
                        progress_cb(i, total, card_count)
                    continue
                fut = ex.submit(
                    self.client.gen_qa_for_chunk, s.text[:8000], n_questions, language
                )
                futures[fut] = (i, s, cache_key)

            for fut in as_completed(futures):
                i, s, cache_key = futures[fut]
                try:
                    items: List[QAItem] = fut.result()
                except Exception as e:
                    logger.warning("OpenAI-Fehler: %s", e)
                    items = None
                if not items:
                    if progress_cb:
                        progress_cb(i, total, card_count)
                    continue
                self._cache_set(cache_key, items)
                if card_cb:
                    for x in items:
                        card_cb(s.text, x.frage, x.antwort)
                card_count += len(items)
                indexed_rows[i] = self._build_row(s, items)
                if progress_cb:
                    progress_cb(i, total, card_count)

        # sortieren nach Ursprungsreihenfolge
        for i in sorted(indexed_rows):
            rows.append(indexed_rows[i])
        return rows

    # === Kosten-Schaetzung ===
    def run(
        self,
        path: str,
        *,
        out_dir: str,
        max_questions_per_chunk: int = 8,
        language: str | None = None,
        budget_usd: float | None = None,
        limit_by_budget: bool = False,
        stop_cb: Optional[Callable[[], bool]] = None,
        pause_event: Any | None = None,
        progress_cb: Optional[Callable[[str, int, int, int], None]] = None,
        status_cb: Optional[Callable[[str], None]] = None,
        log_cb: Optional[Callable[[str], None]] = None,
        card_cb: Optional[Callable[[str, str, str], None]] = None,
        export_title: str | None = None,
        agent_state_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        """High-level orchestration used by the GUI via chained agents."""

        lang = (language or DEFAULT_LANGUAGE).strip() or DEFAULT_LANGUAGE
        cfg = load_config()
        model_cfg = cfg.get("models", {})
        max_workers_cfg = int(model_cfg.get("max_parallel_requests", 3) or 3)
        export_dir_abs = os.path.abspath(out_dir)
        os.makedirs(export_dir_abs, exist_ok=True)

        context: Dict[str, Any] = {
            "pipeline": self,
            "stop_cb": stop_cb or (lambda: False),
            "pause_event": pause_event,
            "progress_cb": progress_cb,
            "status_cb": status_cb,
            "log_cb": log_cb,
            "card_cb": card_cb,
            "export_dir": export_dir_abs,
            "logger": logger,
            "max_workers": max_workers_cfg,
            "agent_state_cb": agent_state_cb,
        }

        segment_queue = TaskQueue("segment")
        classify_queue = TaskQueue("classify")
        qa_queue = TaskQueue("qa")
        export_queue = TaskQueue("export")

        initial_payload = {
            "path": path,
            "export_title": export_title,
            "max_questions_per_chunk": max_questions_per_chunk,
            "language": lang,
            "budget_usd": budget_usd,
            "limit_by_budget": bool(limit_by_budget and budget_usd and budget_usd > 0),
        }
        segment_queue.add(Task(name="segment", payload=initial_payload))

        agents = [
            SegmentAgent("segment", segment_queue, classify_queue),
            ClassificationAgent("classify", classify_queue, qa_queue),
            QaAgent("qa", qa_queue, export_queue),
            ExportAgent("export", export_queue, None),
        ]

        if agent_state_cb:
            for agent in agents:
                agent_state_cb(
                    {
                        "agent": agent.name,
                        "status": "ready",
                        "task": None,
                        "inbox": agent.inbox.size(),
                        "outbox": agent.outbox.size() if agent.outbox else 0,
                        "inbox_name": agent.inbox.name,
                        "outbox_name": agent.outbox.name if agent.outbox else "",
                    }
                )

        while True:
            pending = any(agent.has_pending() for agent in agents)
            if not pending:
                break

            any_processed = False
            for agent in agents:
                if not agent.has_pending():
                    continue
                processed = agent.poll(context)
                if processed:
                    any_processed = True
            if not any_processed:
                break

        if agent_state_cb:
            for agent in agents:
                agent_state_cb(
                    {
                        "agent": agent.name,
                        "status": "idle",
                        "task": None,
                        "inbox": agent.inbox.size(),
                        "outbox": agent.outbox.size() if agent.outbox else 0,
                        "inbox_name": agent.inbox.name,
                        "outbox_name": agent.outbox.name if agent.outbox else "",
                    }
                )

        if context.get("result"):
            return context["result"]

        stop_requested = context["stop_cb"]() if callable(context.get("stop_cb")) else False
        if stop_requested:
            raise RuntimeError("Abgebrochen")
        raise RuntimeError("Export fehlgeschlagen – kein Ergebnis vorhanden.")

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
        prices_c = self._price_for(classify_model)
        prices_q = self._price_for(qa_model)

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

    # --- cache helpers ------------------------------------------------------
    def _qa_cache_key(self, text: str, n_questions: int, language: str) -> str:
        payload = json.dumps(
            {
                "text": text,
                "n": n_questions,
                "lang": language,
                "model": self.settings.qa_model,
            },
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _cache_get(self, key: str) -> List[QAItem] | None:
        if not self.cache:
            return None
        raw = self.cache.get(key)
        if not raw:
            return None
        items: List[QAItem] = []
        for entry in raw:
            frage = entry.get("frage")
            antwort = entry.get("antwort")
            if not isinstance(frage, str) or not isinstance(antwort, str):
                continue
            labels = entry.get("labels")
            if labels is not None and not isinstance(labels, list):
                labels = None
            items.append(QAItem(frage=frage, antwort=antwort, labels=labels))
        return items or None

    def _cache_set(self, key: str, items: List[QAItem]) -> None:
        if not self.cache or not items:
            return
        serialisable = [
            {
                "frage": i.frage,
                "antwort": i.antwort,
                "labels": i.labels,
            }
            for i in items
        ]
        self.cache.set(key, serialisable)

    def _build_row(self, segment: Segment, items: List[QAItem]) -> CardRow:
        fragen = [x.frage for x in items]
        antworten = [x.antwort for x in items]
        labels = [segment.label] if getattr(segment, "label", None) else []
        merged_labels = list(labels)
        # attach optional metadata from QA items if present
        for item in items:
            if item.labels:
                merged_labels.extend(str(lbl) for lbl in item.labels if lbl)
        unique_labels: List[str] = []
        seen: set[str] = set()
        for lbl in merged_labels:
            if lbl not in seen:
                seen.add(lbl)
                unique_labels.append(lbl)
        return CardRow(
            original=segment.text,
            fragen=fragen,
            antworten=antworten,
            labels=unique_labels,
        )

    def _price_for(self, model_id: str) -> Price:
        if model_id in PRICES:
            return PRICES[model_id]

        cfg = load_config()
        costs = cfg.get("costs", {})
        key = model_id.replace(".", "-")
        try:
            return Price(
                float(costs[f"{key}_input_usd_per_mtok"]),
                float(costs.get(f"{key}_cached_input_usd_per_mtok", 0.0)),
                float(costs[f"{key}_output_usd_per_mtok"]),
            )
        except KeyError as exc:
            raise ValueError(
                f"Kostenangaben für Modell '{model_id}' fehlen in config.toml"
            ) from exc


# Übergangs-Alias für alte Imports, bitte mittelfristig entfernen:
Pipeline = LernkartenPipeline

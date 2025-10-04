"""Lightweight agent orchestration for the Lernkarten pipeline."""

from __future__ import annotations

import os
import re
from time import strftime, time as now
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Iterable, MutableMapping, Optional

from .logging_utils import get_logger

logger = get_logger(__name__)

AgentContext = MutableMapping[str, Any]


@dataclass
class Task:
    """Simple container handed between agents."""

    name: str
    payload: Dict[str, Any]
    created_at: float = field(default_factory=now)


class TaskQueue:
    """FIFO container used as inbox/outbox for agents."""

    def __init__(self, name: str):
        self.name = name
        self._queue: Deque[Task] = deque()

    def add(self, task: Task) -> None:
        self._queue.append(task)

    def pop(self) -> Optional[Task]:
        return self._queue.popleft() if self._queue else None

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._queue)

    def has_tasks(self) -> bool:
        return bool(self._queue)

    def size(self) -> int:
        return len(self._queue)


class Agent:
    """Base class for pipeline agents."""

    def __init__(self, name: str, inbox: TaskQueue, outbox: TaskQueue | None = None):
        self.name = name
        self.inbox = inbox
        self.outbox = outbox

    def poll(self, context: AgentContext) -> bool:
        """Process a single task from the inbox if available."""

        self._notify_state(context, status="checking", task=None)

        task = self.inbox.pop()
        if task is None:
            self._notify_state(context, status="idle", task=None)
            return False

        if self._stop_requested(context):
            raise RuntimeError("Abgebrochen")

        self._notify_state(context, status="active", task=task.name)
        result = self.handle(task, context)

        if result is None or self.outbox is None:
            self._notify_state(context, status="done", task=task.name)
            return True

        forwarded = 0
        if isinstance(result, Task):
            self.outbox.add(result)
            forwarded = 1
        elif isinstance(result, Iterable):
            for item in result:
                if not isinstance(item, Task):
                    raise TypeError(
                        f"Agent {self.name} produced non-Task item: {type(item)!r}"
                    )
                self.outbox.add(item)
                forwarded += 1
        else:
            raise TypeError(f"Agent {self.name} returned unsupported result: {type(result)!r}")

        self._notify_state(context, status="forwarded", task=task.name, forwarded=forwarded)
        return True

    def has_pending(self) -> bool:
        return self.inbox.has_tasks()

    def handle(self, task: Task, context: AgentContext) -> Task | Iterable[Task] | None:
        raise NotImplementedError

    def log(self, context: AgentContext, message: str) -> None:
        log_cb: Optional[Callable[[str], None]] = context.get("log_cb")
        if log_cb:
            log_cb(message)
        else:
            context.get("logger", logger).info(message)

    def status(self, context: AgentContext, message: str) -> None:
        status_cb: Optional[Callable[[str], None]] = context.get("status_cb")
        if status_cb:
            status_cb(message)

    def progress(
        self,
        context: AgentContext,
        phase: str,
        current: int,
        total: int,
        cards: int = 0,
    ) -> None:
        progress_cb: Optional[Callable[[str, int, int, int], None]] = context.get("progress_cb")
        if progress_cb:
            progress_cb(phase, current, total, cards)

    def _stop_requested(self, context: AgentContext) -> bool:
        stop_cb: Optional[Callable[[], bool]] = context.get("stop_cb")
        return bool(stop_cb and stop_cb())

    def _notify_state(
        self,
        context: AgentContext,
        *,
        status: str,
        task: Optional[str],
        forwarded: Optional[int] = None,
    ) -> None:
        callback: Optional[Callable[[Dict[str, Any]], None]] = context.get("agent_state_cb")
        if not callback:
            return
        info: Dict[str, Any] = {
            "agent": self.name,
            "status": status,
            "task": task,
            "inbox": self.inbox.size(),
            "outbox": self.outbox.size() if self.outbox else 0,
            "inbox_name": self.inbox.name,
            "outbox_name": self.outbox.name if self.outbox else "",
        }
        if forwarded is not None:
            info["forwarded"] = forwarded
        callback(info)


class SegmentAgent(Agent):
    """Reads and segments the source document."""

    def handle(self, task: Task, context: AgentContext) -> Task:
        pipeline = context["pipeline"]
        path = task.payload["path"]

        self.status(context, "Segmentiere Dokument …")
        segments = pipeline.load_and_segment(path)
        if not segments:
            raise ValueError("Keine Segmente gefunden – enthält die Datei Text?")

        total_pages = 0
        if path.lower().endswith(".pdf"):
            try:  # pragma: no cover - optional dependency
                from pypdf import PdfReader  # type: ignore

                total_pages = len(PdfReader(path).pages)
            except Exception:
                total_pages = 0

        context["total_pages"] = total_pages
        context["segments_total"] = len(segments)
        context["cards_total"] = 0

        self.log(context, f"[Segment] {len(segments)} Rohsegmente ermittelt")
        self.progress(context, "segment", len(segments), len(segments) or 1, 0)

        payload = dict(task.payload)
        payload["segments"] = segments
        payload["total_pages"] = total_pages
        return Task(name="classify", payload=payload)


class ClassificationAgent(Agent):
    """Classifies and filters segments."""

    def handle(self, task: Task, context: AgentContext) -> Task:
        from .segment_filters import is_outline_segment, looks_like_outline_list

        pipeline = context["pipeline"]
        segments = task.payload["segments"]
        pause_event = context.get("pause_event")

        self.status(context, "Klassifiziere Segmente …")

        def cls_progress(i: int, total: int) -> None:
            self.progress(context, "classify", i, total, 0)

        classified = pipeline.classify(
            segments,
            progress_cb=cls_progress,
            stop_cb=context.get("stop_cb"),
            pause_event=pause_event,
        )

        filtered = []
        removed = 0
        for seg in classified:
            text = seg.text.strip()
            label = getattr(seg, "label", "")
            if is_outline_segment(text) or looks_like_outline_list(text, label):
                removed += 1
                continue
            filtered.append(seg)

        self.log(
            context,
            f"[Classify] {len(filtered)} Segmente behalten, {removed} verworfen",
        )

        if not filtered:
            raise ValueError("Alle Segmente wurden als Vorwort/Gliederung verworfen.")

        context["segments_total"] = len(filtered)
        payload = dict(task.payload)
        payload["segments"] = filtered
        return Task(name="qa", payload=payload)


class QaAgent(Agent):
    """Generates question/answer pairs for the remaining segments."""

    def handle(self, task: Task, context: AgentContext) -> Task:
        pipeline = context["pipeline"]
        segments = task.payload["segments"]
        max_questions = task.payload["max_questions_per_chunk"]
        language = task.payload.get("language")
        budget_usd = task.payload.get("budget_usd")
        limit_flag = bool(task.payload.get("limit_by_budget"))
        pause_event = context.get("pause_event")
        stop_cb = context.get("stop_cb")
        max_workers = context.get("max_workers", 3)

        self.status(context, "Erzeuge Lernkarten …")

        def gen_progress(i: int, total: int, cards: int) -> None:
            self.progress(context, "generate", i, total, cards)
            context["cards_total"] = cards

        def adjust_cb(scaled: int) -> None:
            self.log(context, f"[Budget] Fragen pro Segment automatisch auf {scaled} reduziert")
            self.status(context, f"Budget aktiv – Fragen pro Segment jetzt {scaled}")

        def card_cb(original: str, frage: str, antwort: str) -> None:
            preview_cb: Optional[Callable[[str, str, str], None]] = context.get("card_cb")
            if preview_cb:
                preview_cb(original, frage, antwort)

        rows = pipeline.generate_cards(
            segments,
            max_questions,
            language,
            progress_cb=gen_progress,
            stop_cb=stop_cb,
            pause_event=pause_event,
            card_cb=card_cb,
            max_workers=max_workers,
            budget_usd=budget_usd,
            limit_by_budget=limit_flag,
            adjust_cb=adjust_cb if limit_flag else None,
        )

        if not rows:
            raise RuntimeError("Keine Lernkarten generiert.")

        payload = dict(task.payload)
        payload["rows"] = rows
        return Task(name="export", payload=payload)


class ExportAgent(Agent):
    """Writes the generated cards to disk."""

    def handle(self, task: Task, context: AgentContext) -> None:
        pipeline = context["pipeline"]
        rows = task.payload["rows"]
        export_dir = context["export_dir"]
        os.makedirs(export_dir, exist_ok=True)

        title = task.payload.get("export_title")
        if not title:
            title = os.path.splitext(os.path.basename(task.payload["path"]))[0] or "Lernkarten"
        safe_title = re.sub(r"[^A-Za-z0-9_-]+", "_", title).strip("_") or "Lernkarten"

        from time import strftime

        timestamp = strftime("%Y%m%d_%H%M")
        out_path = os.path.abspath(os.path.join(export_dir, f"{safe_title}_{timestamp}.xlsx"))

        pipeline.export_excel(rows, out_path)
        self.log(context, f"[Export] Datei gespeichert: {out_path}")
        self.status(context, "Fertig")
        self.progress(context, "export", len(rows), max(len(rows), 1), len(rows))

        context["result"] = out_path
        return None


__all__ = [
    "Task",
    "TaskQueue",
    "Agent",
    "SegmentAgent",
    "ClassificationAgent",
    "QaAgent",
    "ExportAgent",
]

"""Very small JSON-based cache used to store expensive LLM results.

The cache is intentionally simple: values are serialised to JSON and kept in a
per-user directory (see :mod:`app.paths`).  The goal is to avoid repeated API
calls for identical inputs while keeping the on-disk footprint bounded.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

from .logging_utils import get_logger
from .paths import cache_dir

logger = get_logger(__name__)


class SegmentCache:
    """Disk-backed LRU-ish cache for segment-based computations."""

    def __init__(self, name: str, enabled: bool = True, max_entries: int = 500):
        self.enabled = enabled
        self.max_entries = max_entries
        self.path: Path = cache_dir("segments") / f"{name}.json"
        self._data: "OrderedDict[str, Any]" = OrderedDict()
        if self.enabled:
            self._load()

    # --- persistence helpers -------------------------------------------------
    def _load(self) -> None:
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return
        except json.JSONDecodeError as exc:
            logger.warning("Ignoring invalid cache %s: %s", self.path, exc)
            try:
                self.path.unlink()
            except OSError:
                pass
            return
        if isinstance(data, dict):
            for key, value in data.items():
                self._data[key] = value

    def _dump(self) -> None:
        try:
            tmp = self.path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(self._data, fh)
            tmp.replace(self.path)
        except OSError as exc:
            logger.warning("Could not write cache %s: %s", self.path, exc)

    # --- public API ----------------------------------------------------------
    def get(self, key: str) -> Any | None:
        if not self.enabled:
            return None
        try:
            value = self._data.pop(key)
        except KeyError:
            return None
        # reinsert to mark as recently used
        self._data[key] = value
        return value

    def set(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        # normalise to JSON-serialisable data
        try:
            json.dumps(value)
        except TypeError:
            logger.debug("Value for cache key %s is not JSON serialisable", key)
            return
        if key in self._data:
            self._data.pop(key)
        self._data[key] = value
        while len(self._data) > self.max_entries:
            self._data.popitem(last=False)
        self._dump()

    def clear(self) -> None:
        self._data.clear()
        if self.path.exists():
            try:
                self.path.unlink()
            except OSError:
                pass

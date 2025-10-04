"""Utility helpers for locating writable application directories.

The application ships as a GUI tool intended for end users.  When distributed
via installers or PyInstaller bundles, the package directory itself is often
read-only.  This module centralises the discovery of per-user locations for
logs, caches and state files so that other parts of the code base can rely on a
consistent, writable location across platforms.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

APP_NAME = "Lernkarten"


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _home() -> Path:
    return Path(os.path.expanduser("~"))


def state_dir(*parts: str) -> Path:
    """Return a directory intended for persistent application data."""

    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", _home() / "AppData" / "Roaming"))
    elif system == "Darwin":
        base = _home() / "Library" / "Application Support"
    else:
        base = _home() / ".local" / "share"
    path = base / APP_NAME
    for part in parts:
        path = path / part
    return _ensure_dir(path)


def cache_dir(*parts: str) -> Path:
    """Return a directory intended for non-critical cached data."""

    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", _home() / "AppData" / "Local"))
    elif system == "Darwin":
        base = _home() / "Library" / "Caches"
    else:
        base = _home() / ".cache"
    path = base / APP_NAME
    for part in parts:
        path = path / part
    return _ensure_dir(path)


def log_dir(*parts: str) -> Path:
    """Return a directory for log files."""

    # Logs follow the same convention as other state files on most systems.
    path = state_dir("logs")
    for part in parts:
        path = path / part
    return _ensure_dir(path)

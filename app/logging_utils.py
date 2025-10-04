"""Einfache Logger-Konfiguration.

Stellt `get_logger` bereit, das sowohl in der GUI als auch in Skripten für eine
einheitliche Log-Ausgabe sorgt. Die Logdateien landen im
benutzerspezifischen Anwendungsordner (vgl. :mod:`app.paths`).
"""

import datetime
import logging

from .paths import log_dir


def get_logger(name: str = "gsa") -> logging.Logger:
    """Return a module-specific logger configured once for the application."""

    handlers: list[logging.Handler] = []
    try:
        logfile = log_dir() / f"gsa_{datetime.datetime.now().strftime('%Y%m%d')}.log"
        handlers.append(logging.FileHandler(logfile, encoding="utf-8"))
    except OSError:
        # Fallback: file logging unavailable; continue with console output only.
        pass

    handlers.append(logging.StreamHandler())

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            handlers=handlers,
        )
    return logging.getLogger(name)

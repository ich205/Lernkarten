"""Einfache Logger-Konfiguration.

Stellt `get_logger` bereit, das sowohl in der GUI als auch in Skripten für eine
einheitliche Log-Ausgabe sorgt. Die Logdateien liegen im Unterordner ``.logs``.
"""

import logging, pathlib, datetime

def get_logger(name="gsa"):
    log_dir = pathlib.Path(".logs")
    log_dir.mkdir(exist_ok=True)
    logfile = log_dir / f"gsa_{datetime.datetime.now().strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(logfile, encoding="utf-8"), logging.StreamHandler()],
    )
    return logging.getLogger(name)

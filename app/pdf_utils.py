"""Low-level PDF-Helfer.

Dieses Modul wird von der GUI genutzt, um Text aus PDF-Dateien oder
alternativen Quellen zu extrahieren.
"""

from . import pdf_ingest
from .logging_utils import get_logger

logger = get_logger(__name__)


def extract_text_from_pdf(path):
    """Delegiere die Extraktion an :mod:`pdf_ingest`."""
    return pdf_ingest.extract_text_from_pdf(path)


def try_extract_text(path):
    path = str(path)
    if path.lower().endswith(".pdf"):
        return extract_text_from_pdf(path)
    else:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except OSError as exc:
            logger.warning("Could not read text file %s: %s", path, exc)
            return ""

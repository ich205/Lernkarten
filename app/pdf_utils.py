"""Thin wrapper – bitte direkt :mod:`app.pdf_ingest` verwenden."""

from .pdf_ingest import extract_text_from_pdf as try_extract_text

# Backwards-compat: bisher wurde in der GUI ``try_extract_text`` importiert.
# Exportiere denselben Namen aus ``pdf_ingest``, damit alte Imports weiterlaufen.
__all__ = ["try_extract_text"]

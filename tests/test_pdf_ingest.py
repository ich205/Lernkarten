import pytest
from app.pdf_ingest import segment_text, extract_text_from_pdf


def test_segment_text_headings_and_blank_lines():
    text = "EINLEITUNG\nDies ist Absatz 1.\n\n\nANHANG\nAbsatz 2."
    segments = segment_text(text, min_len=10, max_len=100)
    assert segments == [
        "EINLEITUNG\nDies ist Absatz 1.",
        "ANHANG\nAbsatz 2.",
    ]


def test_segment_text_heading_optional_filter():
    text = "EINLEITUNG\n\nAbsatz 1.\n\nANHANG\n\nAbsatz 2."
    keep = segment_text(text, min_len=10, max_len=100)
    assert keep == [
        "EINLEITUNG",
        "Absatz 1.",
        "ANHANG",
        "Absatz 2.",
    ]

    filtered = segment_text(text, min_len=10, max_len=100, keep_headings=False)
    assert filtered == [
        "Absatz 1.",
        "Absatz 2.",
    ]


def test_segment_text_respects_min_max_length():
    paragraphs = ["A" * 50, "B" * 50, "C" * 50]
    text = "\n\n".join(paragraphs)
    segments = segment_text(text, min_len=100, max_len=120)
    assert len(segments) == 2
    first, second = segments
    assert 100 <= len(first) <= 120
    assert second == "C" * 50


def test_extract_text_fallback_to_pypdf(monkeypatch, caplog):
    import builtins
    import sys
    import types

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pdfplumber":
            raise ImportError("pdfplumber missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    dummy_pypdf = types.ModuleType("pypdf")
    dummy_errors = types.ModuleType("pypdf.errors")

    class DummyPage:
        def extract_text(self):
            return "dummy"

    class DummyReader:
        def __init__(self, path):
            self.pages = [DummyPage()]

    class PdfReadError(Exception):
        pass

    dummy_pypdf.PdfReader = DummyReader
    dummy_errors.PdfReadError = PdfReadError

    monkeypatch.setitem(sys.modules, "pypdf", dummy_pypdf)
    monkeypatch.setitem(sys.modules, "pypdf.errors", dummy_errors)

    with caplog.at_level("WARNING"):
        text = extract_text_from_pdf("dummy.pdf")

    assert text == "dummy"
    assert any("pdfplumber nicht verfügbar" in r.message for r in caplog.records)


def test_extract_text_no_backend(monkeypatch, caplog):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name in ("pdfplumber", "pypdf"):
            raise ImportError(f"{name} missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with caplog.at_level("WARNING"):
        with pytest.raises(ImportError) as excinfo:
            extract_text_from_pdf("dummy.pdf")

    assert "Weder pdfplumber noch pypdf sind verfügbar" in str(excinfo.value)
    assert any(
        "Weder pdfplumber noch pypdf sind verfügbar" in r.message and r.levelname == "ERROR"
        for r in caplog.records
    )

import pytest
from app.pdf_ingest import segment_text


def test_segment_text_headings_and_blank_lines():
    text = "EINLEITUNG\nDies ist Absatz 1.\n\n\nANHANG\nAbsatz 2."
    segments = segment_text(text, min_len=10, max_len=100)
    assert segments == [
        "EINLEITUNG\nDies ist Absatz 1.",
        "ANHANG\nAbsatz 2.",
    ]


def test_segment_text_respects_min_max_length():
    paragraphs = ["A" * 50, "B" * 50, "C" * 50]
    text = "\n\n".join(paragraphs)
    segments = segment_text(text, min_len=100, max_len=120)
    assert len(segments) == 2
    first, second = segments
    assert 100 <= len(first) <= 120
    assert second == "C" * 50

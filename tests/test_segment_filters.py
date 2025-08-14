from app.segment_filters import is_outline_segment, looks_like_outline_list


def test_is_outline_segment():
    assert is_outline_segment("Inhaltsverzeichnis\n1 Einleitung")
    assert is_outline_segment("Glossar\nBegriff A")
    assert not is_outline_segment("Einleitung\nDies ist Text")


def test_looks_like_outline_list():
    text = "1 Einleitung\n2 Methodik\n3 Ergebnisse\n4 Diskussion"
    assert looks_like_outline_list(text, "Aufzaehlung")
    assert not looks_like_outline_list(text, "Fakt")
    assert not looks_like_outline_list("Nur ein Satz", "Aufzaehlung")

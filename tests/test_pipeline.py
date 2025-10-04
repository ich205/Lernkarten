from pathlib import Path

from app.pipeline import LernkartenPipeline
from app.openai_client import OpenAISettings
from app.config import GPT5_NANO, GPT5_MINI
from app.pipeline_models import Segment, QAItem, CardRow
from app.cache import SegmentCache


def test_estimate_cost():
    settings = OpenAISettings(api_key="test", classify_model=GPT5_NANO, qa_model=GPT5_MINI)
    pipeline = LernkartenPipeline(settings)

    result = pipeline.estimate_cost(
        full_text="abc",
        n_segments=10,
        seg_avg_tokens=200,
        questions_per_chunk=3,
        classify_model=GPT5_NANO,
        qa_model=GPT5_MINI,
    )

    assert result["classification"]["input_tokens"] == 3200
    assert result["classification"]["output_tokens"] == 240
    assert result["classification"]["usd"] == 0.0003
    assert result["qa"]["input_tokens"] == 3800
    assert result["qa"]["output_tokens"] == 6600
    assert result["qa"]["usd"] == 0.0141
    assert result["sum_usd"] == 0.0144


def test_generate_cards_reports_all_segments(monkeypatch):
    settings = OpenAISettings(api_key="test")
    pipeline = LernkartenPipeline(settings)

    monkeypatch.setattr(pipeline.tok, "count", lambda text: 100)
    monkeypatch.setattr(
        pipeline.client,
        "gen_qa_for_chunk",
        lambda text, n_questions, language: [QAItem("f", "a")] * n_questions,
    )

    segments = [
        Segment("eins"),
        Segment("zwei", keep=False),
        Segment("drei"),
    ]
    calls = []

    def progress(i, total, cards):
        calls.append((i, total, cards))

    rows = pipeline.generate_cards(
        segments,
        max_questions_per_chunk=2,
        language="de",
        progress_cb=progress,
    )

    assert [c[0] for c in calls] == [1, 2, 3]
    assert len(calls) == len(segments)
    assert all(isinstance(r, CardRow) for r in rows)


def test_generate_cards_skips_empty_items(monkeypatch):
    settings = OpenAISettings(api_key="test")
    pipeline = LernkartenPipeline(settings)

    monkeypatch.setattr(pipeline.tok, "count", lambda text: 100)
    monkeypatch.setattr(
        pipeline.client,
        "gen_qa_for_chunk",
        lambda text, n_questions, language: [],
    )

    segments = [Segment("eins")]

    rows = pipeline.generate_cards(
        segments,
        max_questions_per_chunk=2,
        language="de",
    )

    assert rows == []


def test_generate_cards_scales_with_budget(monkeypatch):
    settings = OpenAISettings(api_key="test")
    pipeline = LernkartenPipeline(settings)

    # Simuliere lange Segmente, sodass viele Fragen moeglich waeren
    monkeypatch.setattr(pipeline.tok, "count", lambda text: 1500)

    called_with: list[int] = []

    def fake_gen(text, n_questions, language):
        called_with.append(n_questions)
        return [QAItem("f", "a")] * n_questions

    monkeypatch.setattr(pipeline.client, "gen_qa_for_chunk", fake_gen)

    # Kostenschaetzung fixieren
    monkeypatch.setattr(
        pipeline,
        "estimate_cost",
        lambda *args, **kwargs: {"sum_usd": 5},
    )

    segments = [Segment("eins"), Segment("zwei")]
    adjusted: list[int] = []

    pipeline.generate_cards(
        segments,
        max_questions_per_chunk=10,
        language="de",
        budget_usd=2.0,
        limit_by_budget=True,
        adjust_cb=lambda v: adjusted.append(v),
    )

    assert called_with == [4, 4]
    assert adjusted == [4]


def test_generate_cards_uses_cache(tmp_path, monkeypatch):
    import app.cache as cache_module

    def fake_cache_dir(*parts: str):
        path = tmp_path
        for part in parts:
            path = path / part
        path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr(cache_module, "cache_dir", fake_cache_dir)

    cache = SegmentCache("qa_cache_test", enabled=True)
    settings = OpenAISettings(api_key="test")
    pipeline = LernkartenPipeline(settings, cache=cache)

    monkeypatch.setattr(pipeline.tok, "count", lambda text: 200)
    call_count = {"n": 0}

    def fake_gen(text, n_questions, language):
        call_count["n"] += 1
        return [QAItem("frage", "antwort")]

    monkeypatch.setattr(pipeline.client, "gen_qa_for_chunk", fake_gen)

    segments = [Segment("eins"), Segment("zwei")]

    pipeline.generate_cards(
        segments,
        max_questions_per_chunk=1,
        language="de",
        max_workers=1,
    )
    pipeline.generate_cards(
        segments,
        max_questions_per_chunk=1,
        language="de",
        max_workers=1,
    )

    assert call_count["n"] == 1


def test_run_pipeline_creates_export(tmp_path, monkeypatch):
    settings = OpenAISettings(api_key="test")
    pipeline = LernkartenPipeline(settings, cache_enabled=False)

    segments = [Segment("eins")]
    monkeypatch.setattr(pipeline, "load_and_segment", lambda path: segments)
    monkeypatch.setattr(pipeline, "classify", lambda segs, **kwargs: segs)

    captured = {}

    def fake_generate(segs, *args, **kwargs):
        captured["limit"] = kwargs.get("limit_by_budget")
        captured["budget"] = kwargs.get("budget_usd")
        return [CardRow(original=s.text, fragen=["f"], antworten=["a"], labels=[]) for s in segs]

    monkeypatch.setattr(pipeline, "generate_cards", fake_generate)

    exported: list[str] = []

    def fake_export(rows, out_path):
        exported.append(out_path)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text("ok", encoding="utf-8")

    monkeypatch.setattr(pipeline, "export_excel", fake_export)

    progress_calls: list[tuple[str, int, int]] = []

    states: list[dict] = []

    result = pipeline.run(
        "dummy.pdf",
        out_dir=str(tmp_path),
        max_questions_per_chunk=3,
        language="de",
        budget_usd=5.0,
        limit_by_budget=True,
        progress_cb=lambda phase, current, total, cards: progress_calls.append((phase, current, total)),
        status_cb=lambda msg: None,
        log_cb=lambda msg: None,
        agent_state_cb=lambda info: states.append(info.copy()),
    )

    assert exported
    assert Path(result).exists()
    assert captured["limit"] is True
    assert captured["budget"] == 5.0
    assert any(phase == "generate" for phase, _, _ in progress_calls)
    agent_names = {entry["agent"] for entry in states if "agent" in entry}
    assert {"segment", "classify", "qa", "export"}.issubset(agent_names)
    assert any(entry.get("status") == "active" for entry in states)

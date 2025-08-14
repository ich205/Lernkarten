from app.pipeline import LernkartenPipeline
from app.openai_client import OpenAISettings
from app.config import GPT5_NANO, GPT5_MINI
from app.pipeline_models import Segment, QAItem, CardRow


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

from app.pipeline import LernkartenPipeline
from app.openai_client import OpenAISettings
from app.config import GPT5_NANO, GPT5_MINI


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

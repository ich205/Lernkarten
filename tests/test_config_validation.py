import pytest

from app.config import validate_config


def _valid_cfg():
    return {
        "models": {"qa_model": "gpt-5-mini", "label_model": "gpt-5-nano"},
        "costs": {
            "gpt-5-mini_input_usd_per_mtok": 0,
            "gpt-5-mini_cached_input_usd_per_mtok": 0,
            "gpt-5-mini_output_usd_per_mtok": 0,
            "gpt-5-nano_input_usd_per_mtok": 0,
            "gpt-5-nano_cached_input_usd_per_mtok": 0,
            "gpt-5-nano_output_usd_per_mtok": 0,
        },
        "chunking": {},
        "ui": {},
    }


def test_validate_config_accepts_valid():
    validate_config(_valid_cfg())


def test_missing_section_raises():
    cfg = _valid_cfg()
    cfg.pop("models")
    with pytest.raises(ValueError, match=r"\[models\] fehlt"):
        validate_config(cfg)


def test_missing_price_raises():
    cfg = _valid_cfg()
    cfg["costs"].pop("gpt-5-mini_input_usd_per_mtok")
    with pytest.raises(ValueError, match="costs.gpt-5-mini_input_usd_per_mtok"):
        validate_config(cfg)


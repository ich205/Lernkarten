from app.config import load_api_key

def test_env_precedence(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "envkey")
    cfg = {"auth": {"api_key": "cfgkey"}}
    key, source = load_api_key(cfg)
    assert key == "envkey"
    assert source == "env"


def test_config_key_warning(caplog):
    cfg = {"auth": {"api_key": "cfgkey"}}
    caplog.set_level("WARNING")
    key, source = load_api_key(cfg)
    assert key == "cfgkey"
    assert source == "config"
    assert any("config.toml" in r.message for r in caplog.records)


def test_file_key_warning(tmp_path, caplog):
    fp = tmp_path / "key.txt"
    fp.write_text("filekey", encoding="utf-8")
    cfg = {"auth": {"api_key_file": str(fp)}}
    caplog.set_level("WARNING")
    key, source = load_api_key(cfg)
    assert key == "filekey"
    assert source == "file"
    assert any("file" in r.message for r in caplog.records)

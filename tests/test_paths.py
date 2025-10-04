import app.paths as paths


def test_state_dir_creates_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_home", lambda: tmp_path)
    monkeypatch.setattr(paths.platform, "system", lambda: "Linux")

    directory = paths.state_dir("unit-test")

    expected = tmp_path / ".local" / "share" / paths.APP_NAME / "unit-test"
    assert directory == expected
    assert directory.exists()


def test_cache_dir_creates_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_home", lambda: tmp_path)
    monkeypatch.setattr(paths.platform, "system", lambda: "Linux")

    directory = paths.cache_dir("segments")

    expected = tmp_path / ".cache" / paths.APP_NAME / "segments"
    assert directory == expected
    assert directory.exists()


def test_log_dir_uses_state_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_home", lambda: tmp_path)
    monkeypatch.setattr(paths.platform, "system", lambda: "Linux")

    directory = paths.log_dir()

    expected = tmp_path / ".local" / "share" / paths.APP_NAME / "logs"
    assert directory == expected
    assert directory.exists()

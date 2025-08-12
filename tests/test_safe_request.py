import app.openai_client as oc


def test_safe_request_retries(monkeypatch):
    sleeps = []
    monkeypatch.setattr(oc.time, "sleep", lambda s: sleeps.append(s))

    class DummyError(oc.OpenAIError):
        status_code = 429
        retry_after = 2

    calls = {"count": 0}

    def flaky(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise DummyError("fail")
        return "ok"

    result = oc.safe_request(flaky)
    assert result == "ok"
    assert sleeps == [2]

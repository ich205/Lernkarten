import app.openai_client as oc


def test_retry_request_uses_jitter(monkeypatch):
    sleep_calls = []

    monkeypatch.setattr(oc, "sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(oc.random, "uniform", lambda a, b: 0.5)

    attempts = {"count": 0}

    def flaky():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise oc.OpenAIError("fail")
        return "ok"

    result = oc.retry_request(flaky, n=2, delay=1, backoff=2)
    assert result == "ok"
    assert sleep_calls == [0.5]

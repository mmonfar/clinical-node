"""R1: a reply cut at max_tokens (repeat loop) must not be retried with the identical call."""
import json
from types import SimpleNamespace

from debate import eval as E


def _resp(text, reason):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason=reason)])


def test_retry_changes_seed_and_adds_repeat_penalty(monkeypatch):
    import importlib
    llm = importlib.import_module('adapters.llm')
    calls = []

    def fake_complete(**kw):
        calls.append(kw)
        return _resp('{"a": "unterminated', "length") if len(calls) == 1 else _resp(json.dumps({"x": 1}), "stop")
    monkeypatch.setattr(llm, "complete", fake_complete)
    call = E.llm_model("m:1b", "proposer", 42, 0.0)
    req = {"role": "proposer", "round": 1, "case_text": "synthetic", "evidence": [], "claims": [], "objections": [],
           "proposer_turn": None, "retry_errors": []}
    try:
        call(req)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "cut at max_tokens" in str(exc)
    call(dict(req, retry_errors=["x"]))
    first, second = calls
    assert "repeat_penalty" not in first and first["seed"] == 42 and first["temperature"] == 0.0
    assert second["seed"] != 42 and second["repeat_penalty"] > 1 and second["temperature"] > 0


def test_adapter_passes_repeat_penalty_and_length(monkeypatch):
    import importlib
    llm = importlib.import_module('adapters.llm')
    seen = {}

    def fake_http(path, payload, *a, **k):
        seen.update(payload)
        return {"model": "m", "message": {"content": "{"}, "done_reason": "length"}
    monkeypatch.setattr(llm, "_http_json", fake_http)
    monkeypatch.setattr(llm, "ollama_digest", lambda m: "d")
    r = llm.complete(backend="ollama", model="m", messages=[], repeat_penalty=1.3)
    assert seen["options"]["repeat_penalty"] == 1.3
    assert r.choices[0].finish_reason == "length"

"""
Tests for the append-only run log in adapters/llm.complete().

No network, no API key: a fake client stands in for OpenAI, and the log is
redirected to tmp_path. The case text used here is synthetic.
"""

import json

import pytest

from adapters import llm

SYNTHETIC_CASE = "Synthetic test patient: 70-year-old with fictional fracture."


def _install_fake(monkeypatch, response=None, raises=None):
    class FakeCompletions:
        def create(self, **kwargs):
            if raises:
                raise raises
            return response

    class FakeClient:
        def __init__(self, api_key=None, timeout=None):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(llm, "OpenAI", FakeClient)
    llm.reset_client()


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    path = tmp_path / "runs.jsonl"
    monkeypatch.setenv("CLINICAL_NODE_RUN_LOG", str(path))
    yield path
    llm.reset_client()


def _call():
    return llm.complete(
        model="gpt-4o-mini",
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": SYNTHETIC_CASE}],
    )


def test_complete_appends_metadata_record(monkeypatch, log_path):
    fake = {
        "model": "gpt-4o-mini-2024-07-18",
        "usage": {"prompt_tokens": 12, "completion_tokens": 3},
        "choices": [{"message": {"content": "{}"}}],
    }
    _install_fake(monkeypatch, response=fake)

    assert _call() is fake  # response passes through untouched

    (line,) = log_path.read_text(encoding="utf-8").splitlines()
    rec = json.loads(line)
    assert rec["model_requested"] == "gpt-4o-mini"
    assert rec["model_returned"] == "gpt-4o-mini-2024-07-18"
    assert rec["params"] == {"temperature": 0.0, "response_format": {"type": "json_object"}}
    assert rec["prompt_tokens"] == 12 and rec["completion_tokens"] == 3
    assert rec["ok"] is True and rec["error"] is None
    assert len(rec["prompt_sha256"]) == 64
    assert rec["latency_ms"] >= 0


def test_log_holds_no_prompt_text(monkeypatch, log_path):
    _install_fake(monkeypatch, response={"model": "m", "choices": []})
    _call()
    raw = log_path.read_text(encoding="utf-8")
    assert "fracture" not in raw and "Synthetic" not in raw
    assert "messages" not in json.loads(raw)


def test_log_is_append_only_and_hash_is_stable(monkeypatch, log_path):
    _install_fake(monkeypatch, response={"model": "m", "choices": []})
    _call()
    _call()
    lines = [json.loads(x) for x in log_path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert lines[0]["prompt_sha256"] == lines[1]["prompt_sha256"]


def test_failed_call_is_logged_then_reraised(monkeypatch, log_path):
    _install_fake(monkeypatch, raises=TimeoutError("synthetic timeout"))
    with pytest.raises(TimeoutError):
        _call()
    rec = json.loads(log_path.read_text(encoding="utf-8"))
    assert rec["ok"] is False and rec["error"] == "TimeoutError"


def test_unwritable_log_does_not_break_the_call(monkeypatch, tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("CLINICAL_NODE_RUN_LOG", str(blocker / "runs.jsonl"))
    fake = {"model": "m", "choices": []}
    _install_fake(monkeypatch, response=fake)
    assert _call() is fake
    llm.reset_client()

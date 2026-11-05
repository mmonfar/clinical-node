"""Ollama backend of adapters.llm.complete(). HTTP is mocked; synthetic text only."""
import json

import pytest

from adapters import llm

SYNTHETIC = "Synthetic test patient: fictional 60-year-old with cough."


class _Resp:
    def __init__(self, obj):
        self._b = json.dumps(obj).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def sent(monkeypatch, tmp_path):
    monkeypatch.setenv("CLINICAL_NODE_RUN_LOG", str(tmp_path / "r.jsonl"))
    calls = []

    def fake_urlopen(req, timeout=None):
        body = json.loads(req.data) if req.data else None
        calls.append((req.full_url, body))
        if req.full_url.endswith("/api/tags"):
            return _Resp({"models": [{"name": "m:1b", "model": "m:1b", "digest": "abc123"}]})
        return _Resp({"model": "m:1b", "message": {"content": '{"ok": true}'},
                      "prompt_eval_count": 7, "eval_count": 3})

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    return calls


def _call(**extra):
    return llm.complete(backend="ollama", model="m:1b", temperature=0.0, seed=42,
                        max_tokens=50, messages=[{"role": "user", "content": SYNTHETIC}], **extra)


def test_response_shape_and_payload(sent):
    r = _call(response_format={"type": "json_schema", "schema": {"type": "object"}}, think=False)
    assert r.choices[0].message.content == '{"ok": true}'
    assert r.usage.prompt_tokens == 7 and r.usage.completion_tokens == 3
    url, body = sent[-1]
    assert url == "http://localhost:11434/api/chat"
    assert body["stream"] is False and body["think"] is False
    assert body["options"] == {"temperature": 0.0, "seed": 42, "num_predict": 50}
    assert body["format"] == {"type": "object"}


def test_log_has_digest_seed_no_prompt_text(sent, tmp_path):
    _call()
    text = (tmp_path / "r.jsonl").read_text(encoding="utf-8")
    rec = json.loads(text.strip().splitlines()[-1])
    assert rec["backend"] == "ollama" and rec["model_digest"] == "abc123"
    assert rec["params"]["seed"] == 42 and rec["params"]["temperature"] == 0.0
    assert rec["params"]["max_tokens"] == 50 and rec["ok"] is True
    assert SYNTHETIC not in text and len(rec["prompt_sha256"]) == 64


def test_error_is_logged_and_raised(monkeypatch, tmp_path):
    monkeypatch.setenv("CLINICAL_NODE_RUN_LOG", str(tmp_path / "r.jsonl"))

    def boom(req, timeout=None):
        raise OSError("down")

    monkeypatch.setattr(llm.urllib.request, "urlopen", boom)
    with pytest.raises(OSError):
        _call()
    rec = json.loads((tmp_path / "r.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert rec["ok"] is False and rec["error"] == "OSError" and rec["model_digest"] is None


def test_running_check(monkeypatch):
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda r, timeout=None: _Resp({"models": []}))
    assert llm.ollama_running() is True

    def boom(r, timeout=None):
        raise OSError

    monkeypatch.setattr(llm.urllib.request, "urlopen", boom)
    assert llm.ollama_running() is False


def test_unknown_backend():
    with pytest.raises(ValueError):
        llm.complete(backend="nope", model="x", messages=[])

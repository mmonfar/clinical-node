"""
Tests for adapters/llm.py (local Ollama only). No network, no API key:
a fake model stands in for Ollama. Synthetic text only.
"""

import importlib
import json
import sys

import pytest

from adapters import llm

SYNTHETIC = "Synthetic test patient: fictional 60-year-old with cough."
INSTALLED = {"medgemma:4b", "qwen3:4b", "qwen3:8b", "qwen2.5:7b", "gemma4:12b",
             "gpt-oss:20b", "granite4.2:8b", "hermes3:latest"}
SBAR = {"situation": "s", "background": "b", "assessment": "a", "recommendation": "r"}


class FakeModel:
    """Records every call and answers with fixed JSON. Replaces llm._http_json."""

    def __init__(self):
        self.calls = []

    def __call__(self, path, payload=None, timeout=0):
        if path == "/api/tags":
            return {"models": []}
        self.calls.append(payload)
        return {"model": payload["model"], "message": {"content": json.dumps(SBAR)},
                "prompt_eval_count": 1, "eval_count": 1}


@pytest.fixture
def fake(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CLINICAL_NODE_RUN_LOG", str(tmp_path / "r.jsonl"))
    f = FakeModel()
    monkeypatch.setattr(llm, "_http_json", f)
    return f


def test_import_modules_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    for name in ("clinical_engine", "cron_refine"):
        sys.modules.pop(name, None)
        assert importlib.import_module(name) is not None


def test_no_cloud_client_in_adapter():
    assert not hasattr(llm, "OpenAI") and not hasattr(llm, "get_client")


def test_default_backend_is_ollama(fake):
    llm.complete(model="qwen3:8b", messages=[{"role": "user", "content": SYNTHETIC}])
    assert fake.calls and fake.calls[0]["model"] == "qwen3:8b"


def test_unknown_backend_refused(fake):
    with pytest.raises(ValueError):
        llm.complete(backend="openai", model="x", messages=[])
    assert fake.calls == []


def test_every_agent_model_is_installed():
    assert set(llm.AGENT_MODELS) >= {"sbar", "researcher", "mdt", "auditor", "refine"}
    for cfg in llm.AGENT_MODELS.values():
        assert cfg["model"] in INSTALLED


def test_engine_agents_use_their_configured_model(fake, monkeypatch):
    import clinical_engine as ce
    monkeypatch.setattr(llm, "AGENT_MODELS", {
        "sbar": {"model": "m-sbar"}, "researcher": {"model": "m-res"},
        "mdt": {"model": "m-mdt"}, "auditor": {"model": "m-aud"},
        "refine": {"model": "m-ref"}})
    ce.parse_sbar_from_text(SYNTHETIC)
    assert fake.calls[-1]["model"] == "m-sbar"
    ce.build_pubmed_query(SBAR)
    assert fake.calls[-1]["model"] == "m-res"

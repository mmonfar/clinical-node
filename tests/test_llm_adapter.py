"""
Tests for the Tier-3 fix: adapters/llm.py.

No network, no API key. Covers:
- importing the engine modules with OPENAI_API_KEY unset (the bug the
  architecture audit found: the old module-level ``OpenAI(api_key=...)``
  raised KeyError at import time);
- that complete() passes the configured timeout to the OpenAI client,
  using a fake client instead of a real network call.
"""

import importlib
import os
import sys

import pytest


@pytest.fixture(autouse=True)
def _clean_key(monkeypatch):
    """Ensure OPENAI_API_KEY is unset unless a test opts in."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    yield


def test_import_clinical_engine_without_api_key():
    """Importing the engine must not require OPENAI_API_KEY to be set."""
    sys.modules.pop("clinical_engine", None)
    sys.modules.pop("adapters.llm", None)
    module = importlib.import_module("clinical_engine")
    assert module is not None


def test_import_cron_refine_without_api_key():
    """Same fix, second call site module."""
    sys.modules.pop("cron_refine", None)
    sys.modules.pop("adapters.llm", None)
    module = importlib.import_module("cron_refine")
    assert module is not None


def test_import_adapters_llm_without_api_key():
    """adapters.llm itself must be importable with no key set (lazy client)."""
    sys.modules.pop("adapters.llm", None)
    module = importlib.import_module("adapters.llm")
    assert module.get_client is not None


def test_get_client_raises_only_when_actually_used(monkeypatch):
    """The KeyError the audit found should now surface only on first use,
    not at import time -- and only when the key really is missing."""
    from adapters import llm

    llm.reset_client()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(KeyError):
        llm.get_client()


def test_complete_passes_configured_timeout_to_client(monkeypatch):
    """complete() must route through a client built with DEFAULT_TIMEOUT."""
    from adapters import llm

    llm.reset_client()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")

    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured["create_kwargs"] = kwargs
            return {"choices": [{"message": {"content": "{}"}}]}

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self, api_key=None, timeout=None):
            captured["api_key"] = api_key
            captured["timeout"] = timeout
            self.chat = FakeChat()

    monkeypatch.setattr(llm, "OpenAI", FakeClient)
    llm.reset_client()

    result = llm.complete(model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}])

    assert captured["timeout"] == llm.DEFAULT_TIMEOUT
    assert captured["api_key"] == "test-key-not-real"
    assert captured["create_kwargs"]["model"] == "gpt-4o-mini"
    assert result == {"choices": [{"message": {"content": "{}"}}]}

    llm.reset_client()


def test_client_is_constructed_only_once(monkeypatch):
    """The client should be built lazily but cached across calls."""
    from adapters import llm

    llm.reset_client()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")

    build_count = {"n": 0}

    class FakeClient:
        def __init__(self, api_key=None, timeout=None):
            build_count["n"] += 1

    monkeypatch.setattr(llm, "OpenAI", FakeClient)
    llm.reset_client()

    llm.get_client()
    llm.get_client()
    llm.get_client()

    assert build_count["n"] == 1
    llm.reset_client()

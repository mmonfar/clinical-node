"""
adapters/llm.py
----------------
Single place that owns the OpenAI client for the Clinical Intelligence Node.

Tier-3 fix (architecture audit): both ``clinical_engine.py`` and
``cron_refine.py`` used to build their own module-level
``OpenAI(api_key=os.environ["OPENAI_API_KEY"])`` at import time. That meant
importing either module — including for unit tests — raised ``KeyError``
whenever ``OPENAI_API_KEY`` was not set, and each of the 7 call sites across
the two modules configured its own (mostly absent) request timeout.

This module fixes both problems without changing any behaviour:

- the client is created lazily, on first use, so importing modules that call
  ``complete()`` no longer requires the API key to be set;
- the client is created exactly once, with one explicit timeout, and every
  call site goes through the single ``complete()`` helper below.

Prompts, models and parameters are untouched — ``complete(**kwargs)`` passes
everything straight through to ``client.chat.completions.create``.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from openai import OpenAI

# Applies to every chat-completion call made through complete(). Previously
# at most one call site set a timeout; the rest had none.
DEFAULT_TIMEOUT = 60.0  # seconds

_client: OpenAI | None = None

# Append-only audit log of every complete() call (see docs/GOVERNANCE.md).
# One JSON object per line. It holds metadata only: a SHA-256 of the
# messages, never the prompt or output text, so no case content lands here.
# Override the path with CLINICAL_NODE_RUN_LOG (tests point it at tmp_path).
DEFAULT_RUN_LOG = Path(__file__).resolve().parent.parent / "logs" / "llm_runs.jsonl"

# Request parameters worth recording for reproducibility. Anything else
# (notably ``messages``) is left out of the log on purpose.
_LOGGED_PARAMS = ("temperature", "max_tokens", "seed", "top_p", "response_format")

# Local Ollama backend (debate engine, SPEC section 5). Plain HTTP, stdlib only.
# Override the address with OLLAMA_HOST_URL. Local only.
OLLAMA_URL = "http://localhost:11434"
OLLAMA_TIMEOUT = 600.0  # seconds; local models on a laptop can be slow


def get_client() -> OpenAI:
    """Return the shared OpenAI client, constructing it on first use.

    Deferred construction is the point: a module that only calls this
    function inside a function body (never at import time) can be imported
    with no ``OPENAI_API_KEY`` set at all — required for unit-testing the
    engine without a key or network access.
    """
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            timeout=DEFAULT_TIMEOUT,
        )
    return _client


def complete(**kwargs: Any) -> Any:
    """Run a chat completion through the shared, timeout-bound client.

    Every call site in this repo should route through here instead of
    calling ``OpenAI(...).chat.completions.create(...)`` directly. All
    keyword arguments (model, temperature, messages, response_format, ...)
    are forwarded unchanged. Each call also appends one metadata record
    to the run log (``run_log_path()``); the response is returned as-is.

    Default backend is OpenAI, unchanged. Pass ``backend="ollama"`` to use
    the local Ollama server (see ``_ollama_complete``).
    """
    backend = kwargs.pop("backend", "openai")
    if backend == "ollama":
        return _ollama_complete(kwargs)
    if backend != "openai":
        raise ValueError(f"unknown backend: {backend!r}")
    started = time.perf_counter()
    try:
        response = get_client().chat.completions.create(**kwargs)
    except Exception as exc:
        _log_run(kwargs, started, response=None, error=type(exc).__name__)
        raise
    _log_run(kwargs, started, response=response, error=None)
    return response


def _ollama_url() -> str:
    return (os.environ.get("OLLAMA_HOST_URL") or OLLAMA_URL).rstrip("/")


def _http_json(path: str, payload: dict | None = None, timeout: float = OLLAMA_TIMEOUT) -> dict:
    """GET (no payload) or POST JSON to the local Ollama server."""
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _ollama_url() + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if data is None else "POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ollama_digest(model: str) -> str | None:
    """Model digest from /api/tags (the tag alone can change). None if unknown."""
    try:
        for entry in _http_json("/api/tags", timeout=10.0).get("models", []):
            if model in (entry.get("name"), entry.get("model")):
                return entry.get("digest")
    except Exception:
        return None
    return None


def ollama_running() -> bool:
    """True if the local Ollama server answers. Never starts it."""
    try:
        _http_json("/api/tags", timeout=3.0)
        return True
    except Exception:
        return False


def _ollama_complete(kwargs: dict) -> Any:
    """Chat call to Ollama, returned in the OpenAI response shape.

    Maps: temperature, seed, top_p -> options; max_tokens -> num_predict;
    num_ctx -> options; response_format {"type":"json_schema","schema":S}
    or {"type":"json_object"} -> Ollama ``format``; ``think`` passed as given.
    """
    started = time.perf_counter()
    options = {}
    for key in ("temperature", "seed", "top_p", "repeat_penalty"):
        if key in kwargs:
            options[key] = kwargs[key]
    if "max_tokens" in kwargs:
        options["num_predict"] = kwargs["max_tokens"]
    if "num_ctx" in kwargs:
        options["num_ctx"] = kwargs["num_ctx"]
    payload = {
        "model": kwargs.get("model"),
        "messages": kwargs.get("messages"),
        "stream": False,
        "options": options,
    }
    if "think" in kwargs:
        payload["think"] = kwargs["think"]
    rf = kwargs.get("response_format")
    if isinstance(rf, dict):
        if rf.get("type") == "json_schema":
            payload["format"] = rf.get("schema")
        elif rf.get("type") == "json_object":
            payload["format"] = "json"
    digest = ollama_digest(kwargs.get("model"))
    extra = {"backend": "ollama", "model_digest": digest}
    try:
        raw = _http_json("/api/chat", payload)
    except Exception as exc:
        _log_run(kwargs, started, response=None, error=type(exc).__name__, extra=extra)
        raise
    msg = raw.get("message") or {}
    response = SimpleNamespace(
        model=raw.get("model"),
        choices=[SimpleNamespace(message=SimpleNamespace(
            role="assistant", content=msg.get("content", "")),
            finish_reason="length" if raw.get("done_reason") == "length" else "stop")],
        usage=SimpleNamespace(prompt_tokens=raw.get("prompt_eval_count"),
                              completion_tokens=raw.get("eval_count")),
    )
    _log_run(kwargs, started, response=response, error=None, extra=extra)
    return response


def run_log_path() -> Path:
    """Where complete() appends its audit records."""
    return Path(os.environ.get("CLINICAL_NODE_RUN_LOG") or DEFAULT_RUN_LOG)


def _prompt_hash(messages: Any) -> str:
    payload = json.dumps(messages, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _field(obj: Any, name: str) -> Any:
    """Read ``name`` from an SDK object or a plain dict (fakes in tests)."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _log_run(kwargs: dict, started: float, response: Any, error: str | None,
             extra: dict | None = None) -> None:
    """Append one metadata record. Never raises: logging must not break a run."""
    usage = _field(response, "usage") if response is not None else None
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "model_requested": kwargs.get("model"),
        "model_returned": _field(response, "model") if response is not None else None,
        "params": {k: kwargs[k] for k in _LOGGED_PARAMS if k in kwargs},
        "prompt_sha256": _prompt_hash(kwargs.get("messages")),
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "prompt_tokens": _field(usage, "prompt_tokens") if usage is not None else None,
        "completion_tokens": _field(usage, "completion_tokens") if usage is not None else None,
        "ok": error is None,
        "error": error,
    }
    if extra:
        record.update(extra)
    try:
        path = run_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
    except OSError:
        pass


def reset_client() -> None:
    """Drop the cached client so the next call() rebuilds it. Tests only."""
    global _client
    _client = None

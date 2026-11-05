"""
adapters/llm.py
----------------
Single place for every model call in the Clinical Intelligence Node.

All calls go to a local Ollama server on this machine. Nothing is sent to a
cloud service and no API key is needed. Importing this module never needs a
key, a network or a running server.

Which model each agent uses is set in ONE place: ``AGENT_MODELS`` below. Use
only models that are already installed (see docs/MODELS.md). The code never
pulls a model.
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

# Append-only audit log of every complete() call (see docs/GOVERNANCE.md).
# One JSON object per line. It holds metadata only: a SHA-256 of the
# messages, never the prompt or output text, so no case content lands here.
# Override the path with CLINICAL_NODE_RUN_LOG (tests point it at tmp_path).
DEFAULT_RUN_LOG = Path(__file__).resolve().parent.parent / "logs" / "llm_runs.jsonl"

# Request parameters worth recording for reproducibility. Anything else
# (notably ``messages``) is left out of the log on purpose.
_LOGGED_PARAMS = ("temperature", "max_tokens", "seed", "top_p", "response_format")

# One config dict: the model for each agent. Installed models only (docs/MODELS.md).
# "think": False turns off Qwen3 thinking mode so the answer is plain text/JSON.
AGENT_MODELS = {
    "sbar":       {"model": "qwen3:8b",   "think": False},  # SBAR step
    "researcher": {"model": "qwen3:8b",   "think": False},  # Researcher
    "mdt":        {"model": "gemma4:12b"},                  # MDT Roundtable
    "auditor":    {"model": "qwen3:8b",   "think": False},  # Auditor
    "refine":     {"model": "gemma4:12b"},                  # 72-hour contradiction check
}


def agent_kwargs(agent: str) -> dict:
    """Model settings for one agent, from AGENT_MODELS. Unknown agent = KeyError."""
    return dict(AGENT_MODELS[agent])


def agent_label(agent: str) -> str:
    """Model name for author lines in the minutes."""
    return AGENT_MODELS[agent]["model"]


# Local Ollama backend (debate engine, SPEC section 5). Plain HTTP, stdlib only.
# Override the address with OLLAMA_HOST_URL. Local only.
OLLAMA_URL = "http://localhost:11434"
OLLAMA_TIMEOUT = 600.0  # seconds; local models on a laptop can be slow


def complete(**kwargs: Any) -> Any:
    """Run a chat completion on the local Ollama server.

    Keyword arguments: model, messages, temperature, seed, max_tokens,
    response_format, think. Each call appends one metadata record to the run
    log (``run_log_path()``). The answer comes back in the chat-completion
    shape: ``response.choices[0].message.content``.
    """
    backend = kwargs.pop("backend", "ollama")
    if backend != "ollama":
        raise ValueError(f"unknown backend: {backend!r} (only 'ollama' is supported)")
    return _ollama_complete(kwargs)


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
    """Chat call to Ollama, returned in the chat-completion response shape.

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
    if kwargs.get("think") is not None:
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
    """Read ``name`` from an object or a plain dict (fakes in tests)."""
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

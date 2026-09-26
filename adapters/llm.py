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

import os
from typing import Any

from openai import OpenAI

# Applies to every chat-completion call made through complete(). Previously
# at most one call site set a timeout; the rest had none.
DEFAULT_TIMEOUT = 60.0  # seconds

_client: OpenAI | None = None


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
    are forwarded unchanged.
    """
    return get_client().chat.completions.create(**kwargs)


def reset_client() -> None:
    """Drop the cached client so the next call() rebuilds it. Tests only."""
    global _client
    _client = None

"""
Escaping test for app.py's _e() helper (security audit item, kept intact by
this brand-adoption + Tier-3 change: model/PubMed text must never reach
unsafe_allow_html markup unescaped).

No network, no API key -- app.py itself talks to no external service at
import time; it only builds Streamlit page config and CSS.
"""

import importlib
import os
import sys

import pytest


@pytest.fixture(autouse=True)
def _clean_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    yield


def _import_app():
    sys.modules.pop("app", None)
    return importlib.import_module("app")


def test_e_escapes_hostile_img_onerror():
    app = _import_app()
    hostile = '<img src=x onerror=alert(1)>'
    escaped = app._e(hostile)

    assert "<img" not in escaped
    assert "onerror=" not in escaped or "&lt;" in escaped
    assert "<" not in escaped
    assert ">" not in escaped
    assert escaped == "&lt;img src=x onerror=alert(1)&gt;"


def test_e_escapes_quotes_too():
    app = _import_app()
    hostile = '"><script>alert(1)</script>'
    escaped = app._e(hostile)

    assert "<script>" not in escaped
    assert "&quot;" in escaped or "&#x27;" in escaped or "&#34;" in escaped

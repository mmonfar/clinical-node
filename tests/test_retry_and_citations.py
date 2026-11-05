"""Retry after a repeat-loop or bad-JSON reply, and the code check on citations. Fake models only."""
import io
import json
import urllib.error
from types import SimpleNamespace

import pytest

import clinical_engine as ce
import cron_refine
from adapters import citations, llm


def _resp(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason="stop")])


def _http500():
    return urllib.error.HTTPError("http://x", 500, "repeat limit", {}, io.BytesIO(b""))


SBAR = {"situation": "s", "background": "b", "assessment": "a", "recommendation": "r"}


# ---- 1. Researcher: HTTP 500 retry, then fallback that records itself ----

def test_retry_after_500_uses_new_seed_and_repeat_penalty(monkeypatch):
    calls = []

    def fake(**kw):
        calls.append(kw)
        if len(calls) == 1:
            raise _http500()
        return _resp("ok")
    monkeypatch.setattr(llm, "complete", fake)
    resp, _, retried = llm.complete_retry(model="m", seed=7, temperature=0.0, messages=[])
    assert retried and resp.choices[0].message.content == "ok"
    assert calls[1]["seed"] != 7 and calls[1]["repeat_penalty"] > 1 and calls[1]["temperature"] > 0


def test_500_twice_is_raised_after_exactly_two_calls(monkeypatch):
    calls = []

    def fake(**kw):
        calls.append(kw)
        raise _http500()
    monkeypatch.setattr(llm, "complete", fake)
    with pytest.raises(urllib.error.HTTPError):
        llm.complete_retry(model="m", messages=[])
    assert len(calls) == 2


def test_other_errors_are_not_retried(monkeypatch):
    calls = []

    def fake(**kw):
        calls.append(kw)
        raise ConnectionRefusedError("down")
    monkeypatch.setattr(llm, "complete", fake)
    with pytest.raises(ConnectionRefusedError):
        llm.complete_retry(model="m", messages=[])
    assert len(calls) == 1


def test_researcher_falls_back_and_records_it(monkeypatch):
    def fake(**kw):
        raise _http500()
    monkeypatch.setattr(llm, "complete", fake)
    monkeypatch.setattr(ce.pubmed_client, "search_clinical_evidence", lambda q, max_results=0: [])
    monkeypatch.setattr(ce.pubmed_client, "search_mid_tier_evidence", lambda q, max_results=0: [])
    monkeypatch.setattr(ce.pubmed_client, "search_case_studies", lambda q, max_results=0: [])
    out = ce.researcher_search("q", sbar=SBAR)
    assert out["articles"] == []
    assert "failed after one retry" in out["fallback"]


def test_researcher_no_fallback_note_when_planning_works(monkeypatch):
    monkeypatch.setattr(ce.pubmed_client, "search_clinical_evidence", lambda q, max_results=0: [])
    monkeypatch.setattr(ce, "_multi_pillar_search", lambda q, s: {"articles": [], "is_multi_pillar": True})
    assert "fallback" not in ce.researcher_search("q", sbar=SBAR)


# ---- 2. Bad JSON: one repair retry, then fail clearly ----

def test_bad_json_gets_one_repair_retry(monkeypatch):
    calls = []

    def fake(**kw):
        calls.append(kw)
        return _resp("{broken" if len(calls) == 1 else json.dumps({"a": 1}))
    monkeypatch.setattr(llm, "complete", fake)
    _, parsed, retried = llm.complete_retry(parse_json=True, model="m", messages=[{"role": "user", "content": "x"}])
    assert parsed == {"a": 1} and retried
    assert "valid JSON" in calls[1]["messages"][-1]["content"]
    assert len(calls[0]["messages"]) == 1


def test_bad_json_twice_fails_clearly(monkeypatch):
    calls = []

    def fake(**kw):
        calls.append(kw)
        return _resp("{broken")
    monkeypatch.setattr(llm, "complete", fake)
    with pytest.raises(ValueError, match="not valid JSON"):
        llm.complete_retry(parse_json=True, model="m", messages=[])
    assert len(calls) == 2


def test_72h_check_repairs_then_answers(monkeypatch, capsys):
    replies = iter(["nope", json.dumps({"contradiction": True, "dissenting_opinion": "d"})])
    monkeypatch.setattr(llm, "complete", lambda **kw: _resp(next(replies)))
    art = [{"title": "t", "year": "2026", "journal": "j", "abstract": "x"}]
    assert cron_refine._check_contradiction("minutes", art) == (True, "d")


def test_72h_check_bad_twice_reports_failure(monkeypatch, capsys):
    monkeypatch.setattr(llm, "complete", lambda **kw: _resp("nope"))
    art = [{"title": "t", "year": "2026", "journal": "j", "abstract": "x"}]
    assert cron_refine._check_contradiction("minutes", art) == (False, "")
    assert "failed" in capsys.readouterr().err


# ---- 3. SAFETY: no citation without a retrieved article ----

MDT_REPLY = {
    "selected_specialists": ["Cardiology"],
    "roundtable": [{"specialist": "Cardiology", "priority": "p", "statement": "Give drug X [1] and Y [1, 2].",
                    "citations": [1, 2], "position": "pos"}],
    "rationale": "Based on [1].", "final_recommendation": "Do X [1].",
}


def test_mdt_citation_with_zero_articles_is_marked(monkeypatch):
    monkeypatch.setattr(llm, "complete", lambda **kw: _resp(json.dumps(MDT_REPLY)))
    out = ce.mdt_roundtable_review(SBAR, "syn", ce._build_ref_list([]))
    entry = out["roundtable"][0]
    assert entry["citations"] == []
    assert "[1]" not in entry["statement"] and "NO EVIDENCE FOUND" in entry["statement"]
    assert "[1]" not in out["rationale"] and "NO EVIDENCE FOUND" in out["final_recommendation"]
    assert out["citations_removed"] >= 5


def test_mdt_real_citation_stays(monkeypatch):
    arts = [{"title": "T", "year": "2020", "journal": "J", "url": "u"}]
    reply = json.loads(json.dumps(MDT_REPLY))
    reply["roundtable"][0]["citations"] = [1]
    reply["roundtable"][0]["statement"] = "Give drug X [1]."
    reply["rationale"] = "Based on [1]."
    reply["final_recommendation"] = "Do X [1]."
    monkeypatch.setattr(llm, "complete", lambda **kw: _resp(json.dumps(reply)))
    out = ce.mdt_roundtable_review(SBAR, "syn", ce._build_ref_list(arts))
    assert out["roundtable"][0]["citations"] == [1]
    assert out["roundtable"][0]["statement"] == "Give drug X [1]."
    assert out["citations_removed"] == 0


def test_group_keeps_real_marks_missing():
    text, n = citations.scrub_text("A [1] B [1, 3] C [2][4]", 2)
    assert text == "A [1] B [1][NO EVIDENCE FOUND] C [2][4]".replace("[4]", "[NO EVIDENCE FOUND]") and n == 2


def test_auditor_minutes_are_scrubbed(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "complete", lambda **kw: _resp("## Minutes\nClaim [1].\n## References\n[1] Made up"))
    saved = {}
    monkeypatch.setattr(ce.state_manager, "append_minutes", lambda **kw: saved.update(kw))
    monkeypatch.setattr(ce.state_manager, "get_case", lambda cid: {"case_id": cid})
    monkeypatch.setattr(ce.state_manager, "create_case", lambda **kw: None)
    monkeypatch.setattr(ce.state_manager, "update_case_field", lambda *a: None)
    monkeypatch.setattr(ce.state_manager, "save_case", lambda c: None)
    out = {"sbar": SBAR, "evidence": {"tier": "t", "articles": []}, "risk_analysis": {}}
    text = ce.auditor_record("CIN-TEST", out)
    assert "[1]" not in text and "NO EVIDENCE FOUND" in text and saved["content"] == text

import sys

from debate import evidence as ev


def fake_brain_factory(table):
    calls = []

    def fn(q, limit=5):
        calls.append(q)
        return table.get(q, [])
    fn.calls = calls
    return fn


def fake_pubmed_factory(table, fail=None):
    calls = []

    def fn(q, limit=5):
        calls.append(q)
        if fail:
            raise fail
        return table.get(q, [])
    fn.calls = calls
    return fn


BOOK = {"book": "b", "file_path": "refs/croskerry.md", "heading": "Anchoring", "snippet": "anchoring bias"}


def test_level_table_order():
    assert ev.level_from_types(["Meta-Analysis"]) == 1
    assert ev.level_from_types(["Systematic Review"]) == 1
    assert ev.level_from_types(["Randomized Controlled Trial"]) == 2
    assert ev.level_from_types(["Practice Guideline"]) == 3
    assert ev.level_from_types(["Cohort Study"]) == 4
    assert ev.level_from_types(["Case-Control Study"]) == 4
    assert ev.level_from_types(["Case Reports"]) == 5
    assert ev.level_from_types(["Expert Opinion"]) == 6
    assert ev.level_from_types(["Journal Article"]) == ev.UNKNOWN
    assert ev.level_from_types([]) == ev.UNKNOWN
    assert ev.level_from_types(["Case Reports", "Randomized Controlled Trial"]) == 2


def test_brain_first_pubmed_not_called():
    b = fake_brain_factory({"anchoring": [BOOK]})
    p = fake_pubmed_factory({})
    e = ev.EvidenceList(brain=b, pubmed=p).gather(["anchoring"])
    assert p.calls == []
    assert e.records[0]["source"] == "brain" and e.records[0]["level"] == 6
    assert e.best_ref("anchoring") == "E1"


def test_pubmed_fallback_and_ranking():
    papers = [
        {"pmid": "111", "title": "Cohort", "abstract": "a", "year": "2015", "pub_types": ["Cohort Study"]},
        {"pmid": "222", "title": "MA", "abstract": "b", "year": "2010", "pub_types": ["Meta-Analysis"]},
        {"pmid": "333", "title": "Untyped", "abstract": "c", "year": "2024"},
    ]
    e = ev.EvidenceList(brain=fake_brain_factory({}), pubmed=fake_pubmed_factory({"x": papers}))
    res = e.search_topic("x")
    assert res["status"] == "found"
    assert res["evidence_ids"] == ["E2", "E1", "E3"]  # meta-analysis first, unknown last
    assert e.best_ref("x") == "E2"
    assert e.records[2]["level"] == ev.UNKNOWN
    assert e.records[0]["ref"] == "PMID 111"


def test_pubmed_unavailable_degrades_cleanly():
    p = fake_pubmed_factory({}, fail=ImportError("No module named Bio"))
    e = ev.EvidenceList(brain=fake_brain_factory({}), pubmed=p).gather(["y"])
    assert e.topics["y"]["status"] == ev.NO_EVIDENCE
    assert e.topics["y"]["pubmed_status"] == ev.PUBMED_UNAVAILABLE
    assert e.best_ref("y") == "NONE"
    assert ev.PUBMED_UNAVAILABLE in e.banners()
    assert ev.BANNER_NONE in e.banners()


def test_pubmed_unavailable_banner_when_brain_hits_other_topic():
    b = fake_brain_factory({"a": [BOOK]})
    p = fake_pubmed_factory({}, fail=EnvironmentError("no email"))
    e = ev.EvidenceList(brain=b, pubmed=p).gather(["a", "b"])
    assert e.pubmed_status == ev.PUBMED_UNAVAILABLE
    assert ev.PUBMED_UNAVAILABLE in e.banners()
    assert ev.BANNER_NONE not in e.banners()


def test_default_pubmed_path_does_not_crash_without_biopython(monkeypatch):
    monkeypatch.setitem(sys.modules, "pubmed_client", None)  # import fails: no Biopython, no network
    e = ev.EvidenceList(brain=fake_brain_factory({})).gather(["z"])
    assert e.topics["z"]["status"] == ev.NO_EVIDENCE
    assert e.best_ref("z") == "NONE"


def test_offline_mode_banner():
    p = fake_pubmed_factory({"q": [{"pmid": "1"}]})
    e = ev.EvidenceList(brain=fake_brain_factory({}), pubmed=p, use_pubmed=False).gather(["q"])
    assert p.calls == []
    assert ev.BANNER_NO_PUBMED in e.banners()
    assert e.best_ref("q") == "NONE"


def test_no_invented_citation_bad_pmid_dropped():
    p = fake_pubmed_factory({"q": [{"pmid": "abc", "title": "t", "abstract": "", "year": "2020"}]})
    e = ev.EvidenceList(brain=fake_brain_factory({}), pubmed=p).gather(["q"])
    assert e.records == []
    assert e.topics["q"]["status"] == ev.NO_EVIDENCE
    assert e.label(e.best_ref("q")) == ev.NO_EVIDENCE


def test_brain_failure_does_not_stop():
    def boom(q, limit=5):
        raise RuntimeError("db locked")
    e = ev.EvidenceList(brain=boom, pubmed=fake_pubmed_factory({})).gather(["q"])
    assert e.topics["q"]["status"] == ev.NO_EVIDENCE
    assert any("brain search failed" in n for n in e.notes)


def test_preprint_marked():
    b = fake_brain_factory({"d": [{"file_path": "refs/arxiv_du2023.md", "heading": "Debate", "snippet": "s"}]})
    e = ev.EvidenceList(brain=b).gather(["d"])
    assert e.records[0]["preprint"] is True
    p = fake_pubmed_factory({"m": [{"pmid": "9", "title": "t", "abstract": "", "year": "2023",
                                    "pub_types": ["Preprint"]}]})
    e2 = ev.EvidenceList(brain=fake_brain_factory({}), pubmed=p).gather(["m"])
    assert e2.records[0]["preprint"] is True


def test_dedupe_same_ref_one_id():
    b = fake_brain_factory({"a": [BOOK], "b": [BOOK]})
    e = ev.EvidenceList(brain=b).gather(["a", "b"])
    assert len(e.records) == 1
    assert e.best_ref("a") == e.best_ref("b") == "E1"


def test_record_fields():
    e = ev.EvidenceList(brain=fake_brain_factory({"a": [BOOK]})).gather(["a"])
    assert set(e.records[0]) == {"id", "source", "ref", "level", "year", "snippet",
                                 "preprint", "pubmed_status"}


def test_real_brain_wrapper_returns_without_crash():
    e = ev.EvidenceList(pubmed=fake_pubmed_factory({})).gather(["anchoring bias"])
    assert "anchoring bias" in e.topics


def test_kb_dir_unset_means_no_local_base(monkeypatch):
    monkeypatch.delenv("DEBATE_KB_DIR", raising=False)
    assert ev.brain_search("anchoring") == []
    monkeypatch.setenv("DEBATE_KB_DIR", "  ")
    assert ev.brain_search("anchoring") == []


def test_kb_dir_unset_goes_to_pubmed(monkeypatch):
    monkeypatch.delenv("DEBATE_KB_DIR", raising=False)
    p = fake_pubmed_factory({"anchoring": [{"pmid": "1", "title": "T", "abstract": "a", "year": "2020",
                                            "pub_types": ["Meta-Analysis"]}]})
    e = ev.EvidenceList(pubmed=p, pubtypes=lambda ids: {}).gather(["anchoring"])
    assert p.calls == ["anchoring"]

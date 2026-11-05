"""Tests for adapters/citations.py. Synthetic references only, no network."""

from adapters import citations as c


def _ref(pmid):
    return {"pmid": pmid, "title": "Synthetic trial", "url": f"{c.PUBMED_URL_PREFIX}{pmid}/"}


def test_pmid_format():
    assert c.is_valid_pmid("12345678")
    assert c.is_valid_pmid(1)
    for bad in ("", None, "0", "01234", "PMC12345", "12a45", "1234567890"):
        assert not c.is_valid_pmid(bad), bad


def test_check_references_flags_missing_pmid_and_url_mismatch():
    arts = [
        _ref("11111111"),
        {"pmid": "", "url": ""},
        {"pmid": "22222222", "url": "https://example.invalid/fake"},
    ]
    assert c.check_references(arts) == [
        {"ref": 2, "problem": "missing or malformed PMID"},
        {"ref": 3, "problem": "URL does not match PMID"},
    ]


def test_clean_reference_list_has_no_flags():
    assert c.check_references([_ref("11111111"), _ref("22222222")]) == []


def test_cited_numbers_and_out_of_range():
    text = "Anticoagulation is held [1][3]; see also [7]."
    assert c.cited_numbers(text) == [1, 3, 7]
    assert c.check_citation_numbers(c.cited_numbers(text), n_refs=3) == [7]
    assert c.check_citation_numbers([0, 1], n_refs=1) == [0]


def test_check_roundtable_flags_uncited_and_phantom_citations():
    rt = [
        {"specialist": "Cardiology", "citations": [1, 2]},
        {"specialist": "Nephrology", "citations": []},
        {"specialist": "ICU", "citations": [4]},
    ]
    assert c.check_roundtable(rt, n_refs=2) == [
        {"specialist": "Nephrology", "problem": "no citation"},
        {"specialist": "ICU", "problem": "cites missing reference(s) [4]"},
    ]


def test_pubmed_url_only_for_valid_pmid():
    assert c.pubmed_url("12345") == "https://pubmed.ncbi.nlm.nih.gov/12345/"
    assert c.pubmed_url("abc") == "" and c.pubmed_url("") == ""


def test_check_evidence_refs():
    recs = [{"id": "E1", "source": "brain", "ref": "x.md | H"},
            {"id": "E2", "source": "pubmed", "ref": "PMID 123"},
            {"id": "E3", "source": "pubmed", "ref": "PMID abc"}]
    assert c.check_evidence_refs(["NONE", "E1", "E2"], recs) == []
    flags = c.check_evidence_refs(["E9", "X1", "E3"], recs)
    assert [f["problem"] for f in flags] == ["not in the evidence list", "malformed evidence ref",
                                              "missing or malformed PMID"]

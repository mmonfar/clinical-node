"""Tests for fix A (pubtypes), fix B (withdrawals) and step 6 (Markdown output).
Fake models, fake knowledge base, fake PubMed, mocked HTTP. Synthetic data only."""
import json

import pytest

from debate import evidence as ev
from debate import loop, output, pubtypes, schema
from tests.test_debate_loop import Fake, crit, prop, reply

BOOK = {"book": "b", "file_path": "refs/x.md", "heading": "H", "snippet": "s"}


# ---------------- fix A: publication types ----------------

def esummary(types_by_pmid):
    uids = list(types_by_pmid)
    res = {"uids": uids}
    for u, t in types_by_pmid.items():
        res[u] = {"uid": u, "pubtype": t}
    return json.dumps({"result": res}).encode()


def test_fetch_pubtypes_parses_and_builds_url():
    urls = []

    def http(url):
        urls.append(url)
        return esummary({"111": ["Journal Article", "Meta-Analysis"], "222": ["Case Reports"]})

    out = pubtypes.fetch_pubtypes(["111", "222", "bad", "111"], http_get=http, sleep=lambda s: None)
    assert out == {"111": ["Journal Article", "Meta-Analysis"], "222": ["Case Reports"]}
    assert len(urls) == 1 and "db=pubmed" in urls[0] and "retmode=json" in urls[0]
    assert "id=111%2C222" in urls[0] and "api_key" not in urls[0] and "email" not in urls[0]


def test_fetch_pubtypes_rate_limit_waits_between_requests():
    pubtypes._last[0] = 0.0
    sleeps, now = [], [100.0]

    def http(url):
        return esummary({})

    ids = [str(i) for i in range(1, 251)]  # 3 batches of up to 100
    pubtypes.fetch_pubtypes(ids, http_get=http, sleep=sleeps.append, clock=lambda: now[0])
    assert len(sleeps) == 2 and all(s >= 0.3 for s in sleeps)


def test_pubmed_records_get_levels_from_pubtypes():
    papers = [{"pmid": "111", "title": "t", "abstract": "a", "year": "2020"},
              {"pmid": "222", "title": "t", "abstract": "a", "year": "2021"},
              {"pmid": "333", "title": "t", "abstract": "a", "year": "2022"},
              {"pmid": "444", "title": "t", "abstract": "a", "year": "2023"}]
    types = {"111": ["Randomized Controlled Trial"], "222": ["Systematic Review"],
             "333": ["Practice Guideline"], "444": ["Preprint"]}
    e = ev.EvidenceList(brain=lambda q, n=5: [], pubmed=lambda q, n=5: papers, limit=4,
                        pubtypes=lambda pmids: types)
    e.search_topic("x")
    lv = {r["ref"]: r["level"] for r in e.records}
    assert lv == {"PMID 111": 2, "PMID 222": 1, "PMID 333": 3, "PMID 444": "unknown"}
    assert [r["preprint"] for r in e.records] == [False, False, False, True]
    assert e.topics["x"]["evidence_ids"] == ["E2", "E1", "E3", "E4"]


def test_pubtype_lookup_failure_leaves_level_unknown_and_run_goes_on():
    def boom(pmids):
        raise OSError("network down")
    e = ev.EvidenceList(brain=lambda q, n=5: [], pubmed=lambda q, n=5: [
        {"pmid": "111", "title": "t", "abstract": "a", "year": "2020"}], pubtypes=boom)
    e.search_topic("x")
    assert e.records[0]["level"] == "unknown" and any("lookup failed" in n for n in e.notes)


def test_fake_pubmed_without_pubtypes_makes_no_lookup():
    # default (pubtypes=None) with a fake pubmed must never touch the network
    e = ev.EvidenceList(brain=lambda q, n=5: [], pubmed=lambda q, n=5: [
        {"pmid": "111", "title": "t", "abstract": "a", "year": "2020"}])
    assert e._pubtypes is None


def test_level_table_new_entries():
    assert ev.level_from_types(["Clinical Trial"]) == 4
    assert ev.level_from_types(["Observational Study"]) == 4
    assert ev.level_from_types(["Review"]) == 6
    assert ev.level_from_types(["Journal Article"]) == "unknown"


@pytest.mark.live
def test_live_esummary_optional(request):
    if not request.config.getoption("--live-pubmed", default=False):
        pytest.skip("live check off; run with --live-pubmed")
    out = pubtypes.fetch_pubtypes(["31452104"])
    assert isinstance(out, dict)


# ---------------- fix B: withdrawal ----------------

def evidence():
    return ev.EvidenceList(brain=lambda q, n=5: [BOOK],
                           pubmed=lambda q, n=5: []).gather(["topic"])


def withdraw_run(tmp_path, who="critic_dx", by_round=2, oid="O1"):
    w = {"objection_id": oid, "reason": "proposer fixed it"}
    dx1 = crit("critic_dx", 1, [("C1", "anchoring", "critical")], none=False)
    dx2 = dict(crit("critic_dx", 2, [("C2", "logic_gap", "minor")], none=False),
               withdrawals=[w] if who == "critic_dx" else [])
    pl1 = crit("critic_plan", 1, [("C2", "missing_step", "minor")], none=False)
    pl2 = dict(crit("critic_plan", 2), withdrawals=[w] if who == "critic_plan" else [])
    p = Fake([prop(1), prop(2, [reply("O1", "rebut")])])
    return loop.run_debate("synthetic case", evidence(), p, Fake([dx1, dx2, crit("critic_dx", 3)]),
                           Fake([pl1, pl2, crit("critic_plan", 3)]), tmp_path / "r.jsonl")


def test_schema_accepts_withdrawals_and_rejects_empty_reason():
    t = crit("critic_dx", 2)
    t["withdrawals"] = [{"objection_id": "O1", "reason": "fixed"}]
    assert schema.is_valid(t)
    t["withdrawals"] = [{"objection_id": "O1", "reason": ""}]
    assert not schema.is_valid(t)
    t["withdrawals"] = [{"objection_id": "O1"}]
    assert not schema.is_valid(t)


def test_critic_withdraws_own_objection_later_round(tmp_path):
    res = withdraw_run(tmp_path)
    o1 = res["objections"][0]
    assert o1["status"] == "resolved" and o1["resolved_by"] == "critic_dx"
    assert o1["resolved_reason"] == "proposer fixed it"
    log = loop.read_log(res["log_path"])
    st = [r for r in log if r["kind"] == "status" and r["new"] == "resolved"]
    assert st[0]["by"] == "critic_dx" and st[0]["text"] == "proposer fixed it"
    assert len(res["objections"]) >= 2  # row kept


def test_other_critic_cannot_withdraw(tmp_path):
    res = withdraw_run(tmp_path, who="critic_plan")
    assert res["objections"][0]["status"] == "unresolved"
    log = loop.read_log(res["log_path"])
    assert any(r["kind"] == "withdrawal_ignored" and "only the critic" in r["reason"] for r in log)


def test_same_round_withdrawal_ignored(tmp_path):
    t = crit("critic_dx", 1, [("C1", "anchoring", "major")], none=False)
    t["withdrawals"] = [{"objection_id": "O1", "reason": "oops"}]
    res = loop.run_debate("c", evidence(), Fake([prop(1)]), Fake([t]),
                          Fake([crit("critic_plan", 1)]), tmp_path / "r.jsonl")
    assert res["objections"][0]["status"] == "unresolved"


def test_unknown_withdrawal_id_logged(tmp_path):
    res = withdraw_run(tmp_path, oid="O9")
    assert any(r["kind"] == "withdrawal_ignored" for r in loop.read_log(res["log_path"]))
    assert res["objections"][0]["status"] == "unresolved"


def test_rebut_alone_never_resolves(tmp_path):
    res = withdraw_run(tmp_path, who="nobody")
    assert res["objections"][0]["status"] == "unresolved" and res["dissent"] == "yes"


def test_human_can_reopen_and_it_is_logged(tmp_path):
    res = withdraw_run(tmp_path)
    loop.reopen(res, res["log_path"], "O1", "reviewer A", "withdrawal too early")
    o1 = res["objections"][0]
    assert o1["status"] == "unresolved" and o1["reopened_by"] == "reviewer A"
    assert "resolved_by" not in o1
    last = loop.read_log(res["log_path"])[-1]
    assert last["new"] == "unresolved" and last["old"] == "resolved" and last["by"] == "reviewer A"
    with pytest.raises(ValueError):
        loop.reopen(res, res["log_path"], "O1", "", "x")
    with pytest.raises(KeyError):
        loop.reopen(res, res["log_path"], "O99", "r", "x")


# ---------------- step 6: Markdown output ----------------

def md_run(tmp_path, with_pubmed=True):
    papers = [{"pmid": "12345", "title": "A trial", "abstract": "a", "year": "2019"}]
    e = ev.EvidenceList(brain=lambda q, n=5: [], pubmed=lambda q, n=5: papers if q == "t1" else [],
                        pubtypes=lambda ids: {"12345": ["Randomized Controlled Trial"]})
    e.gather(["t1", "t2"])
    dx = Fake([crit("critic_dx", 1, [("C1", "anchoring", "critical")], none=False),
               crit("critic_dx", 2)])
    pl = Fake([crit("critic_plan", 1, [("C2", "missing_step", "minor")], none=False),
               crit("critic_plan", 2)])
    p1 = prop(1, ref="E1", claims=("C1",))
    p1["claims"].append({"id": "C2", "text": "Claim | with pipe", "evidence_ref": "NONE"})
    p2 = prop(2, [reply("O1", "rebut"), reply("O2", "accept")], ref="E1", claims=("C1",))
    p2["claims"].append({"id": "C2", "text": "Claim | with pipe", "evidence_ref": "NONE"})
    return loop.run_debate("58-year-old synthetic patient.\nSecond line.", e, Fake([p1, p2]), dx, pl,
                           tmp_path / "run.jsonl", output_path=tmp_path / "run.md")


def test_markdown_written_with_all_parts(tmp_path):
    res = md_run(tmp_path)
    md = (tmp_path / "run.md").read_text(encoding="utf-8")
    assert res["output_path"].endswith("run.md")
    assert md.count(loop.DISCLAIMER) == 2 and md.count(output.NOT_REVIEWED) == 2
    assert md.index(loop.DISCLAIMER) < 400 and md.rstrip().endswith(loop.DISCLAIMER)
    assert "## 1. Case summary" in md and "> 58-year-old synthetic patient." in md
    assert "## 3. Final proposal" in md and "leading hypothesis in this simulation" in md
    assert "the diagnosis is" not in md
    assert "E1: PMID 12345 (https://pubmed.ncbi.nlm.nih.gov/12345/), level 2, randomised controlled trial, 2019" in md
    assert "**NO EVIDENCE FOUND**" in md and "Claims without evidence: **1 of 2**" in md
    assert "Claim \\| with pipe" in md
    assert md.index("## 2. Disagreement box") < md.index("## 3. Final proposal")


def test_disagreement_box_lists_every_unresolved_and_critical(tmp_path):
    res = md_run(tmp_path)
    md = (tmp_path / "run.md").read_text(encoding="utf-8")
    box = md.split("## 2. Disagreement box")[1].split("## 3.")[0]
    assert "DISAGREEMENT" in box and "**O1** [CRITICAL, **unresolved**]" in box
    assert "O2" not in box  # accepted + minor: not in the box
    assert "Dissent: **yes**" in md
    assert [o["id"] for o in res["box"]] == ["O1"]


def test_no_dissent_box_text(tmp_path):
    dx, pl = Fake([crit("critic_dx", 1)]), Fake([crit("critic_plan", 1)])
    res = loop.run_debate("c", evidence(), Fake([prop(1)]), dx, pl, tmp_path / "r.jsonl",
                          output_path=tmp_path / "r.md")
    md = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert "No unresolved or critical objections" in md and "Dissent: **no**" in md


def test_invalid_citation_is_flagged_not_shown_as_evidence(tmp_path):
    res = md_run(tmp_path)
    res["evidence"] = []  # pretend the list lost its records
    md = output.render_markdown(res)
    assert "INVALID CITATION" in md


def test_no_evidence_at_all_shows_banner(tmp_path):
    e = ev.EvidenceList(brain=lambda q, n=5: [], pubmed=lambda q, n=5: []).gather(["t"])
    p = prop(1, ref="NONE")
    res = loop.run_debate("c", e, Fake([p]), Fake([crit("critic_dx", 1)]),
                          Fake([crit("critic_plan", 1)]), tmp_path / "r.jsonl",
                          output_path=tmp_path / "r.md")
    md = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert ev.BANNER_NONE in md and "Claims without evidence: **2 of 2**" in md


def test_preprint_marked_in_output(tmp_path):
    e = ev.EvidenceList(brain=lambda q, n=5: [], pubmed=lambda q, n=5: [
        {"pmid": "55", "title": "t", "abstract": "a", "year": "2024"}],
        pubtypes=lambda ids: {"55": ["Preprint"]}).gather(["t"])
    res = loop.run_debate("c", e, Fake([prop(1, claims=("C1",))]), Fake([crit("critic_dx", 1)]),
                          Fake([crit("critic_plan", 1)]), tmp_path / "r.jsonl")
    assert "PREPRINT" in output.render_markdown(res) and "level unknown" in output.render_markdown(res)


def test_output_file_never_overwritten(tmp_path):
    res = md_run(tmp_path)
    with pytest.raises(FileExistsError):
        output.write_markdown(res, tmp_path / "run.md")


def test_invalid_run_without_proposal_still_renders(tmp_path):
    bad = {"role": "proposer"}
    res = loop.run_debate("c", evidence(), Fake([bad]), Fake([crit("critic_dx", 1)]),
                          Fake([crit("critic_plan", 1)]), tmp_path / "r.jsonl")
    md = output.render_markdown(res)
    assert "No valid proposal was produced." in md and md.count(loop.DISCLAIMER) == 2


def test_withdrawal_reason_shown_in_table(tmp_path):
    res = withdraw_run(tmp_path)
    md = output.render_markdown(res)
    assert "resolved by critic_dx: proposer fixed it" in md

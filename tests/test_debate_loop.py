import json

import pytest

from debate import loop, schema
from debate.evidence import EvidenceList

BOOK = {"book": "b", "file_path": "refs/x.md", "heading": "H", "snippet": "s"}


def make_evidence(with_hit=True):
    b = (lambda q, n=5: [BOOK]) if with_hit else (lambda q, n=5: [])

    def no_pm(q, n=5):
        raise ImportError("Bio missing")
    return EvidenceList(brain=b, pubmed=no_pm).gather(["topic"])


def prop(rnd, replies=None, ref="E1", claims=("C1", "C2")):
    t = {"role": "proposer", "round": rnd, "turn_id": f"p{rnd}", "model_id": "fake", "seed": 1,
         "diagnosis": {"leading": "dx", "alternatives": ["alt"], "confidence": "low"},
         "plan": [{"step": "s", "why": "w"}],
         "claims": [{"id": c, "text": "t", "evidence_ref": ref} for c in claims],
         "changes_since_last_round": [], "open_gaps": []}
    if replies is not None:
        t["replies"] = replies
    return t


def reply(oid, response="rebut", ref="NONE"):
    return {"objection_id": oid, "response": response, "text": "because", "evidence_ref": ref}


def crit(role, rnd, objs=(), none=None):
    return {"role": role, "round": rnd, "turn_id": f"{role}{rnd}", "model_id": "fake", "seed": 2,
            "objections": [{"id": f"O{i + 1}", "target_claim": c, "type": t, "text": "x",
                            "severity": s, "evidence_ref": "NONE"}
                           for i, (c, t, s) in enumerate(objs)],
            "no_new_objection": (not objs) if none is None else none}


class Fake:
    """Returns scripted turns in order; the last one repeats. Records requests."""

    def __init__(self, turns):
        self.turns, self.requests = list(turns), []

    def __call__(self, req):
        self.requests.append(req)
        i = min(len(self.requests) - 1, len(self.turns) - 1)
        t = self.turns[i]
        if isinstance(t, Exception):
            raise t
        return t


def run(tmp_path, p, a, b, **kw):
    return loop.run_debate("synthetic case", make_evidence(), p, a, b,
                           tmp_path / "run.jsonl", **kw)


# ---- the new-objection rule ----

def test_rule_new_key_is_new():
    r = loop.Registry()
    assert r.classify("C1", "anchoring", "minor") == (True, None)


def test_rule_same_key_same_or_lower_severity_is_not_new():
    r = loop.Registry()
    r.add({"id": "O1", "target_claim": "C1", "type": "anchoring", "text": "x",
           "severity": "major", "evidence_ref": "NONE"}, "critic_dx", 1, None)
    assert r.classify("C1", "anchoring", "major") == (False, None)
    assert r.classify("C1", "anchoring", "minor") == (False, None)


def test_rule_higher_severity_is_new_and_points_to_older():
    r = loop.Registry()
    r.add({"id": "O1", "target_claim": "C1", "type": "anchoring", "text": "x",
           "severity": "major", "evidence_ref": "NONE"}, "critic_dx", 1, None)
    assert r.classify("C1", "anchoring", "critical") == (True, "O1")


def test_rule_different_claim_or_type_is_new():
    r = loop.Registry()
    r.add({"id": "O1", "target_claim": "C1", "type": "anchoring", "text": "x",
           "severity": "major", "evidence_ref": "NONE"}, "critic_dx", 1, None)
    assert r.classify("C2", "anchoring", "minor")[0] is True
    assert r.classify("C1", "logic_gap", "minor")[0] is True


def test_answered_objection_is_still_not_new(tmp_path):
    # Round 1 objection; proposer accepts in round 2; critic raises the same key again: duplicate.
    dx = Fake([crit("critic_dx", 1, [("C1", "anchoring", "major")], none=False),
               crit("critic_dx", 2, [("C1", "anchoring", "major")], none=False)])
    pl = Fake([crit("critic_plan", 1), crit("critic_plan", 2)])
    p = Fake([prop(1), prop(2, [reply("O1", "accept")])])
    res = run(tmp_path, p, dx, pl)
    assert len(res["objections"]) == 1
    assert res["objections"][0]["status"] == "accepted"
    assert res["status"] == "converged"
    kinds = [(r["kind"], r.get("new")) for r in loop.read_log(res["log_path"]) if r["kind"] == "objection"]
    assert kinds == [("objection", True), ("objection", False)]


# ---- stop rules ----

def test_stop_both_critics_no_new(tmp_path):
    p = Fake([prop(1)])
    dx, pl = Fake([crit("critic_dx", 1)]), Fake([crit("critic_plan", 1)])
    res = run(tmp_path, p, dx, pl)
    assert res["status"] == "converged" and res["stop"]["round"] == 1
    assert res["dissent"] == "no" and res["objections"] == []


def test_stop_zero_new_by_code_even_if_critic_says_new(tmp_path):
    # Critic lies: no_new_objection False but only repeats an old key. Code stops it.
    dx = Fake([crit("critic_dx", 1, [("C1", "anchoring", "minor")], none=False),
               crit("critic_dx", 2, [("C1", "anchoring", "minor")], none=False)])
    pl = Fake([crit("critic_plan", 1), crit("critic_plan", 2)])
    p = Fake([prop(1), prop(2, [reply("O1")])])
    res = run(tmp_path, p, dx, pl)
    assert res["status"] == "converged" and res["stop"]["round"] == 2
    assert res["stop"]["new_objections_this_round"] == 0


def test_stop_max_rounds(tmp_path):
    types = ["anchoring", "logic_gap", "premature_closure", "other", "missed_differential"]
    dx = Fake([crit("critic_dx", r, [("C1", types[r - 1], "minor")], none=False) for r in range(1, 6)])
    pl = Fake([crit("critic_plan", r) for r in range(1, 6)])
    p = Fake([prop(1)] + [prop(r, []) for r in range(2, 6)])
    res = run(tmp_path, p, dx, pl, max_rounds=3)
    assert res["status"] == "max_rounds" and res["stop"]["round"] == 3
    assert len(res["objections"]) == 3 and res["dissent"] == "yes"


def test_max_rounds_hard_limit(tmp_path):
    with pytest.raises(ValueError):
        run(tmp_path, Fake([prop(1)]), Fake([crit("critic_dx", 1)]), Fake([crit("critic_plan", 1)]),
            max_rounds=7)
    with pytest.raises(ValueError):
        run(tmp_path, Fake([prop(1)]), Fake([crit("critic_dx", 1)]), Fake([crit("critic_plan", 1)]),
            max_rounds=0)


def test_stop_invalid_twice_in_a_row(tmp_path):
    bad = {"role": "proposer"}
    p = Fake([prop(1), bad])           # round 2: bad, retry bad -> 1 invalid turn
    dx = Fake([crit("critic_dx", 1, [("C1", "anchoring", "minor")], none=False),
               {"role": "critic_dx"}])  # round 2 critic: bad, retry bad -> 2nd invalid in a row
    pl = Fake([crit("critic_plan", 1), crit("critic_plan", 2)])
    res = run(tmp_path, p, dx, pl)
    assert res["status"] == "invalid_turn"
    log = loop.read_log(res["log_path"])
    assert sum(1 for r in log if r["kind"] == "turn_invalid") == 2


def test_one_retry_fixes_a_turn(tmp_path):
    dx = Fake([{"role": "critic_dx"}, crit("critic_dx", 1)])
    pl = Fake([crit("critic_plan", 1)])
    res = run(tmp_path, Fake([prop(1)]), dx, pl)
    assert res["status"] == "converged"
    assert dx.requests[1]["retry_errors"], "retry must carry the error text"
    assert dx.requests[0]["retry_errors"] == []
    log = loop.read_log(res["log_path"])
    assert [r["valid"] for r in log if r["kind"] == "turn" and r["role"] == "critic_dx"] == [False, True]


def test_model_that_raises_is_an_invalid_turn_not_a_crash(tmp_path):
    p = Fake([RuntimeError("boom")])
    res = run(tmp_path, p, Fake([crit("critic_dx", 1)]), Fake([crit("critic_plan", 1)]))
    assert res["status"] == "invalid_turn"
    errs = [r["errors"] for r in loop.read_log(res["log_path"]) if r["kind"] == "turn_invalid"]
    assert "boom" in errs[0][0]   # the log keeps the reason, not just the error type


def test_stop_timeout(tmp_path):
    t = {"now": 0.0}

    def clock():
        t["now"] += 400.0
        return t["now"]
    dx = Fake([crit("critic_dx", 1, [("C1", "anchoring", "minor")], none=False)])
    res = run(tmp_path, Fake([prop(1)]), dx, Fake([crit("critic_plan", 1)]), time_limit_s=900, clock=clock)
    assert res["status"] == "timeout"


# ---- checks the code does on turns ----

def test_evidence_id_not_in_list_is_invalid(tmp_path):
    res = run(tmp_path, Fake([prop(1, ref="E9")]), Fake([crit("critic_dx", 1)]), Fake([crit("critic_plan", 1)]))
    assert res["status"] == "invalid_turn"
    log = loop.read_log(res["log_path"])
    assert any("not in the evidence list" in e for r in log if r["kind"] == "turn_invalid" for e in r["errors"])


def test_none_ref_is_allowed(tmp_path):
    res = run(tmp_path, Fake([prop(1, ref="NONE")]), Fake([crit("critic_dx", 1)]), Fake([crit("critic_plan", 1)]))
    assert res["status"] == "converged"


def test_unknown_target_claim_is_invalid(tmp_path):
    dx = Fake([crit("critic_dx", 1, [("C9", "anchoring", "minor")], none=False)])
    res = run(tmp_path, Fake([prop(1)]), dx, Fake([crit("critic_plan", 1)]))
    assert res["objections"] == []  # the bad objection never entered the table
    log = loop.read_log(res["log_path"])
    assert any("not a known claim" in e for r in log if r["kind"] == "turn_invalid" for e in r["errors"])


def test_wrong_round_is_invalid(tmp_path):
    res = run(tmp_path, Fake([prop(2)]), Fake([crit("critic_dx", 1)]), Fake([crit("critic_plan", 1)]))
    assert res["status"] == "invalid_turn"


# ---- status, unresolved kept and shown ----

def two_round_run(tmp_path, response):
    dx = Fake([crit("critic_dx", 1, [("C1", "anchoring", "critical")], none=False),
               crit("critic_dx", 2)])
    pl = Fake([crit("critic_plan", 1, [("C2", "missing_step", "minor")], none=False),
               crit("critic_plan", 2)])
    p = Fake([prop(1), prop(2, [reply("O1", response), reply("O2", "accept")])])
    return run(tmp_path, p, dx, pl)


def test_rebutted_critical_objection_stays_unresolved_and_in_box(tmp_path):
    res = two_round_run(tmp_path, "rebut")
    by = {o["id"]: o for o in res["objections"]}
    assert by["O1"]["status"] == "unresolved" and by["O2"]["status"] == "accepted"
    assert [o["id"] for o in res["box"]] == ["O1"]
    assert res["dissent"] == "yes" and res["counts"] == {"unresolved": 1, "accepted": 1, "resolved": 0}


def test_accepted_critical_is_still_in_box(tmp_path):
    res = two_round_run(tmp_path, "accept")
    assert res["dissent"] == "no"
    assert [o["id"] for o in res["box"]] == ["O1"]  # critical is always shown


def test_objections_never_deleted(tmp_path):
    res = two_round_run(tmp_path, "rebut")
    assert [o["id"] for o in res["objections"]] == ["O1", "O2"]
    assert all(o["text"] == "x" for o in res["objections"])


def test_critics_do_not_see_each_other_in_round_one(tmp_path):
    dx = Fake([crit("critic_dx", 1, [("C1", "anchoring", "minor")], none=False), crit("critic_dx", 2)])
    pl = Fake([crit("critic_plan", 1), crit("critic_plan", 2)])
    run(tmp_path, Fake([prop(1), prop(2, [reply("O1")])]), dx, pl)
    assert pl.requests[0]["other_critic_objections"] == []
    assert [o["id"] for o in pl.requests[1]["other_critic_objections"]] == ["O1"]


def test_unknown_reply_id_is_logged_not_applied(tmp_path):
    dx = Fake([crit("critic_dx", 1, [("C1", "anchoring", "minor")], none=False), crit("critic_dx", 2)])
    pl = Fake([crit("critic_plan", 1), crit("critic_plan", 2)])
    res = run(tmp_path, Fake([prop(1), prop(2, [reply("O7", "accept")])]), dx, pl)
    assert res["objections"][0]["status"] == "unresolved"
    assert any(r["kind"] == "reply_ignored" for r in loop.read_log(res["log_path"]))


def test_higher_severity_adds_entry_and_keeps_old(tmp_path):
    dx = Fake([crit("critic_dx", 1, [("C1", "anchoring", "minor")], none=False),
               crit("critic_dx", 2, [("C1", "anchoring", "critical")], none=False),
               crit("critic_dx", 3)])
    pl = Fake([crit("critic_plan", 1), crit("critic_plan", 2), crit("critic_plan", 3)])
    p = Fake([prop(1), prop(2, []), prop(3, [])])
    res = run(tmp_path, p, dx, pl)
    assert [o["severity"] for o in res["objections"]] == ["minor", "critical"]
    assert res["objections"][1]["supersedes"] == "O1"


def test_mark_resolved_is_logged_and_keeps_row(tmp_path):
    res = two_round_run(tmp_path, "rebut")
    n_before = len(loop.read_log(res["log_path"]))
    loop.mark_resolved(res, res["log_path"], "O1", "reviewer A", "checked")
    assert res["objections"][0]["status"] == "resolved"
    log = loop.read_log(res["log_path"])
    assert len(log) == n_before + 1 and log[-1]["new"] == "resolved"
    assert len(res["objections"]) == 2


# ---- log ----

def test_log_is_append_only_jsonl_and_stop_record_valid(tmp_path):
    res = two_round_run(tmp_path, "rebut")
    log = loop.read_log(res["log_path"])
    assert [r["seq"] for r in log] == list(range(1, len(log) + 1))
    assert log[0]["kind"] == "run_start" and "Not a medical device" in log[0]["disclaimer"]
    assert log[1]["kind"] == "evidence"
    stops = [r for r in log if r["kind"] == "stop"]
    assert len(stops) == 1
    rec = {k: v for k, v in stops[0].items() if k not in ("seq", "kind")}
    assert schema.validate(rec, schema.STOP) == []
    for line in open(res["log_path"], encoding="utf-8"):
        json.loads(line)


def test_log_file_is_never_reused(tmp_path):
    run(tmp_path, Fake([prop(1)]), Fake([crit("critic_dx", 1)]), Fake([crit("critic_plan", 1)]))
    with pytest.raises(FileExistsError):
        run(tmp_path, Fake([prop(1)]), Fake([crit("critic_dx", 1)]), Fake([crit("critic_plan", 1)]))


def test_no_evidence_banner_in_result(tmp_path):
    def no_pm(q, n=5):
        raise ImportError("Bio")
    e = EvidenceList(brain=lambda q, n=5: [], pubmed=no_pm).gather(["t"])
    res = loop.run_debate("c", e, Fake([prop(1, ref="NONE")]), Fake([crit("critic_dx", 1)]),
                          Fake([crit("critic_plan", 1)]), tmp_path / "r.jsonl")
    assert "No evidence retrieved. Treat all output as unsupported." in res["banners"]

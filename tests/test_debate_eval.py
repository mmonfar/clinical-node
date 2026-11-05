import json

from debate import eval as ev


def res(case, arm, repeat=0, leading="x", proposal="", objs=(), claims_text="", turns=(3, 3),
        status="converged", bad_cit=0, unsup=0):
    return {"case_id": case, "arm": arm, "repeat": repeat, "status": status, "leading": leading,
            "claims": [{"id": "C1", "text": "t", "evidence_ref": "E1"}], "proposal_text": proposal,
            "claims_text": claims_text,
            "objections": [{"raised_by": r, "text": t, "type": "other", "severity": "major",
                            "status": "unresolved", "evidence_ref": "NONE"} for r, t in objs],
            "turns_total": turns[0], "turns_valid": turns[1], "invalid_citations": bad_cit,
            "unsupported_claims": unsup, "evidence_records": [{"id": "E1", "ref": "r", "snippet": "s"}]}


def case(cid, cat="trap"):
    return {"id": cid, "category": cat, "evidence_topics": ["t"],
            "expected_leading_diagnosis": {"name": "pulmonary embolism", "synonyms": ["pe"]},
            "must_catch": [{"id": "MC1", "critic": "critic_plan", "terms": ["bleed*", "allergy"], "why": "w"}],
            "must_not_claim": [{"id": "MN1", "terms": ["no bleeding risk"], "why": "w"}], "reviewed": False}


CASES = [case("a"), case("b", "easy")]
QUIET = dict(say=lambda *_: None)


def test_term_matching():
    assert ev.term_hit("bleed*", "active bleeding present")
    assert not ev.term_hit("bleed", "active bleeding present")      # whole word without the star
    assert ev.term_hit("beta-blocker", "Avoid a Beta-Blocker here")
    assert ev.dx_matches("Acute PE", {"name": "pulmonary embolism", "synonyms": ["pe"]})
    assert not ev.dx_matches(None, {"name": "x", "synonyms": []})


def test_scores_with_hand_built_results():
    rs = [res("a", "A", proposal="plain"), res("a", "B", objs=[("critic_plan", "avoid this, active bleeding")]),
          res("b", "A", proposal="avoid drug, allergy", turns=(1, 1)),
          res("b", "B", objs=[("critic_dx", "allergy is a danger")], turns=(4, 3), bad_cit=1,
              claims_text="there is no bleeding risk")]
    S = ev.score_group(rs, CASES, ("A", "B"))
    assert S["2_must_catch"]["value"] == (1, 2, 0, 1)             # A 1, B 2; trap: A 0, B 1
    assert S["2_must_catch"]["verdict"] == "meets target"
    assert S["1_valid_turns_B"]["value"] == 6 / 7 and S["1_valid_turns_B"]["verdict"] == "below target"
    assert S["3_must_not_claim_B"]["verdict"] == "below target"
    assert S["3_must_not_claim_A"]["verdict"] == "meets target"
    assert S["5_invalid_citations_B"]["value"] == 1
    assert S["5_invalid_citations_B"]["verdict"] == "below target"
    assert S["6_converged"]["value"] == 1.0
    # the right critic type is counted separately: case b came from critic_dx, not critic_plan
    assert "right critic type: 1" in S["2_must_catch"]["shown"]


def test_not_measured_and_partial_coverage():
    S = ev.score_group([], CASES, ("A", "B"))
    for k, s in S.items():
        assert s["shown"] == "not measured" and s["verdict"] == "not measured", k
        assert s["n"] == 0 and s["N"] == 2, k
    S = ev.score_group([res("a", "A"), res("a", "B")], CASES, ("A", "B"))
    s = S["5_invalid_citations_B"]
    assert s["n"] == 1 and s["N"] == 2 and "no verdict" in s["verdict"]
    assert S["7_repeat_agreement"]["verdict"] == "not measured"      # no repeats yet
    report = ev.build_report([], CASES, {"run_id": "r", "mode": "live"})
    assert "not measured" in report and "meets target" not in report


def test_repeat_agreement():
    rs = [res("a", "B", repeat=k, leading=l) for k, l in enumerate(["PE", "pulmonary embolism", "pe"])]
    rs += [res("b", "B", repeat=k, leading=l) for k, l in enumerate(["PE", "PE", "asthma"])]
    s = ev.score_group(rs, CASES, ("A", "B"))["7_repeat_agreement"]
    assert s["value"] == 0.5 and s["n"] == 2 and s["verdict"] == "below target"


def test_human_sheet_has_empty_verdict_and_snippet():
    rows, n = ev.human_sheet_rows([res("a", "B"), res("b", "B")])
    assert n == 2 and rows[0]["cited_snippet"] == "s" and rows[0]["claim_text"] == "t"
    assert all(r["verdict (yes/partly/no)"] == "" for r in rows)


def test_resume_skips_finished_and_survives_a_failure(tmp_path):
    tasks = ev.make_tasks(["a", "b"], swap=False)
    ok = {"status": "converged", "seconds": 1}

    def execute(t):
        if t == ("a", "B", 0):
            raise RuntimeError("model crashed")
        return dict(ok, case_id=t[0], arm=t[1], repeat=t[2])
    s1 = ev.run_plan(tasks, tmp_path, execute, **QUIET)
    assert len(s1["failed"]) == 1 and s1["ran"] == len(tasks) - 1       # one failure did not stop the run
    s2 = ev.run_plan(tasks, tmp_path, lambda t: dict(ok, case_id=t[0], arm=t[1], repeat=t[2]), **QUIET)
    assert s2["skipped"] == len(tasks) - 1 and s2["ran"] == 1           # only the failed one is redone
    (tmp_path / "results" / "a__A__r0.json").write_text("{broken", encoding="utf-8")   # half-written
    s3 = ev.run_plan(tasks, tmp_path, lambda t: dict(ok, case_id=t[0], arm=t[1], repeat=t[2]), **QUIET)
    assert s3["ran"] == 1


def test_task_order():
    t = ev.make_tasks(["a", "b"])
    assert t[:4] == [("a", "A", 0), ("a", "B", 0), ("b", "A", 0), ("b", "B", 0)]
    assert [x[1] for x in t[4:8]] == ["A_swap", "B_swap", "A_swap", "B_swap"]
    assert all(x[1] == "B" and x[2] > 0 for x in t[8:])


def test_hours_cap_stops_new_work(tmp_path):
    now = [0.0]

    def execute(t):
        now[0] += 3600                       # every task "takes" one hour
        return {"case_id": t[0], "arm": t[1], "repeat": t[2], "status": "converged"}
    tasks = ev.make_tasks(["a", "b"], swap=False)
    s = ev.run_plan(tasks, tmp_path, execute, hours=2, clock=lambda: now[0], **QUIET)
    assert s["ran"] == 2 and "hours cap" in s["stopped"]
    assert len(list((tmp_path / "results").glob("*.json"))) == 2


def test_server_down_drops_result_and_stops(tmp_path):
    s = ev.run_plan([("a", "A", 0), ("a", "B", 0)], tmp_path, lambda t: {"status": "invalid_turn"},
                    healthy=lambda: False, **QUIET)
    assert s["ran"] == 0 and "run again" in s["stopped"]
    assert not list((tmp_path / "results").glob("*.json"))


def test_evidence_is_cached_and_failure_is_recorded(tmp_path):
    n = []

    def fetch(c):
        n.append(1)
        return {"records": [{"id": "E1", "ref": "r", "snippet": "s", "level": 6}], "topics": {},
                "banners": [], "notes": []}
    e1 = ev.get_evidence({"id": "a"}, tmp_path, fetch)
    e2 = ev.get_evidence({"id": "a"}, tmp_path, fetch)
    assert len(n) == 1 and e1.records == e2.records

    def broken(c):
        raise ConnectionError("down")
    e3 = ev.get_evidence({"id": "z"}, tmp_path, broken)
    assert e3.records == [] and e3.to_dict()["notes"] and e3.banners()


def test_estimate_hours():
    lo, mid, hi = ev.estimate_hours(ev.make_tasks([f"c{i}" for i in range(14)]))
    assert 0 < lo < mid < hi


def test_cases_are_well_formed():
    cases = ev.load_cases()
    assert 12 <= len(cases) <= 15
    for c in cases:
        assert c["reviewed"] is False and c["category"] in ("easy", "ambiguous", "trap")
        assert c["must_catch"] is not None and c["expected_leading_diagnosis"]["name"]


def test_fake_run_end_to_end_no_network(tmp_path, capsys):
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    for i, c in enumerate(ev.load_cases()[:3]):
        (cases_dir / f"{i}.json").write_text(json.dumps(c), encoding="utf-8")
    rc = ev.main(["--fake", "--runs-dir", str(tmp_path / "runs"), "--cases-dir", str(cases_dir),
                  "--run-id", "t1"])
    out = capsys.readouterr().out
    assert rc == 0 and "FAKE RUN" in out and "APPROXIMATE" in out and "Estimated time" in out
    assert (tmp_path / "runs" / "t1" / "report.md").exists()
    assert (tmp_path / "runs" / "t1" / "human_review_sheet.csv").exists()


def test_live_says_clearly_when_ollama_is_down(monkeypatch, capsys):
    from adapters import llm
    monkeypatch.setattr(llm, "ollama_running", lambda: False)
    assert ev.main(["--live"]) == 2
    assert "Ollama is not running" in capsys.readouterr().out


def test_negation_guard_and_sentence_in_violation():
    c = {"id": "n", "category": "trap", "must_catch": [], "expected_leading_diagnosis": {"name": "x", "synonyms": []},
         "must_not_claim": [{"id": "MN1", "terms": ["start amoxicillin"], "why": "w"}]}
    neg = res("n", "B", claims_text="Do not start amoxicillin. Treat with a macrolide")
    bad, negated = ev.violated_items(c, neg)
    assert bad == [] and negated[0]["sentence"] == "Do not start amoxicillin"
    assert ev.violated_items(c, res("n", "B", claims_text="We rather than wait start amoxicillin"))[0] == []
    pos = res("n", "B", claims_text="Fine. Then start amoxicillin now")
    bad, _ = ev.violated_items(c, pos)
    assert bad == [{"id": "MN1", "sentence": "Then start amoxicillin now"}]
    # a negation farther than 3 words away does not protect
    far = res("n", "B", claims_text="Not sure but we think so, start amoxicillin")
    assert len(ev.violated_items(c, far)[0]) == 1
    S = ev.score_group([res("n", "A", claims_text="do not start amoxicillin")], [c], ("A", "B"))
    assert S["3_must_not_claim_A"]["verdict"].startswith("meets") or "coverage" in S["3_must_not_claim_A"]["verdict"]
    assert S["3_must_not_claim_A"]["value"] == 1.0


def test_report_lists_every_hit_sentence_and_the_note():
    rs = [res("a", "A", proposal="Plain. Avoid it with bleeding here"), res("a", "B", claims_text="no bleeding risk today")]
    r = ev.build_report(rs, CASES, {"run_id": "r", "mode": "live"})
    assert "Code screen only" in r and "MAIN OUTCOME" in r
    assert '- A a MC1: "Avoid it with bleeding here"' in r
    assert 'a MN1: "no bleeding risk today"' in r        # counted violation prints its sentence


def test_dx_generic_term_inside_other_named_diagnosis_does_not_match():
    key = {"name": "essential hypertension", "synonyms": ["hypertension", "high blood pressure"]}
    assert not ev.dx_matches("Pulmonary hypertension secondary to Tetralogy of Fallot", key)
    assert not ev.dx_matches("Portal hypertension. The patient history of hypertension is noted.", key)
    assert ev.dx_matches("Hypertension with potential for complications", key)
    assert ev.dx_matches("Essential hypertension, uncontrolled", key)


def mc_case():
    return {"id": "m", "category": "trap", "must_catch": [{"id": "MC1", "critic": "critic_plan",
            "terms": ["beta-blocker*", "bronchospasm"], "why": "w"}], "must_not_claim": [],
            "expected_leading_diagnosis": {"name": "x", "synonyms": []}}


def test_r2_recommended_mention_is_not_caught():
    # c09-style: the text recommends the drug the key says to warn against
    r = res("m", "A", proposal="Medical management with ACE inhibitors and beta-blockers is appropriate. Fine")
    x = ev.caught_items(mc_case(), r)[0]
    assert not x["caught"] and x["stance"] == "recommends" and x["mentioned"]


def test_r2_warning_is_caught_also_from_an_objection():
    r = res("m", "A", proposal="Avoid beta-blockers in asthma")
    assert ev.caught_items(mc_case(), r)[0]["caught"]
    r = res("m", "B", proposal="Plan", objs=[("critic_plan", "Beta-blockers are contraindicated: bronchospasm risk")])
    x = ev.caught_items(mc_case(), r)[0]
    assert x["caught"] and x["right_critic"]


def test_r2_unclear_goes_to_check_by_eye_and_is_not_counted():
    mention = res("m", "A", proposal="The patient takes a beta-blocker at home")
    mixed = res("m", "A", proposal="Include a beta-blocker but avoid high doses")
    for r in (mention, mixed):
        x = ev.caught_items(mc_case(), r)[0]
        assert not x["caught"] and x["stance"] == "check by eye"
    rep = ev.build_report([mention], [mc_case()], {"run_id": "r", "mode": "live"})
    assert "check by eye" in rep and '- A m MC1: "The patient takes a beta-blocker at home"' in rep


def test_r2_no_term_means_no_stance():
    x = ev.caught_items(mc_case(), res("m", "A", proposal="Nothing relevant here"))[0]
    assert not x["caught"] and x["stance"] is None and not x["mentioned"]

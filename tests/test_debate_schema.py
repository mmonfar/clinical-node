"""Tests for debate/schema.py. Synthetic fake turns only."""
import copy
import json

import pytest

from debate.schema import SCHEMAS, is_valid, validate_turn

COMMON = {"round": 1, "turn_id": "t1", "model_id": "fake-model", "seed": 42}

GOOD_PROPOSER = dict(COMMON, role="proposer",
    diagnosis={"leading": "Synthetic case: community-acquired pneumonia", "alternatives": ["pulmonary embolism"], "confidence": "medium"},
    plan=[{"step": "Chest X-ray", "why": "Confirm consolidation"}],
    claims=[{"id": "C1", "text": "Fever and cough fit pneumonia", "evidence_ref": "E1"},
            {"id": "C2", "text": "Outpatient oral therapy is enough", "evidence_ref": "NONE"}],
    changes_since_last_round=[], open_gaps=["Oxygen saturation not given"])

GOOD_CRITIC_DX = dict(COMMON, role="critic_dx", objections=[
    {"id": "O1", "target_claim": "C1", "type": "missed_differential",
     "text": "Pulmonary embolism not excluded", "severity": "major", "evidence_ref": "E2"}],
    no_new_objection=False)

GOOD_CRITIC_PLAN = dict(COMMON, role="critic_plan", objections=[
    {"id": "O2", "target_claim": "C2", "type": "dose_or_drug",
     "text": "No dose or duration given", "severity": "minor", "evidence_ref": "NONE"}],
    no_new_objection=False)

GOOD_CRITIC_DONE = dict(GOOD_CRITIC_DX, objections=[], no_new_objection=True)

GOOD_REPLY = dict(GOOD_PROPOSER, round=2, changes_since_last_round=["Added D-dimer"],
    replies=[{"objection_id": "O1", "response": "partly", "text": "Will test D-dimer", "evidence_ref": "E2"}])

GOOD_STOP = {"role": "stop", "round": 3, "status": "converged",
             "reason": "both critics: no_new_objection", "new_objections_this_round": 0}

GOOD = [GOOD_PROPOSER, GOOD_CRITIC_DX, GOOD_CRITIC_PLAN, GOOD_CRITIC_DONE, GOOD_REPLY, GOOD_STOP]


def mutate(base, fn):
    t = copy.deepcopy(base)
    fn(t)
    return t


# (name, bad turn, text that must appear in the errors)
BAD = [
    ("not an object", ["x"], "JSON object"),
    ("unknown role", dict(GOOD_PROPOSER, role="judge"), "$.role"),
    ("missing role", mutate(GOOD_PROPOSER, lambda t: t.pop("role")), "$.role"),
    ("missing seed", mutate(GOOD_PROPOSER, lambda t: t.pop("seed")), "'seed'"),
    ("seed is text", mutate(GOOD_PROPOSER, lambda t: t.update(seed="42")), "$.seed"),
    ("round zero", mutate(GOOD_PROPOSER, lambda t: t.update(round=0)), "minimum"),
    ("round above hard limit", mutate(GOOD_PROPOSER, lambda t: t.update(round=7)), "maximum"),
    ("bad confidence", mutate(GOOD_PROPOSER, lambda t: t["diagnosis"].update(confidence="certain")), "confidence"),
    ("empty plan", mutate(GOOD_PROPOSER, lambda t: t.update(plan=[])), "at least 1"),
    ("empty claim text", mutate(GOOD_PROPOSER, lambda t: t["claims"][0].update(text="  ")), "empty"),
    ("invented citation form", mutate(GOOD_PROPOSER, lambda t: t["claims"][0].update(evidence_ref="PMID 123")), "evidence_ref"),
    ("evidence_ref missing", mutate(GOOD_PROPOSER, lambda t: t["claims"][0].pop("evidence_ref")), "'evidence_ref'"),
    ("extra field", mutate(GOOD_PROPOSER, lambda t: t.update(verdict="the diagnosis is X")), "unexpected field 'verdict'"),
    ("bad claim id", mutate(GOOD_PROPOSER, lambda t: t["claims"][0].update(id="claim1")), "$.claims[0].id"),
    ("critic without target_claim", mutate(GOOD_CRITIC_DX, lambda t: t["objections"][0].pop("target_claim")), "'target_claim'"),
    ("vague target_claim", mutate(GOOD_CRITIC_DX, lambda t: t["objections"][0].update(target_claim="the plan")), "target_claim"),
    ("critic_dx uses plan type", mutate(GOOD_CRITIC_DX, lambda t: t["objections"][0].update(type="dose_or_drug")), "not in"),
    ("critic_plan uses dx type", mutate(GOOD_CRITIC_PLAN, lambda t: t["objections"][0].update(type="anchoring")), "not in"),
    ("bad severity", mutate(GOOD_CRITIC_DX, lambda t: t["objections"][0].update(severity="fatal")), "severity"),
    ("no_new_objection is text", mutate(GOOD_CRITIC_DX, lambda t: t.update(no_new_objection="false")), "expected boolean"),
    ("bad reply response", mutate(GOOD_REPLY, lambda t: t["replies"][0].update(response="ignore")), "response"),
    ("stop with bad status", dict(GOOD_STOP, status="done"), "status"),
    ("stop negative count", dict(GOOD_STOP, new_objections_this_round=-1), "minimum"),
]


@pytest.mark.parametrize("turn", GOOD, ids=[t["role"] + str(i) for i, t in enumerate(GOOD)])
def test_good_turns_pass(turn):
    assert validate_turn(turn) == []
    assert is_valid(turn)


@pytest.mark.parametrize("name,turn,expect", BAD, ids=[b[0] for b in BAD])
def test_bad_turns_fail_with_useful_error(name, turn, expect):
    errors = validate_turn(turn)
    assert errors, name
    assert any(expect in e for e in errors), errors
    assert not is_valid(turn)


def test_good_turns_survive_json_round_trip():
    for turn in GOOD:
        assert validate_turn(json.loads(json.dumps(turn))) == []


def test_bool_is_not_an_integer():
    assert not is_valid(dict(GOOD_PROPOSER, seed=True))


def test_all_roles_have_schema():
    assert set(SCHEMAS) == {"proposer", "critic_dx", "critic_plan", "stop"}


def test_matches_jsonschema_library_when_installed():
    jsonschema = pytest.importorskip("jsonschema")
    for turn in GOOD:
        jsonschema.validate(turn, SCHEMAS[turn["role"]])
    for name, turn, _ in BAD:
        # Our validator is stricter on blank text (whitespace only); the library is not.
        if name != "empty claim text" and isinstance(turn, dict) and turn.get("role") in SCHEMAS:
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(turn, SCHEMAS[turn["role"]])

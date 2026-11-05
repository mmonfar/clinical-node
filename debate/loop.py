"""Debate loop (SPEC section 3). Models are plain callables, so tests use fakes.

Research and demonstration software. Not a medical device. Synthetic cases only.

A model is a callable: model(request: dict) -> dict (one turn). It may raise; that is an invalid turn.
Request keys: role, round, case_text, evidence (list of records), claims, objections (full registry),
proposer_turn (latest), other_critic_objections, retry_errors (list, only on the one retry).

NEW-OBJECTION RULE (code decides, not the model):
  key = (target_claim, type).
  An objection is NEW only if its key was never raised before in this run (answered or not),
  or if its severity is HIGHER than the highest severity already logged for that key.
  Same key with same or lower severity = duplicate: logged, never counted, never added again.
  A higher severity is added as a new entry that points to the older one ("supersedes").
  Two objections with the same key in one round: the first counts, the second is a duplicate
  unless its severity is higher.

STATUS of an objection: unresolved (default) | accepted | resolved.
  Proposer reply "accept" -> accepted. "rebut" or "partly" -> stays unresolved (a rebuttal
  is the proposer's word, not agreement). "resolved" is set only when the critic who raised the
  objection withdraws it in a LATER round, in the schema field `withdrawals` (objection_id +
  reason); the log records who and why. A critic cannot withdraw another critic's objection,
  an objection of the same round, or one that is not "unresolved". A human reviewer can set
  "resolved" with mark_resolved() or reopen with reopen() (back to "unresolved"); both are
  logged. The proposer can never delete or edit an objection; only status changes, and each
  change is logged.
"""
import json
import time
from pathlib import Path

from debate import schema

SEVERITY_RANK = {"minor": 1, "major": 2, "critical": 3}
STATUSES = ("unresolved", "accepted", "resolved")
HARD_MAX_ROUNDS = 6
DISCLAIMER = ("Research and demonstration software. Not a medical device. "
              "Not clinical advice. Synthetic cases only.")


class RunLog:
    """Append-only JSONL. One file per run. Never rewrites, never opens an existing run file."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # 'x' = fail if the file exists: a run never overwrites or reuses another run's log.
        self._fh = open(self.path, "x", encoding="utf-8")
        self.n = 0

    def write(self, kind, **data):
        self.n += 1
        rec = {"seq": self.n, "kind": kind}
        rec.update(data)
        self._fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._fh.flush()
        return rec

    def close(self):
        self._fh.close()


def read_log(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


class Registry:
    """All objections of one run. Append-only; only status changes."""

    def __init__(self):
        self.items = []

    def classify(self, target_claim, otype, severity):
        """Return (is_new, supersedes_id or None). Pure rule, see module docstring."""
        same = [o for o in self.items if (o["target_claim"], o["type"]) == (target_claim, otype)]
        if not same:
            return True, None
        top = max(same, key=lambda o: SEVERITY_RANK[o["severity"]])
        if SEVERITY_RANK[severity] > SEVERITY_RANK[top["severity"]]:
            return True, top["id"]
        return False, None

    def add(self, obj, raised_by, rnd, supersedes):
        item = {"id": f"O{len(self.items) + 1}", "raised_id": obj["id"], "raised_by": raised_by,
                "round": rnd, "target_claim": obj["target_claim"], "type": obj["type"],
                "text": obj["text"], "severity": obj["severity"],
                "evidence_ref": obj["evidence_ref"], "status": "unresolved",
                "supersedes": supersedes}
        self.items.append(item)
        return item

    def get(self, oid):
        for o in self.items:
            if o["id"] == oid:
                return o
        return None


def check_turn(turn, role, rnd, evidence_ids, claim_ids):
    """Schema check plus the checks code can do: right role/round, E ids exist, claim exists."""
    errors = schema.validate_turn(turn)
    if errors:
        return errors
    errors = []
    if turn["role"] != role:
        errors.append(f"$.role: expected {role}, got {turn['role']}")
    if turn["round"] != rnd:
        errors.append(f"$.round: expected {rnd}, got {turn['round']}")

    def ref_ok(ref, where):
        if ref != "NONE" and ref not in evidence_ids:
            errors.append(f"{where}: {ref} is not in the evidence list")

    if role == "proposer":
        for i, c in enumerate(turn["claims"]):
            ref_ok(c["evidence_ref"], f"$.claims[{i}].evidence_ref")
        for i, r in enumerate(turn.get("replies", [])):
            ref_ok(r["evidence_ref"], f"$.replies[{i}].evidence_ref")
    else:
        for i, o in enumerate(turn["objections"]):
            ref_ok(o["evidence_ref"], f"$.objections[{i}].evidence_ref")
            if o["target_claim"] not in claim_ids:
                errors.append(f"$.objections[{i}].target_claim: {o['target_claim']} is not a known claim")
    return errors


def run_debate(case_text, evidence, proposer, critic_dx, critic_plan, log_path,
               max_rounds=4, time_limit_s=900, clock=time.monotonic, config=None,
               output_path=None):
    """Run one debate with the given model callables. Returns the result dict."""
    if not isinstance(max_rounds, int) or not 1 <= max_rounds <= HARD_MAX_ROUNDS:
        raise ValueError(f"max_rounds must be 1..{HARD_MAX_ROUNDS}")
    log = RunLog(log_path)
    reg = Registry()
    ev_records = list(evidence.records)
    ev_ids = {r["id"] for r in ev_records}
    started = clock()
    log.write("run_start", disclaimer=DISCLAIMER, max_rounds=max_rounds,
              time_limit_s=time_limit_s, config=config or {}, banners=evidence.banners())
    log.write("evidence", **evidence.to_dict())

    state = {"proposer_turn": None, "claims": set(), "invalid_streak": 0, "turns": 0}
    stop = None

    def ask(model, role, rnd, extra):
        """One model turn with one retry. Returns the valid turn or None (invalid)."""
        req = {"role": role, "round": rnd, "case_text": case_text, "evidence": ev_records,
               "claims": sorted(state["claims"]), "objections": [dict(o) for o in reg.items],
               "proposer_turn": state["proposer_turn"], "retry_errors": []}
        req.update(extra)
        errors = []
        for attempt in (1, 2):
            try:
                turn = model(dict(req, retry_errors=list(errors)))
            except Exception as exc:  # a crashing model is an invalid turn, not a crashed run
                turn, errors = None, [f"model raised {type(exc).__name__}: {str(exc)[:200]}"]
            else:
                claim_ids = state["claims"] | (
                    {c["id"] for c in turn.get("claims", [])} if isinstance(turn, dict) and role == "proposer"
                    and isinstance(turn.get("claims"), list) else set())
                errors = check_turn(turn, role, rnd, ev_ids, claim_ids)
            state["turns"] += 1
            if not errors:
                log.write("turn", role=role, round=rnd, attempt=attempt, valid=True, turn=turn)
                state["invalid_streak"] = 0
                return turn
            log.write("turn", role=role, round=rnd, attempt=attempt, valid=False,
                      errors=errors, turn=turn if isinstance(turn, dict) else repr(turn))
        state["invalid_streak"] += 1
        log.write("turn_invalid", role=role, round=rnd, errors=errors)
        return None

    def timed_out():
        return clock() - started >= time_limit_s

    def apply_replies(turn, rnd):
        for r in turn.get("replies", []):
            o = reg.get(r["objection_id"])
            if o is None:
                log.write("reply_ignored", round=rnd, objection_id=r["objection_id"],
                          reason="unknown objection id")
                continue
            old = o["status"]
            new = "accepted" if r["response"] == "accept" else old
            if new != old:
                o["status"] = new
            log.write("status", round=rnd, objection_id=o["id"], response=r["response"],
                      old=old, new=o["status"], by="proposer", text=r["text"],
                      evidence_ref=r["evidence_ref"])

    def apply_withdrawals(turn, rnd):
        for w in turn.get("withdrawals", []):
            o = reg.get(w["objection_id"])
            if o is None:
                reason = "unknown objection id"
            elif o["raised_by"] != turn["role"]:
                reason = "only the critic who raised an objection can withdraw it"
            elif o["round"] >= rnd:
                reason = "an objection can be withdrawn only in a later round"
            elif o["status"] != "unresolved":
                reason = f"objection is {o['status']}, not unresolved"
            else:
                o["status"] = "resolved"
                o["resolved_by"] = turn["role"]
                o["resolved_reason"] = w["reason"]
                log.write("status", round=rnd, objection_id=o["id"], response="withdrawn",
                          old="unresolved", new="resolved", by=turn["role"], text=w["reason"])
                continue
            log.write("withdrawal_ignored", round=rnd, objection_id=w["objection_id"],
                      by=turn["role"], reason=reason)

    def take_objections(turn, rnd):
        """Count NEW objections by the code rule; log every one."""
        new = 0
        for obj in turn["objections"]:
            is_new, sup = reg.classify(obj["target_claim"], obj["type"], obj["severity"])
            if is_new:
                item = reg.add(obj, turn["role"], rnd, sup)
                new += 1
                log.write("objection", new=True, **item)
            else:
                log.write("objection", round=rnd, new=False, raised_by=turn["role"],
                          target_claim=obj["target_claim"], type=obj["type"],
                          severity=obj["severity"], raised_id=obj["id"])
        return new

    rnd = 0
    while stop is None:
        rnd += 1
        if timed_out():
            stop = ("timeout", rnd - 1 or 1, "run time limit reached before the round", 0)
            break
        prop_extra = {}
        pturn = ask(proposer, "proposer", rnd, prop_extra)
        if pturn is not None:
            state["proposer_turn"] = pturn
            state["claims"] |= {c["id"] for c in pturn["claims"]}
            apply_replies(pturn, rnd)
        if state["invalid_streak"] >= 2:
            stop = ("invalid_turn", rnd, "two invalid turns in a row", 0)
            break
        if pturn is None and state["proposer_turn"] is None:
            # No proposal yet: critics have nothing to attack.
            stop = ("invalid_turn", rnd, "proposer gave no valid first turn", 0)
            break
        prior = {"critic_dx": [dict(o) for o in reg.items], "critic_plan": [dict(o) for o in reg.items]}
        new_count, flags = 0, []
        for role, model, other in (("critic_dx", critic_dx, "critic_plan"),
                                   ("critic_plan", critic_plan, "critic_dx")):
            if timed_out():
                break
            extra = {"other_critic_objections": [] if rnd == 1 else
                     [dict(o) for o in prior[other] if o["raised_by"] == other]}
            cturn = ask(model, role, rnd, extra)
            if state["invalid_streak"] >= 2:
                stop = ("invalid_turn", rnd, "two invalid turns in a row", new_count)
                break
            if cturn is None:
                flags.append(False)
                continue
            apply_withdrawals(cturn, rnd)
            new_count += take_objections(cturn, rnd)
            flags.append(bool(cturn["no_new_objection"]))
        if stop:
            break
        if timed_out():
            stop = ("timeout", rnd, "run time limit reached", new_count)
        elif len(flags) == 2 and all(flags):
            stop = ("converged", rnd, "both critics report no new objection", new_count)
        elif new_count == 0:
            stop = ("converged", rnd, "the round added zero new objections (code check)", 0)
        elif rnd >= max_rounds:
            stop = ("max_rounds", rnd, f"max_rounds ({max_rounds}) reached", new_count)

    status, srnd, reason, n_new = stop
    stop_rec = {"role": "stop", "round": max(1, min(srnd, HARD_MAX_ROUNDS)), "status": status,
                "reason": reason, "new_objections_this_round": n_new}
    errs = schema.validate(stop_rec, schema.STOP)
    assert not errs, errs
    log.write("stop", **stop_rec)
    result = build_result(reg, state["proposer_turn"], stop_rec, evidence, log.path)
    result["case_text"] = case_text
    log.write("result_summary", dissent=result["dissent"], box_ids=[o["id"] for o in result["box"]],
              counts=result["counts"])
    log.close()
    if output_path is not None:  # step 6: Markdown output per run (debate/output.py)
        from debate import output
        result["output_path"] = str(output.write_markdown(result, output_path))
    return result


def build_result(reg, proposer_turn, stop_rec, evidence, log_path):
    items = [dict(o) for o in reg.items]
    box = [o for o in items if o["status"] == "unresolved" or o["severity"] == "critical"]
    counts = {s: sum(1 for o in items if o["status"] == s) for s in STATUSES}
    return {
        "disclaimer": DISCLAIMER,
        "status": stop_rec["status"], "stop": stop_rec,
        "final_proposal": proposer_turn,
        "objections": items,          # the full table: every objection ever raised, none removed
        "box": box,                   # unresolved + critical, shown at the top even if rebutted
        "dissent": "yes" if any(o["status"] == "unresolved" for o in items) else "no",
        "counts": counts,
        "banners": evidence.banners(),
        "evidence": [dict(r) for r in evidence.records],
        "log_path": str(log_path),
    }


def mark_resolved(result, log_path, objection_id, by, note):
    """Human reviewer sets 'resolved'. Appended to the log; the objection stays in the table."""
    return _human_status(result, log_path, objection_id, by, note, "resolved")


def reopen(result, log_path, objection_id, by, note):
    """Human reviewer reopens an objection (any status -> 'unresolved'). Logged."""
    return _human_status(result, log_path, objection_id, by, note, "unresolved")


def _human_status(result, log_path, objection_id, by, note, new):
    if not str(by).strip() or not str(note).strip():
        raise ValueError("a reviewer name and a note are required")
    for o in result["objections"]:
        if o["id"] == objection_id:
            old, o["status"] = o["status"], new
            if new == "resolved":
                o["resolved_by"], o["resolved_reason"] = by, note
            else:
                o.pop("resolved_by", None)
                o.pop("resolved_reason", None)
                o["reopened_by"], o["reopen_reason"] = by, note
            with open(log_path, "a", encoding="utf-8") as fh:  # append only
                fh.write(json.dumps({"kind": "status", "objection_id": objection_id, "old": old,
                                     "new": new, "by": by, "text": note}) + "\n")
            result["box"] = [x for x in result["objections"]
                             if x["status"] == "unresolved" or x["severity"] == "critical"]
            result["dissent"] = "yes" if any(x["status"] == "unresolved"
                                             for x in result["objections"]) else "no"
            return o
    raise KeyError(objection_id)

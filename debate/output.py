"""Markdown output for one debate run (SPEC sections 3, 4, 6).

Research and demonstration software. Not a medical device. Synthetic cases only.

Shows: case summary, final proposal, every claim with its citation and evidence level
(or "NO EVIDENCE FOUND"), a disagreement box with every unresolved objection, the
"NOT REVIEWED" banner and the disclaimer at the top and the bottom.
Code checks that a cited E id exists and that a PMID is well formed (adapters/citations.py).
Code does NOT check that the source supports the claim. A reviewer does. The page says so.
"""
from pathlib import Path

from adapters import citations
from debate import evidence as ev
from debate.loop import DISCLAIMER, SEVERITY_RANK

NOT_REVIEWED = "NOT REVIEWED. A named human reviewer has not signed off this output."
LIMIT_NOTE = ("Limit: the code checks that each cited evidence id exists and that each PMID is "
              "well formed. It does not check that the source supports the claim. A reviewer must.")


def _cell(text):
    """One safe table cell: no pipes, no line breaks."""
    return " ".join(str(text).replace("|", "\\|").split())


def _quote(text):
    return "\n".join("> " + line for line in str(text).strip().splitlines()) or ">"


def describe_ref(ref, by_id, bad_refs):
    """Text for one citation: evidence id, source, level, year; or NO EVIDENCE FOUND."""
    if ref == "NONE":
        return f"**{ev.NO_EVIDENCE}**"
    rec = by_id.get(ref)
    if rec is None or ref in bad_refs:
        return f"**INVALID CITATION** ({_cell(ref)} is not a valid entry in the evidence list)"
    lvl = rec["level"]
    level = f"level {lvl}, {ev.LEVEL_NAMES[lvl]}" if isinstance(lvl, int) else "level unknown"
    where = rec["ref"]
    if rec["source"] == "pubmed":
        url = citations.pubmed_url(str(rec["ref"]).replace("PMID", "").strip())
        where = f"{rec['ref']} ({url})" if url else rec["ref"]
    parts = [str(where), level]
    if rec.get("year"):
        parts.append(str(rec["year"]))
    if rec.get("preprint"):
        parts.append("PREPRINT, not peer reviewed")
    return _cell(f"{ref}: " + ", ".join(parts))


def render_markdown(result):
    proposal = result.get("final_proposal")
    records = result.get("evidence", [])
    by_id = {r["id"]: r for r in records}
    claims = proposal["claims"] if proposal else []
    objs = result["objections"]

    # citation check (adapters/citations.py) on claims and objections
    refs = [c["evidence_ref"] for c in claims] + [o["evidence_ref"] for o in objs]
    bad = {f["ref"] for f in citations.check_evidence_refs(refs, records)}

    unsupported = sum(1 for c in claims if c["evidence_ref"] == "NONE" or c["evidence_ref"] in bad)
    box = sorted(result["box"], key=lambda o: -SEVERITY_RANK[o["severity"]])
    unresolved = [o for o in objs if o["status"] == "unresolved"]

    L = []
    add = L.append
    add("# Clinical debate output (simulation)")
    add("")
    add(f"> **{NOT_REVIEWED}**")
    add(f"> {DISCLAIMER}")
    for b in result.get("banners", []):
        add(f"> **Banner:** {b}")
    add("")
    add(f"Ending status: **{result['status']}** ({result['stop']['reason']}, round "
        f"{result['stop']['round']}). Dissent: **{result['dissent']}**.")
    add("")
    add("## 1. Case summary")
    add("")
    add(_quote(result.get("case_text", "(case text not stored)")))
    add("")

    add("## 2. Disagreement box")
    add("")
    if box:
        add("> **DISAGREEMENT. Read this before the proposal.**")
        add(f"> {len(unresolved)} unresolved objection(s). The box also lists every critical "
            "objection, even if the proposer accepted or rebutted it.")
        add(">")
        for o in box:
            add(f"> - **{o['id']}** [{o['severity'].upper()}, **{o['status']}**] "
                f"{o['raised_by']}, round {o['round']}, claim {o['target_claim']}, "
                f"type {o['type']}: {_cell(o['text'])}")
            add(f">   Evidence: {describe_ref(o['evidence_ref'], by_id, bad)}")
    else:
        add("> No unresolved or critical objections. This does not mean the proposal is right.")
    add("")

    add("## 3. Final proposal")
    add("")
    if not proposal:
        add("No valid proposal was produced.")
    else:
        d = proposal["diagnosis"]
        add(f"The leading hypothesis in this simulation is: **{_cell(d['leading'])}** "
            f"(confidence: {d['confidence']}).")
        if d["alternatives"]:
            add("")
            add("Alternatives: " + "; ".join(_cell(a) for a in d["alternatives"]) + ".")
        add("")
        add("Plan (a discussion aid, not an order):")
        add("")
        for i, p in enumerate(proposal["plan"], 1):
            add(f"{i}. {_cell(p['step'])} (why: {_cell(p['why'])})")
        if proposal["open_gaps"]:
            add("")
            add("Open gaps (missing information): "
                + "; ".join(_cell(g) for g in proposal["open_gaps"]))
    add("")

    add("## 4. Claims, citations and evidence level")
    add("")
    add("| Claim | Text | Citation and evidence level |")
    add("|---|---|---|")
    for c in claims:
        add(f"| {c['id']} | {_cell(c['text'])} | {describe_ref(c['evidence_ref'], by_id, bad)} |")
    add("")
    add(f"Claims without evidence: **{unsupported} of {len(claims)}**.")
    add("")
    add(LIMIT_NOTE)
    add("")

    add("## 5. All objections")
    add("")
    add("| ID | Raised by | Round | Claim | Type | Severity | Status | Evidence | Why this status |")
    add("|---|---|---|---|---|---|---|---|---|")
    for o in objs:
        why = ""
        if o.get("resolved_by"):
            why = f"resolved by {o['resolved_by']}: {o.get('resolved_reason', '')}"
        elif o.get("reopened_by"):
            why = f"reopened by {o['reopened_by']}: {o.get('reopen_reason', '')}"
        add(f"| {o['id']} | {o['raised_by']} | {o['round']} | {o['target_claim']} | {o['type']} | "
            f"{o['severity']} | {o['status']} | {describe_ref(o['evidence_ref'], by_id, bad)} | "
            f"{_cell(why)} |")
    if not objs:
        add("| (none) | | | | | | | | |")
    add("")
    add(f"Counts: {result['counts']}. Full turn log: `{result['log_path']}`.")
    add("")
    add("---")
    add(f"**{NOT_REVIEWED}**")
    add("")
    add(DISCLAIMER)
    add("")
    return "\n".join(L)


def write_markdown(result, path):
    """Write the Markdown file. Fails if the file exists (one file per run)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "x", encoding="utf-8") as fh:
        fh.write(render_markdown(result))
    return p

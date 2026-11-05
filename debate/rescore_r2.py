"""Read-only rescore of a finished run under the R2 must-catch rule (warns/objects only).
Never writes into the run folder. Usage: python -m debate.rescore_r2 eval/runs/overnight-1 eval/rescored/overnight-1_r2"""
import json
import sys
from pathlib import Path

from debate import eval as ev


def rescore(run_dir, out_dir):
    cases = ev.load_cases()
    cmap = {c["id"]: c for c in cases}
    results = [r for r in ev.load_results(run_dir) if r["repeat"] == 0 and r["case_id"] in cmap]
    rows = []
    for r in sorted(results, key=lambda r: (r["case_id"], r["arm"])):
        if r["arm"] not in ("A", "B"):
            continue
        for x in ev.caught_items(cmap[r["case_id"]], r):
            rows.append({"case": r["case_id"], "arm": r["arm"], "item": x["id"], "category": cmap[r["case_id"]]["category"],
                         "old_mention": x["mentioned"], "new_caught": x["caught"], "stance": x["stance"],
                         "sentence": x["sentence"]})
    tot = sum(1 for r in rows if r["arm"] == "A")
    L = ["# Rescore of " + Path(run_dir).name + " under the R2 must-catch rule (code screen only)", "",
         "Read-only. No model run. The human score is the main outcome; none exists yet.", "",
         "| Arm | Items | Old rule (mention) | New rule (warns/objects) | Check by eye (not counted) |", "|---|---|---|---|---|"]
    for arm in ("A", "B"):
        rs = [r for r in rows if r["arm"] == arm]
        L.append(f"| {arm} | {len(rs)} | {sum(r['old_mention'] for r in rs)} | {sum(r['new_caught'] for r in rs)} | "
                 f"{sum(r['stance'] == 'check by eye' for r in rs)} |")
    L += ["", "## Items that changed (old caught, new not caught)", ""]
    for r in rows:
        if r["old_mention"] and not r["new_caught"]:
            L.append(f"- {r['arm']} {r['case']} {r['item']}: {r['stance']}: \"{r['sentence']}\"")
    L += ["", "## Items caught under the new rule", ""]
    L += [f"- {r['arm']} {r['case']} {r['item']}: \"{r['sentence']}\"" for r in rows if r["new_caught"]]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rescore_r2.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "rescore_r2.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return rows


if __name__ == "__main__":
    rescore(sys.argv[1], sys.argv[2])

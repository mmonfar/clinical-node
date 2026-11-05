"""Live run of the local agents on the synthetic eval cases (offline evidence).

Usage (from the clinical-node folder, with its venv):
    python eval/run_local.py                 # all cases, one subprocess each
    python eval/run_local.py --case eval/cases/c01_cap_easy.json   # one case

What it does
- Calls the real engine functions with the local Ollama models.
- PubMed is switched off: every search returns no articles. The Researcher
  therefore summarises an empty evidence set. This tests the agents, not search.
- Minutes and the case store are written to a temporary folder, not the repo.
- Output: eval/local_run_results.json (valid yes/no and seconds per agent).
Research and demonstration software. Not a medical device. Synthetic cases only.
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = sorted((ROOT / "eval" / "cases").glob("c*.json"))
OUT = ROOT / "eval" / "local_run_results.json"
CASE_TIMEOUT = 1500  # seconds per case


def run_one(case_path: Path) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="cn_local_"))
    os.environ["ENTREZ_EMAIL"] = "synthetic@example.invalid"  # never used: no search runs
    os.environ["CLINICAL_NODE_RUN_LOG"] = str(tmp / "llm_runs.jsonl")
    sys.path.insert(0, str(ROOT))
    import dotenv
    dotenv.load_dotenv = lambda *a, **k: False  # do not read any .env file
    import pubmed_client
    for name in ("search_clinical_evidence", "search_mid_tier_evidence",
                 "search_case_studies"):
        setattr(pubmed_client, name, lambda *a, **k: [])
    import state_manager
    state_manager.CASES_FILE = tmp / "cases.json"
    state_manager.MINUTES_DIR = tmp / "minutes"
    import clinical_engine as ce
    import cron_refine

    case = json.loads(case_path.read_text(encoding="utf-8"))
    cid = case["id"]
    res = {"case": cid, "agents": {}}

    def step(name, fn, check):
        t0 = time.time()
        entry = {"valid": False, "seconds": None, "problem": ""}
        val = None
        try:
            val = fn()
            ok, why = check(val)
            entry["valid"], entry["problem"] = ok, why
        except Exception as exc:  # report plainly, keep going
            entry["problem"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        entry["seconds"] = round(time.time() - t0, 1)
        res["agents"][name] = entry
        return val

    def chk_sbar(s):
        keys = ("situation", "background", "assessment", "recommendation")
        if not isinstance(s, dict):
            return False, "not an object"
        miss = [k for k in keys if not str(s.get(k) or "").strip()]
        return (not miss), ("empty: " + ",".join(miss)) if miss else ""

    sbar = step("sbar", lambda: ce.parse_sbar_from_text(case["case_text"]), chk_sbar)
    if not isinstance(sbar, dict):
        return res
    holder = {}

    def researcher():
        # Researcher = query planning (pillar split) + empty-evidence synthesis.
        holder["ev"] = ce.researcher_search(ce.build_pubmed_query(sbar), sbar=sbar)
        return ce.researcher_synthesize(sbar, holder["ev"])
    synth = step("researcher", researcher,
                 lambda s: (isinstance(s, str) and len(s.strip()) >= 80,
                            "" if isinstance(s, str) and len(s.strip()) >= 80 else "empty or very short"))
    if not isinstance(synth, str):
        # Query planning failed. Keep going so the other agents are still tested:
        # synthesise from an empty evidence set (own row, so nothing is hidden).
        holder["ev"] = {"tier": "none", "articles": [], "query": "",
                        "is_multi_pillar": False, "pillars": []}
        synth = step("researcher_synthesis_only",
                     lambda: ce.researcher_synthesize(sbar, holder["ev"]),
                     lambda s: (isinstance(s, str) and len(s.strip()) >= 80,
                                "" if isinstance(s, str) and len(s.strip()) >= 80 else "empty or very short"))
        if not isinstance(synth, str):
            return res
    evidence = holder["ev"]
    ref_list = ce._build_ref_list(evidence.get("articles", []))

    def chk_mdt(m):
        if not isinstance(m, dict):
            return False, "not an object"
        rt = m.get("roundtable")
        if not isinstance(rt, list) or not rt:
            return False, "no roundtable"
        if not all(isinstance(e, dict) and e.get("specialist") and e.get("statement") for e in rt):
            return False, "roundtable entry lacks specialist or statement"
        if not str(m.get("final_recommendation") or "").strip():
            return False, "no final_recommendation"
        why = ""
        if any(e.get("citations") for e in rt):
            why = "cites reference numbers although no references exist (offline)"
        return True, why

    mdt = step("mdt", lambda: ce.mdt_roundtable_review(sbar, synth, ref_list), chk_mdt)
    if not isinstance(mdt, dict):
        return res
    out = ce.build_output(cid, sbar, evidence, synth, mdt)
    res["mdt_specialists"] = mdt.get("selected_specialists")
    res["mdt_final"] = str(mdt.get("final_recommendation"))[:300]
    minutes = step("auditor", lambda: ce.auditor_record(cid, out),
                   lambda s: (isinstance(s, str) and len(s.strip()) >= 300 and "#" in s,
                              "" if isinstance(s, str) and len(s.strip()) >= 300 and "#" in s else "empty, short or no headings"))
    if not isinstance(minutes, str):
        return res

    def refine():
        # Synthetic new article that clearly contradicts a typical plan.
        arts = [{"title": "Synthetic trial: the usual first-line plan was harmful",
                 "year": "2026", "journal": "Synthetic Journal",
                 "abstract": "Invented abstract for a software test. The standard first-line plan "
                             "increased harm compared with no treatment."}]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            r = cron_refine._check_contradiction(minutes, arts)
        if "failed" in err.getvalue():
            raise RuntimeError("model call or JSON failed (swallowed by the check): " + err.getvalue()[:150])
        return r
    step("refine72h", refine,
         lambda r: (isinstance(r, tuple) and len(r) == 2 and isinstance(r[0], bool), ""))
    return res


def main() -> None:
    if "--case" in sys.argv:
        r = run_one(Path(sys.argv[sys.argv.index("--case") + 1]))
        print("RESULT_JSON " + json.dumps(r))
        return
    results = []
    for cp in CASES:
        t0 = time.time()
        try:
            p = subprocess.run([sys.executable, str(Path(__file__)), "--case", str(cp)],
                               capture_output=True, text=True, timeout=CASE_TIMEOUT, cwd=str(ROOT))
            line = [l for l in p.stdout.splitlines() if l.startswith("RESULT_JSON ")]
            r = json.loads(line[0][12:]) if line else {"case": cp.stem, "agents": {},
                                                         "error": (p.stderr or "no output")[-300:]}
        except subprocess.TimeoutExpired:
            r = {"case": cp.stem, "agents": {}, "error": f"timeout after {CASE_TIMEOUT}s"}
        r["case_seconds"] = round(time.time() - t0, 1)
        results.append(r)
        OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(cp.stem, r["case_seconds"], flush=True)


if __name__ == "__main__":
    main()

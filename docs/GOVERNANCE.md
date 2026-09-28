# Clinical Intelligence Node: model governance

> **Report to the Executive Director (C5, 2026-09-28; SendMessage unreachable):**
> Shipped this page, an append-only JSONL run log in `complete()` (no prompt text), and a
> PMID/[N] citation checker (built, not wired). Prompts and behaviour are unchanged.
> pytest 18/18 (10 new, fake client, synthetic data), no key or network. Commits `420d43c`,
> `192240b` and this one; no push. Main gaps: "full audit trail" is overstated, model ids float,
> no eval set, no clinician feedback, no PHI guard, no UI disclaimer, silent cron failure.
> Backlog C5-1..9 added; board C5 done; CEO Checklist: `mm-gov-linkedin`, `mm-gov-priority`.
> Suggested next: C5-6 PHI guard + C5-7 disclaimer.

How the virtual M&M committee harnesses the LLM, how its runs are audited,
how feedback flows, and what is not in place yet. Written from the code on
2026-09-28 (commit `192240b`). Every "in place" claim below points to a file
or a test. If the code and this page disagree, the code wins: fix the page.

**This is a prototype decision-support aid, not a medical device and not
clinical advice.** Every case used to build and test it is fictional.

---

## 1. How the model is harnessed (as built)

**Pipeline** (`clinical_engine.run_committee`, and step by step in `app.py`):

| Step | Function | Model | Temp | Output |
|---|---|---|---|---|
| SBAR extraction | `parse_sbar_from_text` | gpt-4o-mini | 0.0 | JSON |
| PubMed query | `build_pubmed_query` | gpt-4o-mini | 0.0 | text |
| Pillar queries (thin evidence only) | `build_pillar_queries` | gpt-4o-mini | 0.0 | JSON |
| Researcher synthesis | `researcher_synthesize` | gpt-4o-mini | 0.0 | text, cites `[N]` |
| MDT roundtable | `mdt_roundtable_review` | gpt-4o | 0.25 | JSON, `citations: list[int]` |
| Auditor minutes | `auditor_record` | gpt-4o-mini | 0.0 | Markdown |
| 72-h contradiction check | `cron_refine._check_contradiction` | gpt-4o | 0.0 | JSON |

- **One entry point.** All 7 calls go through `adapters/llm.complete()`: one
  lazily built client, 60 s timeout, OpenAI SDK default of 2 retries
  (`tests/test_llm_adapter.py`).
- **Parameters.** No `max_tokens`, no `seed`. Model ids are aliases
  (`gpt-4o`, `gpt-4o-mini`), not dated snapshots, so the provider can change
  the model underneath. Since `420d43c` the *returned* model id is logged per
  call, so a silent change is at least visible.
- **Prompts** are inline string literals in `clinical_engine.py` and
  `cron_refine.py`. They are versioned by git only; there is no prompt id.
  The roundtable prompt hard-codes reversal-agent and CrCl renal-dosing checks.

**Evidence ladder** (`researcher_search`, filters in `pubmed_client.py`):
Tier 1 RCT / meta-analysis / systematic review / practice guideline (≥ 3 hits
wins) → if < 2 hits, **multi-pillar** search (A conflict, B guidelines with a
`Practice Guideline[pt]` retry, C procedure; each pillar walks the ladder;
de-duplicated by PMID) → Tier 1b society-consensus anchor → Tier 2 clinical
trial / observational → Tier 3 case reports. Max 5 articles per search,
abstracts truncated to 350–400 characters in the prompt. The tier label is
the *search filter that returned results*, not an appraisal of each paper.

**Citations.** Articles carry their PMID from PubMed `efetch`; the URL is
built from that PMID (`pubmed_client._build_url`), so the reference list is
real by construction. The models cite by number. Gaps: nothing checks that a
cited `[N]` exists or that the paper supports the claim, and the Auditor
re-writes the reference list as free text, so a URL in the minutes is not
guaranteed to match the one retrieved. `adapters/citations.py` now flags
malformed PMIDs, URL/PMID mismatches, uncited roundtable statements and
out-of-range `[N]` (`tests/test_citations.py`), but it is **not wired into
the UI or minutes yet** and does not query PubMed.

**Output safety.** Model and PubMed text is HTML-escaped with `app._e()`
(36 call sites) and links pass `_safe_url()` (http/https only) before any
`unsafe_allow_html` render (`tests/test_escaping.py`, incl. a hostile
`<img onerror>`).

**Errors.** PubMed failures raise `RuntimeError`; the app catches any
exception, shows it, and stops the run. Model JSON is parsed with
`json.loads` and not schema-validated. In `cron_refine`, a failed
contradiction check returns "no contradiction" and only prints to stderr —
a failure reads the same as a clean result (gap S2 below).

## 2. How runs are audited

| Record | Where | Append-only? | Holds |
|---|---|---|---|
| LLM run log | `logs/llm_runs.jsonl` (git-ignored) | yes | time, model requested/returned, params, prompt SHA-256, latency, tokens, ok/error — **no prompt text** |
| Minutes | `minutes/<case>.md` (git-ignored) | yes (file append) | Auditor minutes + 72-h dissent blocks, timestamp, author label |
| Case record | `cases.json` (git-ignored) | **no** (upsert, overwritten each run) | SBAR, evidence, synthesis, roundtable, status |

The run log (`adapters/llm.py`, `tests/test_run_log.py`) makes cost, latency
and model drift measurable. What it cannot do yet: link a call to a case
(no run id), or reproduce a run (prompt text is not stored, by design, and
the model alias floats). The minutes' author line is a hard-coded label
("Auditor (GPT-4o-mini)"), not the model id actually returned.

## 3. How feedback flows

- **Machine → human:** every 72 h `cron_refine.py` re-queries PubMed; if
  gpt-4o judges new articles contradictory, the case becomes `needs_review`
  and a dissent block is appended to its minutes.
- **Human → system: nothing is captured.** There is no rating, correction or
  sign-off; a clinician's judgement of an output is not stored anywhere and
  cannot improve prompts. This is the biggest gap for a credible M&M claim.

## 4. Data handling

- Free text typed into the chat goes to the OpenAI API (a third party) as-is.
  **There is no de-identification.** Nothing stops a user pasting real
  patient details; only the README disclaimer says not to.
- Runtime data (`cases.json`, `minutes/`, `logs/`) stays on the local disk
  and is git-ignored. The repo is on `NEVER_ONLINE`.
- The app UI shows **no** not-clinical-advice or no-real-data notice today.

## 5. Gap analysis

| Area | Status | Gap |
|---|---|---|
| Reproducibility | partial | model aliases float; no seed; prompts only in git; no run id |
| Audit trail | partial | run log + minutes append-only; case record overwritten |
| Grounding / citations | partial | real PMIDs by construction; checker exists but unwired; no claim-support check |
| Evaluation | **none** | no synthetic case set, no scoring on change |
| Human feedback | **none** | no rating/correction capture or review |
| Safety: prompt injection | **none** | abstracts and case text enter prompts undelimited |
| Safety: hallucination / over-confidence | partial | cite-by-number rule in prompts; no wording check, no confidence language rule |
| Safety: disclaimer | partial | README only; not in UI or minutes |
| Privacy | partial | local storage; **no PHI guard before the API call** |
| Cost / latency | in place (measure) | logged per call; no budget or alert |
| Failure visibility | partial | cron failure is silent (reads as "no contradiction") |

**Sources.** The brain (`refs_books`) has **no** sources on LLM governance,
evaluation, prompt injection, citation grounding or clinical AI audit
(searched 2026-09-28: 12 queries, only unrelated forecasting/ML hits). This
page rests on the code alone. Adding 2–3 references via `refs_books/_inbox`
(e.g. a clinical-AI reporting guideline and an LLM-evaluation paper) is plan
item C5-8.

## 6. Status table

| Claim | Evidence | Status |
|---|---|---|
| One LLM entry point, lazy client, 60 s timeout | `adapters/llm.py`; `tests/test_llm_adapter.py` | in place |
| Every LLM call appends a metadata record with no prompt text | `adapters/llm.py::_log_run`; `tests/test_run_log.py` | in place |
| Returned model id and token usage are recorded per call | `tests/test_run_log.py::test_complete_appends_metadata_record` | in place |
| Low temperature (0.0; roundtable 0.25) | `clinical_engine.py`, `cron_refine.py` call sites | in place |
| Evidence ladder with multi-pillar fallback | `clinical_engine.researcher_search`, `pubmed_client.py` filters | in place (no test) |
| Reference list uses real PubMed PMIDs/URLs | `pubmed_client._build_url` | in place (no test) |
| Model/PubMed text escaped before HTML render | `app._e`, `app._safe_url`; `tests/test_escaping.py` | in place |
| Minutes are an append-only log | `state_manager.append_minutes` | in place (no test) |
| Citations checked for PMID format and valid `[N]` | `adapters/citations.py`; `tests/test_citations.py` | partial: built, not wired |
| Pinned model snapshots | — | planned (C5-1) |
| Synthetic evaluation set scored on each change | — | planned (C5-3) |
| Reviewer ratings/corrections stored and reviewed | — | planned (C5-4) |
| Prompt-injection hardening | — | planned (C5-5) |
| PHI guard before the API call | — | planned (C5-6) |
| Disclaimer in UI and minutes | — | planned (C5-7) |

## 7. Plan (board backlog, division C)

| # | Item | Effort |
|---|---|---|
| C5-1 | Pin dated model snapshots + `seed`, set `max_tokens`; move prompts to `prompts/` with an id/version logged per call; add a run id linking calls → case | Low |
| C5-2 | Wire `citations.py` into `build_output` + minutes (flag banner); Auditor must not re-write URLs (append the reference block in code) | Low |
| C5-3 | Evaluation harness: 10–15 synthetic cases with expected findings (e.g. reversal agent named, CrCl requested, gap banner fires), fake-LLM unit tests + an opt-in live scored run; score logged per change | Med |
| C5-4 | Reviewer feedback: per-case rating + free-text correction + sign-off in the UI, append-only `feedback.jsonl`, monthly review feeding prompt changes | Med |
| C5-5 | Prompt-injection hardening: delimit abstracts/case text as data, schema-validate model JSON, test with a hostile synthetic abstract | Low |
| C5-6 | PHI guard: regex/NER pre-check (names, dates, IDs, NHS/MRN-like numbers) blocking the API call + UI warning; tests on synthetic identifiers | Med |
| C5-7 | "Not a medical device / not clinical advice / fictional data only" in UI and minutes header (with the licensing rollout backlog row) | Low |
| C5-8 | Brain intake: 2–3 governance references via `refs_books/_inbox` | Low |
| C5-9 | Make cron failures visible (status `check_failed`, not "no contradiction"); make `cases.json` history append-only | Low |

## 8. Proposed LinkedIn wording (for the CEO; the post file is unchanged)

The draft says the Auditor writes minutes "with a full audit trail". Today
that overstates it. Suggested replacement sentences:

> Every model call goes through one gateway that logs which model actually
> answered, its settings, time taken and tokens used — without storing any
> case text. References come straight from PubMed with real PMIDs, and the
> minutes are kept as an append-only record.
>
> What it doesn't do yet: score itself against a benchmark case set, or
> capture a reviewing clinician's corrections. Those are next, and until
> they exist this stays a prototype.

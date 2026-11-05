# SPEC: Clinical debate engine (local critics)

Status: SPEC only, 1 Nov 2026. No code written. Decisions recorded in section 9 (decisions by the author, 1 Nov); sources verified (section 10).
Research and demo software. Not a medical device. Synthetic cases only.

## 1. Goal and non-goals

**Goal.** Add a second mode to clinical-node. One local model proposes a diagnosis and plan. Two local critics hunt for weaknesses. They debate in rounds until no new objection is left. Every claim is tied to evidence. The user sees the whole debate, including what stayed unresolved.

**Where it sits in the M&M (1 Nov).** It is a support tool, not a reviewer. Two uses:
- **Before the M&M (pre-debate):** the debate runs on the case first, so the committee starts with the strongest proposal, the objections and the evidence already on the table.
- **After the M&M (gap finder):** feed it the M&M minutes or the meeting transcript. It compares them with the debate and the evidence and lists gaps: objections nobody answered, claims without evidence, actions without an owner. Build step 10.

**Builds on what exists (do not start over):**
- `clinical_engine.py`: SBAR parsing, `researcher_search`, `run_committee`, `build_output`.
- `pubmed_client.py`: PubMed search and the evidence ladder (RCT/meta-analysis/review, then guidelines, then observational, then case reports).
- `adapters/llm.py`: one entry point for model calls, with a run log (no prompt text). It talks to local Ollama only.
- `adapters/citations.py`: PMID check and `[N]` check (built, not wired; GOVERNANCE R2).
- `docs/GOVERNANCE.md` section 7: R1 (pinned models, seed), R2 (citations wired), R3 (synthetic eval set), R4 (reviewer sign-off), R5 (schema-checked model JSON), R6 (PHI guard), R7 (disclaimer in UI).

**Non-goals.**
- No clinical use. No real patient data. No diagnosis for a real person.
- No cloud model in the debate. Local only (Ollama). The app also runs on Ollama.
- No training or fine-tuning.
- No claim that the debate is "more correct" than one model. We measure it (section 7).
- No new web UI in the first steps. Output is a file and the existing minutes view.

## 2. Roles and turn schema

Three roles. Each turn is one JSON object. The harness rejects anything that does not match the schema. One retry with the error text, then the turn is marked `invalid` and shown as such.

Common fields in every turn: `role`, `round` (int), `turn_id`, `model_id`, `seed`.

**Proposer** (one per case)
```json
{
  "role": "proposer", "round": 1,
  "diagnosis": {"leading": "text", "alternatives": ["text"], "confidence": "low|medium|high"},
  "plan": [{"step": "text", "why": "text"}],
  "claims": [{"id": "C1", "text": "text", "evidence_ref": "E3 | NONE"}],
  "changes_since_last_round": ["text"],
  "open_gaps": ["missing info the case does not give"]
}
```

**Critic A: diagnosis and reasoning.** Looks for anchoring, premature closure, missed differentials, logic gaps.
```json
{
  "role": "critic_dx", "round": 1,
  "objections": [{
    "id": "O1", "target_claim": "C1",
    "type": "missed_differential|anchoring|premature_closure|logic_gap|unsupported_claim|other",
    "text": "text", "severity": "minor|major|critical",
    "evidence_ref": "E5 | NONE"
  }],
  "no_new_objection": false
}
```

**Critic B: treatment plan and safety.** Looks for wrong drug or dose, interactions, missing contraindication checks, missing escalation or follow-up.
Same shape as Critic A. `role` is `critic_plan`. `type` is one of `dose_or_drug|interaction|contraindication|missing_step|harm_risk|unsupported_claim|other`.

**Proposer reply** (round 2 and later) adds, per objection: `{"objection_id": "O1", "response": "accept|rebut|partly", "text": "text", "evidence_ref": "..."}`.

Rules for all roles:
- A critic must name the claim it attacks (`target_claim`). No vague "this seems wrong".
- A claim or objection with `evidence_ref: NONE` is allowed but is shown as "no evidence found" (section 4).
- Free text is data only. Case text and abstracts go in delimited blocks the model is told never to obey (GOVERNANCE R5).

Who plays which role is set in config (section 5). Default: MedGemma proposes; Qwen is Critic A; MedGemma (second instance, other prompt and seed) is Critic B. See open question 2.

## 3. Debate loop

1. **Evidence pass** (section 4) builds an evidence list `E1..En` from the case. All roles see it.
2. **Round 1.** Proposer turn. Then Critic A and Critic B turns (they do not see each other in this round, to avoid copying).
3. **Round 2 and later.** The proposer replies to each objection and may change the plan. Critics read the reply and the other critic, then raise only NEW objections or mark old ones resolved.
4. **New objection** = an objection whose (`target_claim`, `type`) pair is not in the log, or one with higher `severity`. The harness checks this in code, not the model.
5. **Stop rule** (checked by code; any one stops the loop):
   - both critics return `no_new_objection: true`, or
   - a round adds zero new objections by the code check, or
   - `max_rounds` is reached (default 4; hard limit 6), or
   - a turn is `invalid` twice in a row, or
   - the run time limit is reached (default 15 min).
6. **Ending status** is always shown: `converged`, `max_rounds`, `invalid_turn`, `timeout`.

**Disagreement is shown, not hidden.** The final output has:
- the final plan, with the proposer's confidence;
- a table of every objection: who raised it, severity, status (`resolved`, `accepted`, `unresolved`);
- all `unresolved` and `critical` objections at the top, in a box, even if the proposer rebutted them;
- a line "Dissent: yes/no";
- the full turn log (append-only file, like the existing minutes).

The proposer can never delete or edit an objection. Only its status changes, and the change is logged.

## 4. Evidence layer

Search order per claim topic:

1. **Local knowledge base first.** If the environment variable `DEBATE_KB_DIR` names a folder that holds `query_brain.py`, call its `search(query, limit)`. It returns book, file path, heading and snippet. The engine imports it locally, read-only. If `DEBATE_KB_DIR` is unset, there is no local knowledge base and the engine goes straight to PubMed, as on no hit.
2. **PubMed fallback** only if the local knowledge base has no useful hit for that topic. Use `pubmed_client.py` (it already filters by study type and throttles). Network is needed only here. Offline mode = local knowledge base only, with the banner "PubMed not searched".
3. **Rank by level of evidence**, highest first:
   1. Meta-analysis / systematic review
   2. Randomised controlled trial
   3. Practice guideline (named body)
   4. Cohort / case-control
   5. Case series / case report
   6. Expert opinion / textbook (brain book page without a primary study)

   Each item gets a `level` (1-6) from the publication-type tags (PubMed) or the book metadata (brain). If the type is unknown, `level` is `unknown` and the item ranks last. The mapping is a small table in code, covered by tests. A GRADE-style certainty rating is NOT in scope for v1 (see section 10).
4. **Evidence record** (one per item): `{"id": "E3", "source": "brain|pubmed", "ref": "PMID or file path + heading", "level": 1-6|unknown, "year": int, "snippet": "text"}`.

**One citation per claim.** Each claim and each objection carries exactly one `evidence_ref` (the best-ranked item that supports it), or `NONE`. Code checks that the `E` id exists in the list (reuse `adapters/citations.py`: PMID format and `[N]` validity). Code does NOT check that the snippet truly supports the claim; a reviewer does (section 6). The output states this limit.

**No evidence found.** The claim stays, marked "NO EVIDENCE FOUND", and counts in the metric "unsupported claims". It never gets an invented citation. If the local knowledge base and PubMed both return nothing for the whole case, the run still goes, with a top banner: "No evidence retrieved. Treat all output as unsupported."

Prompt rule: models may cite only `E` ids from the list. Anything else fails the schema check.

## 5. Models

Runtime: Ollama on a laptop (16-32 GB RAM), local only, no network for the models.

| Role | Model family | Sizes to try | Note |
|---|---|---|---|
| Proposer, Critic B | MedGemma | small (about 4B) and large (about 27B) | **Check:** which MedGemma sizes and quantised builds exist in the Ollama library, and which are text-only |
| Critic A | Qwen | mid (about 7B-14B) and larger (about 32B) | **Check:** exact Qwen release and tag in Ollama |

Sizes are candidates, NOT verified. Memory rule of thumb, to confirm by test: a 4-bit build needs roughly half a byte per parameter plus working memory. So a 27B-32B model is tight or too big on 16 GB, and two big models at once do not fit. Default plan: load models one at a time (Ollama swaps them); small/mid sizes on 16 GB; larger sizes allowed on 32 GB.

Settings (one config file, logged per turn):
- `temperature` 0.0 to 0.2 (default 0.0 proposer, 0.1 critics).
- `seed` fixed per run (default 42); each role gets its own derived seed.
- `num_ctx` set explicitly; `num_predict` capped.
- JSON output through Ollama's structured-output option (schema passed in), plus our own schema check.
- Model **digest** (not only the tag) recorded in the run log. This closes GOVERNANCE R1 for local models.
- The same seed may not give the same text on different hardware. Step 3 measures this and reports it. We do not promise identical output.

`adapters/llm.py` gets a second backend (Ollama) behind the same `complete()` call and run log. It is now the only backend.

## 6. Safety and governance

- **Disclaimer** on every output page and file header: "Research and demonstration software. Not a medical device. Not clinical advice. Synthetic cases only." (closes GOVERNANCE R7 for this mode).
- **Synthetic cases only.** The input box warns. An identifier check (names, dates of birth, ID-like numbers) blocks the run (GOVERNANCE R6; may start as a simple pattern check).
- **Licence block** unchanged: AGPL-3.0 + commercial on request, CC BY-NC content, Independence and data notice (already in README).
- **Prompt injection:** case text and abstracts are delimited data; model JSON is schema-checked (R5).
- **Logging:** append-only run log per debate: config, model digests, seeds, every turn (valid or not), stop reason, evidence list, time. Prompts live in `prompts/` with id and version, never inline (R1).
- **Wording:** the output never says "the diagnosis is". It says "the leading hypothesis in this simulation is".
- **Reviewer sign-off (R4):** each saved debate starts as `unreviewed`. A named human reviewer sets `reviewed-ok`, `reviewed-needs-change` or `rejected`, with a note, appended to `feedback.jsonl`. Output without sign-off carries the banner "NOT REVIEWED".
- **Link to C5 items.** The brief names "C5-1..C5-5"; GOVERNANCE section 7 lists R1..R9. Mapping used here: pinned models and seeds = R1 (section 5); citations wired = R2 (section 4); synthetic eval set = R3 (section 7); reviewer sign-off = R4 (this section). Step 0 confirms the mapping.
- **Clinical safety case and data-protection note** (company rule R024) are still to write for this mode: step 9.

## 7. Evaluation

**Case set.** 12-15 synthetic cases, written by hand and reviewed by a clinical reviewer. Mix: easy, ambiguous, and "trap" cases (a tempting wrong anchor, a missing contraindication, a missing key fact). Each case has a short answer key: expected leading diagnosis, must-catch objections, must-not-claim items. Stored as JSON in `eval/cases/`. No real patients.

**Compared arms** (same cases, same evidence list):
- A: single local model, one pass.
- B: proposer + critics debate (this spec).
- C (optional): the earlier committee, as a reference.

**Scores** (mostly computed by code):
1. Schema-valid turns, share of all turns.
2. Must-catch objections found (recall against the key).
3. Must-not-claim items avoided.
4. Unsupported claims (`evidence_ref: NONE`) per debate.
5. Invalid citations (id not in list, bad PMID). Must be 0.
6. Converged before `max_rounds`, share of runs.
7. Repeat-run agreement: same case, same seed, 3 runs; same leading diagnosis, share.
8. Human review of a sample of 5 debates: does each cited snippet support its claim (yes/partly/no).

**Pass bar (proposed; to be confirmed, question 4):**
- Items 1, 3 and 5: 100% on the set.
- Item 7: same leading diagnosis in at least 80% of cases.
- Item 2: the debate arm finds at least as many must-catch objections as arm A, and more on the trap cases in total. If not, the debate adds cost and no value, and we say so.
- Item 8: zero "no" in the sample.

These are targets that set the bar, not results. No result exists yet.

## 8. Build steps

Each step is small (about 12-15 tool calls), ends with a check command, and is reviewed before the next. Paths are relative to `clinical-node/`. Steps that need Ollama use a fake model when Ollama is not running.

| # | Step | Check command |
|---|---|---|
| 0 | Confirm model names/sizes in Ollama; map C5/R ids. Write `docs/MODELS.md`. Docs only. | `python -m pytest tests -q` (nothing breaks) |
| 1 | Turn JSON schemas and a validator, with fake good and bad turns. | `python -m pytest tests/test_debate_schema.py -q` |
| 2 | Ollama backend in `adapters/llm.py` (same `complete()` and run log; digest and seed logged). HTTP mocked in tests. | `python -m pytest tests/test_llm_adapter.py tests/test_run_log.py -q` |
| 3 | Smoke run: one real call per model, fixed seed, 3 repeats; report if outputs differ. Needs Ollama. | `python -m debate.smoke --repeat 3` |
| 4 | Evidence layer: brain search wrapper, PubMed fallback, level table, evidence records. Fake brain and fake PubMed in tests. | `python -m pytest tests/test_evidence.py -q` |
| 5 | Debate loop with fake models: rounds, new-objection check, stop rules, status, append-only log. | `python -m pytest tests/test_debate_loop.py -q` |
| 6 | Wire the citation check and disclaimer into the output; render the disagreement box (Markdown file). | `python -m pytest tests/test_debate_output.py tests/test_citations.py -q` |
| 7 | Synthetic eval set (12-15 cases) and scorer; arm A vs arm B run script. | `python -m debate.eval --fake`, then `python -m debate.eval --live` (needs Ollama) |
| 8 | Reviewer sign-off file and note; "NOT REVIEWED" banner. | `python -m pytest tests/test_signoff.py -q` |
| 9 | Safety case, data-protection note, FINDINGS.md entry, README section. | the company health check (command confirmed in step 0) |
| 10 | Gap finder: read M&M minutes (the existing `minutes/` Markdown) or a plain-text transcript; output a gap list against the debate log and evidence records (unanswered objection, uncited claim, action without owner). Synthetic minutes/transcripts only. | `python -m pytest tests/test_gap_finder.py -q` |

Stop and report if a library is missing (no installs). The Ollama Python client may be missing; plain HTTP to the local Ollama port avoids it. Module and test names above are proposals.

## 9. Decisions (1 Nov 2026)

1. **How far first:** steps 0-8, then 10 (decided).
2. **Roles:** MedGemma proposes; Qwen and MedGemma critique. The evaluation also runs the swap (Qwen proposes) and reports both (decided).
3. **Clinical reviewer:** none in v1. Every output carries "NOT REVIEWED". The tool supports the M&M; it does not replace the committee (1 Nov).
4. **Pass bar:** the proposed bar in section 7, reported as a target, not a result (decided).
5. **Sources:** verified against the record or abstract (section 10).

## 10. Sources needed (brain gaps)

VERIFIED 1 Nov 2026: all 8 below are real and match (record/abstract level, mostly via Europe PMC; arXiv for preprints). Du 2023 and MedGemma 2025 are preprint/technical report, not peer-reviewed; Liang 2023 appeared at EMNLP 2024; Singhal 2023 has a publisher correction, no retraction. Two added: Singh 2014 (BMJ Qual Saf, outpatient diagnostic error 5.08%) and Kim 2024 (MDAgents, multi-agent LLMs in medicine).  Full texts not yet read.

| # | Source (verified 1 Nov) | Authors, year | Why |
|---|---|---|---|
| 1 | Improving Factuality and Reasoning in Language Models through Multiagent Debate | Du et al., 2023 | Base paper for debate in rounds |
| 2 | Encouraging Divergent Thinking in Large Language Models through Multi-Agent Debate | Liang et al., 2023 | Why fixed-role critics may beat self-checking; debate failure modes |
| 3 | Large language models encode clinical knowledge | Singhal et al., 2023 | Method for scoring clinical answers by human review |
| 4 | MedGemma technical report | Google research team, 2025 | What the model is, what it was tested on, its limits |
| 5 | The importance of cognitive errors in diagnosis and strategies to minimize them | Croskerry, 2003 | Bias list (anchoring, premature closure) for the diagnosis critic |
| 6 | Diagnostic error in internal medicine | Graber, Franklin, Gordon, 2005 | Sources of diagnostic error; basis for objection types |
| 7 | GRADE: an emerging consensus on rating quality of evidence and strength of recommendations | Guyatt et al., 2008 | Evidence hierarchy for the ranking table |
| 8 | GRADE guidelines: 3. Rating the quality of evidence | Balshem et al., 2011 | Detail for later GRADE-style certainty (out of scope in v1) |

Once these sources are in the local knowledge base, the evidence layer finds them first.

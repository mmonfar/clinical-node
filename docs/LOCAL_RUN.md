# Local run: the agents on the synthetic cases (Ollama, this laptop)

Research and demonstration software. Not a medical device. Not clinical advice. Synthetic cases only.
**This report is NOT REVIEWED by a clinician.** It tests the software, not the medicine.

## No baseline

There is no stored gpt-4o output for these cases, so there is **no baseline** and **no claim of equal quality** with any cloud model. The table only says whether each agent returned output that the software can use, and how long it took.

## How the run was done

- Runner: `eval/run_local.py`. Raw numbers: `eval/local_run_results.json`.
- Models: SBAR, Researcher and Auditor use `qwen3:8b`. The MDT roundtable and the 72-hour check use `gemma4:12b`. All run on the local Ollama server. No cloud call is made.
- Laptop: 31.5 GB RAM. Speed was measured in the earlier run at about 5 to 6 tokens per second, so runs are slow.
- PubMed was switched off (evidence offline, a synthetic setting for the NCBI e-mail was used). Every search returned no articles. The Researcher therefore summarised an empty evidence set. Search itself is not tested here.
- Minutes and the case store went to a temporary folder, not to the repository.
- Each case ran in its own process with a 1500 s limit (`CASE_TIMEOUT` in `eval/run_local.py`).
- "Valid" means: SBAR has all four non-empty fields; Researcher text of at least 80 characters; MDT is JSON with a non-empty roundtable and a final recommendation; Auditor minutes of at least 300 characters with headings; the 72-hour check returns a yes/no answer. It does not mean the content is right.

## Latest run (6 Nov): all 14 cases, after the fixes

Run on code after fix commit `45c6c72` (retry after HTTP 500 and bad JSON; mark citations that have no retrieved article). All 14 cases were started.

- **12 of 14 cases finished.** `c02_cystitis_easy` and `c06_appendix_missing_fact` hit the 1500 s per-case limit. The raw file shows `"error": "timeout after 1500s"` and no agent data for them. **Why they timed out is not known; this was not checked.**
- In the 12 finished cases every agent was valid: SBAR, Researcher, MDT, Auditor and 72-hour check each 12 of 12. The `problem` text is empty in all 60 agent rows, so the runner flagged no MDT citations without sources.
- Case totals are 759 to 1500 s (the two timeouts are the 1500 s). All 14 cases together took about 4.4 hours (15 970 s).

### Results (valid = yes in every row shown; seconds)

| Case | SBAR | Researcher | MDT | Auditor | 72-h check | Case total (s) |
|---|---|---|---|---|---|---|
| c01 cap_easy | 45 | 123 | 446 | 322 | 178 | 1113 |
| c02 cystitis_easy | timeout | timeout | timeout | timeout | timeout | 1500 |
| c03 dka_easy | 50 | 78 | 665 | 392 | 94 | 1279 |
| c04 hf_vs_copd | 72 | 90 | 491 | 457 | 201 | 1311 |
| c05 dvt_ambiguous | 48 | 197 | 562 | 376 | 146 | 1329 |
| c06 appendix_missing_fact | timeout | timeout | timeout | timeout | timeout | 1500 |
| c07 sah_anchor | 40 | 84 | 526 | 311 | 142 | 1106 |
| c08 pe_with_bleed | 50 | 148 | 384 | 312 | 100 | 995 |
| c09 htn_asthma | 45 | 120 | 447 | 261 | 185 | 1058 |
| c10 cap_penicillin | 42 | 120 | 382 | 296 | 614 | 1454 |
| c11 acs_epigastric | 52 | 115 | 366 | 326 | 104 | 963 |
| c12 thyroid_anxiety | 39 | 103 | 311 | 253 | 112 | 819 |
| c13 ace_pregnancy | 37 | 101 | 293 | 238 | 90 | 759 |
| c14 uti_warfarin | 35 | 70 | 300 | 273 | 108 | 787 |

"timeout" means the case produced no agent data, so nothing is known about its agents.

### Valid outputs per agent (12 finished cases)

| Agent | Model | Valid | Mean seconds |
|---|---|---|---|
| SBAR | qwen3:8b | 12 of 12 | 46 |
| Researcher | qwen3:8b | 12 of 12 | 112 |
| MDT roundtable | gemma4:12b | 12 of 12 | 431 |
| Auditor | qwen3:8b | 12 of 12 | 318 |
| 72-hour check | gemma4:12b | 12 of 12 | 173 |

Means are over the 12 finished cases only. The 72-hour check in c10 took 614 s, the longest single agent step of this run.

### What this run does not show

- The results file does not record whether a retry or a fallback was used, so it cannot show how often the new retry code ran.
- Why c02 and c06 timed out: not checked. (In the earlier run the same two cases did finish, in 1014 s and 1281 s, but that run used older code and the timing may differ for other reasons.)
- Content quality: not reviewed. Answer keys (`must_catch`) were not scored. "Valid" only says the output has the right shape.
- PubMed search: not tested live. Search was offline in this run too.
- A valid MDT with no flagged citation does not prove the content is right.

## Earlier run (5 Nov, before fixes)

Only cases c01 to c06 were run (the session ended first). Result on the old code:

- Researcher valid in 3 of 6 cases (3 failed with HTTP 500 in query planning; the fallback summary worked).
- 1 bad MDT JSON (c03): the case stopped there.
- 1 bad 72-hour check JSON (c06).
- Made-up citations: the MDT cited reference numbers with no references in 3 cases.
- SBAR 6 of 6, MDT 5 of 6, Auditor 5 of 5 reached, 72-hour check 4 of 5 reached. Mean case time about 1020 s (range 595 to 1281 s).

The fixes in `45c6c72` aimed at exactly these faults:

1. **HTTP 5xx:** a model call that fails with HTTP 5xx is retried once with a new seed, a repeat penalty and a small temperature. If pillar planning still fails, the engine uses the single-query search and records the reason under `fallback`.
2. **Bad JSON (MDT, 72-hour check):** one retry that asks for valid JSON. A second failure is raised as before.
3. **Citations without sources:** every `[N]` in the MDT output and the Auditor minutes is checked against the retrieved articles. A number with no article is removed from `citations` lists and marked `[NO EVIDENCE FOUND]` in text; `citations_removed` counts them. It cannot tell whether a real-numbered citation supports the claim, and it does not flag claims with no citation.

Compared with the earlier run, the 12 finished cases show no failure of these kinds. This is a change between two runs on different code, not proof that the fixes caused it.

## Not done / limits

- c02 and c06 have no agent data (timeout, reason not checked).
- Answer keys were not scored. Quality was not judged.
- Search was offline, so evidence quality is untested.
- To repeat: `python eval/run_local.py` (about 4.4 hours).

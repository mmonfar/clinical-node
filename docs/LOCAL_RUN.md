# Local run: the agents on the synthetic cases (Ollama, this laptop)

Research and demonstration software. Not a medical device. Not clinical advice. Synthetic cases only.
**This report is NOT REVIEWED by a clinician.** It tests the software, not the medicine.

## No baseline

There is no stored gpt-4o output for these cases, so there is **no baseline** and **no claim of equal quality** with any cloud model. The table only says whether each agent returned output that the software can use, and how long it took.

## How the run was done

- Runner: `eval/run_local.py`. Raw numbers: `eval/local_run_results.json`.
- Models: SBAR, Researcher and Auditor use `qwen3:8b`. The MDT roundtable and the 72-hour check use `gemma4:12b`. All run on the local Ollama server. No cloud call is made.
- Laptop: 31.5 GB RAM. Measured speed was about 5 to 6 tokens per second, so runs are slow.
- PubMed was switched off (evidence offline, a synthetic setting for the NCBI e-mail was used). Every search returned no articles. The Researcher therefore summarised an empty evidence set. Search itself is not tested here.
- Minutes and the case store went to a temporary folder, not to the repository.
- Each case ran in its own process with a 1500 s limit.
- "Valid" means: SBAR has all four non-empty fields; Researcher text of at least 80 characters; MDT is JSON with a non-empty roundtable and a final recommendation; Auditor minutes of at least 300 characters with headings; the 72-hour check returns a yes/no answer. It does not mean the content is right.

## Coverage: 6 of 14 cases

Cases c01 to c06 were run. **Cases c07 to c14 were not run**: one case takes 10 to 21 minutes on this laptop, and the working session ended first. Run `python eval/run_local.py` to do all 14 (about 4 hours).

## Results (valid = yes / no, seconds)

| Case | SBAR | Researcher | MDT | Auditor | 72-h check | Case total (s) |
|---|---|---|---|---|---|---|
| c01 cap_easy | yes, 37 | NO, 48 (HTTP 500); fallback summary yes, 38 | yes, 466 (*) | yes, 376 | yes, 121 | 1087 |
| c02 cystitis_easy | yes, 48 | NO, 57 (HTTP 500); fallback summary yes, 64 | yes, 371 (*) | yes, 302 | yes, 172 | 1014 |
| c03 dka_easy | yes, 54 | yes, 80 | NO, 460 (bad JSON) | not reached | not reached | 595 |
| c04 hf_vs_copd | yes, 62 | yes, 77 | yes, 409 | yes, 290 | yes, 160 | 1000 |
| c05 dvt_ambiguous | yes, 40 | NO, 49 (HTTP 500); fallback summary yes, 43 | yes, 411 (*) | yes, 418 | yes, 172 | 1134 |
| c06 appendix_missing_fact | yes, 59 | yes, 96 | yes, 344 | yes, 285 | NO, 497 (bad JSON) | 1281 |
| c07 to c14 | not run | not run | not run | not run | not run | not run |

(*) Valid, but the roundtable cites reference numbers although no references existed (evidence was offline). Treat those citations as made up.

## Valid outputs per agent (cases run)

| Agent | Model | Valid | Mean seconds |
|---|---|---|---|
| SBAR | qwen3:8b | 6 of 6 | 50 |
| Researcher | qwen3:8b | 3 of 6 (3 failed in query planning; the fallback summary worked 3 of 3) | 85 when it worked |
| MDT roundtable | gemma4:12b | 5 of 6 | 410 |
| Auditor | qwen3:8b | 5 of 5 reached | 334 |
| 72-hour check | gemma4:12b | 4 of 5 reached | 156 when valid |

Mean time per case: about 1020 s (17 minutes); range 595 to 1281 s.

## What failed

1. **Researcher, query planning (3 of 6 cases).** When the first search finds too few articles, the engine asks the Researcher model to split the case into three search queries (JSON, temperature 0.0). With `qwen3:8b` the model fell into a repeating loop and Ollama stopped it: `prediction aborted, token repeat limit reached` (HTTP 500). This happens in the engine code path, not only in the test. With real PubMed results this step may be skipped for common cases, but it was not tested here. Possible fixes (not done): a small temperature above 0, a repeat penalty, a token limit, or a retry.
2. **MDT, bad JSON (c03).** `gemma4:12b` returned JSON that could not be parsed. The engine has no retry, so the case stopped there.
3. **72-hour check, bad JSON (c06).** The model answer could not be parsed. The check swallows the error and answers "no contradiction", so a failure looks like a quiet "no". The runner flags it.
4. **Citations without sources.** With no articles, the MDT still cited reference numbers (3 cases). This is a risk to watch when evidence is empty.
5. After a failure the runner continued with a fallback so later agents were still tested. These fallback rows are listed separately above.

## Not done / limits

- 8 of 14 cases not run (time).
- Answer keys (`must_catch`) were not scored. Quality was not judged.
- Search was offline, so evidence quality is untested.

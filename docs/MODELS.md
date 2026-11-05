# MODELS: what is installed for the debate engine (checked 1 Nov 2026)

Research and demonstration software. Not a medical device. Synthetic cases only.
Source: `ollama list` and `http://localhost:11434/api/tags` (server was running). Nothing was pulled.

## Laptop

- RAM: 31.5 GB installed (`Win32_ComputerSystem`, 31.46 GB). Treat as the "32 GB" case in SPEC section 5.
- Ollama: installed locally, server answers on port 11434.

## Installed models (exact)

| Name | Digest (first 12) | Size | Params / quant |
|---|---|---|---|
| medgemma:4b | 9fe4e9a6c9bd | 3.3 GB | MedGemma, 4B (Ollama tag `medgemma:4b`) |
| qwen3:4b | 359d7dd4bcda | 2.5 GB | 4.0B, Q4_K_M |
| qwen3:8b | 500a1f067a9f | 5.2 GB | Qwen3 8B |
| qwen2.5:7b | 845dbda0ea48 | 4.7 GB | Qwen2.5 7B |
| qwen2.5-coder:7b | dae161e27b0e | 4.7 GB | 7.6B, Q4_K_M (code model, not for this use) |
| gemma4:12b | 6114515d63c1 | 8.0 GB | 11.9B, Q4_K_M |
| gpt-oss:20b | f38aa0c53da5 | 13 GB | 20.9B, MXFP4 |
| granite4.2:8b | f586c02fdecd | 5.3 GB | 8.8B, Q4_K_M |
| hermes3:latest | 4f6b83f30b62 | 4.7 GB | Hermes 3 |
| nomic-embed-text:latest | 0a109f422b47 | 274 MB | embedding only |

Full 64-character digests (needed for the run log, GOVERNANCE R1) come from the `/api/tags` call at run time; step 2 logs them.

## Gap against SPEC section 5

| Need | Have | Missing |
|---|---|---|
| MedGemma small (about 4B) | `medgemma:4b` (yes) | none |
| MedGemma large (about 27B) | no | `medgemma:27b` (not pulled; the tag and whether it is text-only must be checked in the Ollama library first) |
| Qwen mid (7B-14B) | `qwen3:8b`, `qwen2.5:7b` (yes) | `qwen3:14b` if a 14B is wanted |
| Qwen large (about 32B) | no | `qwen3:32b` (will be tight on 32 GB with a second model loaded) |

The first debate runs (steps 3 to 8) can start with what is installed: MedGemma 4B as proposer and Critic B, Qwen3 8B as Critic A.
Open: whether `medgemma:4b` is text-only or also takes images is not recorded by Ollama's tag list here; the test in step 3 will show it.

### Pull commands needed (the user runs them; the code never pulls)

```
ollama pull medgemma:27b
ollama pull qwen3:14b
ollama pull qwen3:32b
```

These are optional. They are about 17 GB, 9 GB and 20 GB, a guess from the usual 4-bit sizes. Check the real sizes before pulling. Check the disk space first.

## Map: "C5" items to GOVERNANCE R ids

The brief's C5-1..C5-9 are the same numbers as GOVERNANCE section 7 R1..R9 (confirmed in `docs/GOVERNANCE.md` section 7). The mapping is one to one.

| C5 item | GOVERNANCE id | Subject | Used in the debate engine (SPEC) |
|---|---|---|---|
| C5-1 | R1 | Pin model snapshots, seed, max_tokens, prompts versioned, run id | Section 5: digest + seed logged; step 2 |
| C5-2 | R2 | Wire `adapters/citations.py` into output | Section 4; step 6 |
| C5-3 | R3 | Synthetic evaluation set, scored per change | Section 7; step 7 |
| C5-4 | R4 | Reviewer sign-off, append-only feedback | Section 6; step 8 ("NOT REVIEWED" banner) |
| C5-5 | R5 | Prompt-injection hardening + JSON schema validation | Section 2; step 1 (`debate/schema.py`) |
| C5-6 | R6 | PHI guard before the model call | Section 6 (pattern check; no step of its own yet) |
| C5-7 | R7 | Disclaimer in UI and minutes | Section 6; step 6 |
| C5-8 | R8 | LLM-governance references in the local knowledge base | Section 10 sources |
| C5-9 | R9 | Visible cron failures, append-only case history | Not used by the debate engine |

Note: the SPEC section 6 sentence names only R1 to R4. Step 1 also covers R5 (schema check) and the PHI guard (R6) has no build step yet. This is a gap still to be placed.

## Baseline test result (before step 1)

`python -m pytest tests -q`: 14 passed, 4 failed. The 4 failures were already there and are not caused by this work. Cause: the `Bio` module (Biopython) is not installed (`ModuleNotFoundError: No module named 'Bio'`) in `test_escaping.py` (2) and `test_llm_adapter.py` (2). Not installed because builders must not install anything.

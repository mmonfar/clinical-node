# Synthetic evaluation cases (debate engine, SPEC section 7)

14 invented cases. No real patients. Mix: 3 easy, 2 ambiguous, 9 trap
(tempting wrong anchor, missing contraindication, missing key fact).

**The answer keys are drafted by the author. They are NOT reviewed by a clinician.**
Every case has `"reviewed": false`. There is no clinical reviewer in v1
(SPEC section 9, decision 3). The keys use well-established textbook medicine only.
Treat the scores as a test of the software, not as a clinical judgement.

Fields per case:
- `case_text`: the fictional case.
- `category`: `easy`, `ambiguous` or `trap` (`trap_kind` says which trap).
- `evidence_topics`: search topics for the evidence layer.
- `expected_leading_diagnosis`: name plus accepted synonyms.
- `must_catch`: items a good review should raise. `terms` are key words (any one counts;
  a trailing `*` means "starts with"). `critic` says which critic type should raise it.
- `must_not_claim`: statements the proposal must not make. `terms` are whole phrases.
- `reviewed`: always `false` in v1.

Term matching in code is approximate. A key-word match is not a clinical judgement.

Research and demonstration software. Not a medical device. Not clinical advice. Synthetic cases only.

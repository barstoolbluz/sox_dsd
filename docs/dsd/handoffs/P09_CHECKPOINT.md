# P09 continuation checkpoint

Input source SHA-256: dd88d30d9367fe7edc94eb1f9739c5d4dcdd3b71d7c82496ae590993c405849e.
Baseline regression P09 runner stated 36/0 by supplied brief; independent verification pending.
Frozen analysis filter not yet generated; no quality comparisons authorized at this checkpoint.

Sequence: (1) construct/freeze independent analysis-v1 and verify synthetic known answers;
(2) implement exact-rate immutable registry and independent small scalar normal state;
(3) run tests, numerical candidate/control measurements; (4) paired benchmarks; (5) handoff and source-only archive.

No changes to production source are made at this point. Preserve original prior evidence.

Checkpoint 2 (2026-10-09): Created high-precision, rate-specific analysis-v1
filters; eight self-tests pass. `tests/dsd/reference/analysis-v1/SHA256SUMS.txt`
seals coefficients, generator, analysis, verifier and candidate scoring. Frozen
before *any* candidate dB comparisons. The 30 original baseline coefficient
hashes are separately pinned in `reference/p09_original_coefficients.json`.
Implemented new strict-rate profile API / small monitored scalar normal state
and wrote public-ABI unit/integration fixtures. Next: build/verify before
candidate metrics. Do not change analysis-v1 in place.

Checkpoint 3 (2026-10-09): All inherited and new P09 executable tests pass.
Frozen analysis-v1 self-tests 8/0, analytic scalar cases 24/0, original
coefficient hashes 12/12; P09 runner 36/0, generic check passes, development
benchmark 36/36. Normal and trellis legacy bytes match untouched P08 control.
P08/P09 throughput paired measurements were completed but are inadmissible
because host repeatability is 6.4%, above the 2% cap. No mastering promotion.
The authoritative final continuation archive and its SHA-256 are recorded in
the conversation handoff, not this checkpoint (avoid self-hashing).

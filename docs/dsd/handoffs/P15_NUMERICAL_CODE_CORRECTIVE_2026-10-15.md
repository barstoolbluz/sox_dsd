# P15 SRC numerical-disposition code handoff — 2026-10-15

**Decision: P15 remains BLOCKED; no defaults, encoder-v2, P16 or new ISA
preference is authorized.** This is a *code* corrective, not documentation
alone. The existing production SRC and DSP code are unchanged.

## Normative ruling and machine checker

`docs/dsd/DSD_DESIGN.md` §8.6.1 now carries the normative P15 SRC
same-operator numerical error bound and a narrower ruling that samplewise
comparisons between different SRC filters are **diagnostics only**. Do **not**
weaken the existing full-chain 0.0001-dB passband and -160-dB unwanted
alias/stopband limits. The machine-readable selector is
`tests/dsd/reference/p15_src_numerical_criteria.json` (not a separate copy of
normative threshold constants). The executable checker is
`tests/dsd/p15_src_envelope_review.py`. Its output is
`tests/dsd/results/P15_src_numerical_disposition_2026-10-15/review.json`.
The new `tests/dsd/test_p15_src_envelope_review.py` verifies counts, scope,
finite metrics, tamper resistance, the gamma(k) evaluator and immutable
result writing. All source/session/cell digests are checked without rerunning
the original recordings.

**Results:** 81 scalar cells, 324 forced-ISA same-scalar receipts, and 9
true no-SRC FIR cases examined. Exactly 36 fractional native/output-ratio
cells (24 v1, 12 v2) have the correctly classified, different-filter
numerical diagnostic. The other 36 integer native/output-ratio cells also
use SRC, since intermediate R differs from F_out. Consequently the full
same-transfer numerical oracle and composite spectral/alias certificate
remain OPEN for all 72 SRC-active cells. The existing `.npz`, `graph-raw`
and `.state` transport omissions are *not* new measured failures. The
missing coefficient/phase operator, numerical operation audit, and
between-tone extremum/alias proofs cannot be reverse-engineered from
recorded scalar summary errors without pretending a new measurement took
place. Do not choose post-hoc `1e-3` interior or `3e-3` edge thresholds.

## Current vs historical reviewer entry points

* `python3 tests/dsd/p15_src_envelope_review.py --output NEW.json
  --require-qualified` — creates a new, idempotent, separate numeric
  disposition; current honest result exits 2 (blocked).
* `python3 tests/dsd/p15_current_closeout.py --output NEW.json
  --require-release` — current-source composite inventory including this
  code-side numerical disposition; expected exit 2.
* `python3 tests/dsd/p15_release_manifest.py --current-evidence
  --current-output NEW.json --require-qualified` — opt-in current evidence;
  the historical `P15/release` manifest stays frozen. Expected exit 2.
* `python3 tests/dsd/p15_closeout_review.py --current-evidence
  --output NEW.json --require-qualified` — same current report through the
  old reviewer CLI; historic dated adjudication stays frozen. Exit 2.

An inventory command without `--require-qualified` may exit 0 while reporting
`BLOCKED`. The original reviewers' no-flag historical semantics are retained;
they are *not* legitimate current-source release decisions. Both new bridge
modes refuse to write inside their historically protected output directories.

## P10 lineage

The originally certified P10 35-input manifest and verifier are intact.
At this source revision 30 original inputs remain byte-identical, four
previously approved later executable files differ, and the operative design
document is the fifth changed P10 input. The new §8.6.1 revision is checked
by a specific SHA-256 pin in `p15_current_closeout.py`. This is a reviewed
P15 change, **not P10 re-certification**, a rewrite of its certificate, or a
generic exemption for future document edits. The current reviewers pin 17
(v1) / 22 (v2) current noncompiled reference inputs per executing session.

## Complete remaining blockers and release scope

1. **Full-chain SRC qualification (OPEN).** The newly adjudicated
   unlike-transfer samplewise differences are no longer a spurious failing
   test, but an independently constructed production *same-transfer*
   high-precision arithmetic witness (§8.6.1) and bounded composed FIR+SRC
   all-frequency extrema/coherent-image certificate (§§6.1, 6.5, 10.4) are
   still missing. Reuse existing hashes, measured matrices, and tested
   common SRC clock-pair operator identities; do not demand another full
   hardware matrix just because the mathematical proof is missing.
2. **DSD256 controlled performance (OPEN).** The historical physical v1
   direct-legacy target receipt is scoped; the staged `sinc -20000` arm is
   not a bandwidth-matched control for 40-kHz v1 or 66-kHz v2 DSD256
   mastering. Characterize a valid 40/80 and 66/80 comparator and obtain
   the still-required v2 physical, paired/direct performance evidence.
   §10.7's >=2x threshold is versus the direct legacy arm; matched-control
   comparison is reported, not separately required to exceed 2x.

Previously admitted, scoped older-AVX physical evidence, 915 soak continuation
states and 15 receipts, independent-source corpus, and v2 bank/filter
certificate are not newly failed by this code. Physical Intel AVX-512
performance remains **UNRUN**, exempt only under the strictly unchanged
conservative dispatch and no Intel-specific physical-performance claim.
Stripped raw payloads cannot be replayed here; no live native compiler,
full build or physical host acceptance is asserted.

Keep all previous result JSON/measurement bytes unchanged. Regenerate the
`tests/dsd/results/P00/P00_SHA256SUMS.txt` inventory after editing; it
excludes itself and preserves SHA-256 identities for the omitted bulk files.
Supply a *cumulative patch against the original fb612f2b archive*, not a tree.

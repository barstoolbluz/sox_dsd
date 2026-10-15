# P15 current-source closeout, 2026-10-15 — BLOCKED, two substantive gates

**Reviewed supplied snapshot:** reported `fb612f2b`, verified archive SHA-256
`a9cc4fccd4dfe3627d02e2a56dba3b9dbb7f1678da9c84ec93fbc57f400ef3e5`.
The transport is a deliberately stripped `git archive` without `.git`; that
commit identity cannot be independently verified from the archive alone.
Machine review: `tests/dsd/p15_current_closeout.py`, new result
`tests/dsd/results/P15_current_closeout_2026-10-15/review.json`.
`--require-release` must exit 2; ordinary inventory runs exit 0 on valid
inputs even when the release is BLOCKED. A zero exit code is **not** a
qualification or approval to enter P16.

## Rulings against the actual current tree

| Question | Disposition |
| --- | --- |
| P10 pinned authority changed | **RECONCILED WITH SCOPED LIMIT**. Historical 35-input P10 certificate retains exactly 30 byte-identical inputs. Four changed executable inputs are tied to the accepted post-P10 source binding; the 35th is `docs/dsd/DSD_DESIGN.md`. Its current content contains reviewed Intel §10.7 and v2 policy changes and is accepted as *current P15 design*, not misrepresented as P10-certified source. Review pins the exact current design + Intel amendment SHA-256. Do not edit certificate/checker or silently generalize this one-revision allowance. |
| Stale `p15_release_manifest.py` | **Historical**, intentionally unchanged. Its fixed evidence paths and 31/4 count cannot describe P15-R3/R2+ current results. Use the new dated reader; do not regenerate old UNRUN records as if original tests occurred today. |
| Stale `p15_closeout_review.py` | **Historical**, intentionally unchanged. Its `P15_matrix_metrology_2026-10-14` hash of `src/dsd_decode.c` binds an earlier version and must remain so. Current matrix selections instead: `P15_v1_matrix_rebound_2026-10-15` and `P15_v2_matrix_2026-10-15`. Never relax source digests on an old session. |
| v1 metrology | **SOURCE-BOUND MEASURED, NOT QUALIFIED.** 54 scalar cells, 216 forced ISA jobs, 96 detailed ISA comparisons, 54 sampled SRC and graph cases. 17 reference inputs per session match current sources. |
| v2 metrology | **SOURCE-BOUND MEASURED, NOT QUALIFIED.** 27 scalar cells, 108 forced ISA jobs, 48 detailed ISA comparisons, 27 sampled SRC and graph cases. 22 reference inputs per session match current sources. |
| v2 independent FIR certificate | **Existing bounded candidate certificate**, three new banks and profiles (alongside old v1 certificate); not the 27-cell final SRC certificate. |
| Intel physical AVX-512 | **UNRUN-SCOPE-EXEMPT** only under the approved conservative/no-Intel-preference first-release policy. It is never PASS, and is reactivated for any Intel physical/default preference claim. |
| Older AVX, software material corpus and one-hour SDM soaks | **PASS-SCOPED, INHERITED** from 2026-10-14 adjudication. The original 15 one-hour receipts/915 serialized states were previously checked. Source-only transport omission prevents raw replay here but does not reverse that accepted decision. No extra one-hour decoder soak is manufactured. |

### Substantive gate A — full composite SRC acceptance: OPEN

The numerical rule is in
`docs/dsd/amendments/P15_SRC_ACCEPTANCE_METHOD_2026-10-15.md`. A
sample-by-sample bound against a *different design's* Kaiser SRC is explicitly
**out of scope**. However §§6.1, 6.5 and 10.4's independently certified
composite frequency/extrema/coherent-alias response and §8.6's independently
bounded *like-for-like* arithmetic remain mandatory. The current 54/27
matrices' `qualified: false` and `release_gate_closed: false` remain correct.

The claimed 24 v1 plus 12 v2 fractional cells understate SRC use. **48 v1
and 24 v2 cells invoke the private SRC**, including integer native/output
ratios involving intermediate-rate conversion. All 72 need numerical and
transfer coverage; the other 9 bypass SRC. Only 24 distinct
intermediate/output SRC clock pairs are involved, so operator proofs may be
reused where coefficients, phase, arithmetic and boundary behavior match.
Do not rerun accepted metrology
just to rebrand observations as acceptance. Complete the missing independent
proof with the existing raw vectors and deterministic bound/transfer inputs.

### Substantive gate B — DSD256 control/performance: OPEN

The retained 2026-10-14 R2 15-repetition physical observation exceeds 2×
against the **direct** legacy reference at 176.4/352.8 kHz, but its staged
`rate -v 88200 sinc -20000 rate -v` control has a 20-kHz cutoff rather than
v1's **40/80 kHz** pass/stop policy. Calling this control bandwidth-matched
is incorrect. **V2's intended 66/80-kHz DSD256 mastering default has no
valid matched staged comparison either**, nor a v2 candidate-specific
controlled 2× direct-path qualification in the cited R2 receipt.

Smallest sufficient follow-up: independently characterize *one staged control
per actually released DSD256 profile* against the required passband,
transition/stopband and pre-/post-decimation alias behavior at 176.4 and
352.8 kHz, including ultrasonic holdouts (not just a fixture quiet above
20 kHz). For v2, obtain a physically controlled, reproducible 15-repetition
six-channel candidate/direct/staged comparison (same host/build/fixture,
clock/affinity evidence, exact source and executable hashes, per-arm samples
and independently recomputed medians/dispersion). Reuse v1 R2 direct-path
timings as scoped observations; rerun only the v1 *matched* arm if its source,
host/build and comparison validity can be established. If not, rerun a
properly paired v1 comparison. No separate new architecture is necessary.

**Do not invent a second 2× target for the matched control.** Section 10.7
specifies ≥2× against the reviewed **direct** ultra-quality legacy path
and requires the bandwidth-matched comparison also be **reported**, so that
bandwidth-dependent speedup is visible. A qualified matched comparator may
show less than 2× without automatically violating that numerical target;
its result may still inform performance judgment.

## Completeness, transport and authorization

The baseline P00 SHA inventory had **11,124 entries**, of which **3,508**
original raw arrays, `graph-raw` and continuation-state payloads are
intentionally omitted from the source-only transport; all retained present
file hashes verify. Never delete these manifest entries, fabricate the bytes
or turn the stripped-tree omissions into new measurements. New sources,
result and this handoff are added to P00; the file excludes its own digest.
All previous measured evidence and earlier results must remain byte-identical.

No **additional independent P15 release gate** is demonstrated by the
received artifacts beyond A and B. Existing accepted physical older-AVX,
Intel scope exception, source corpus, FIR and soaks retain their original
limits; absent raw payloads are a **replay limitation**, not an invented third
failure. Final release needs an independent adjudication of A and B and its
exact final-source bindings. Do not treat the present source-bound checks as
a future unconditional certificate. The current review explicitly records
`status=BLOCKED`, `default_promotion_authorized=false`, `p16_authorized=false`.

**Not authorized:** automatic default/profile migration, v2 default
promotion, P10 encoder qualified-bit changes, new AVX512/Intel auto preference,
claiming physical device compatibility, declaring all hardware classes
performance-qualified, erasing/rebasing old receipts, or starting P16.
`decode.mastering.v2.dsd64/128/256` remains explicitly selectable under its
existing unqualified candidate policy; v1 coefficients and the explicit
conservative v1 path remain intact. The approved *intent* is v2 decode by
default **after qualification**, not a permanent v1-only final design.

Only a reviewed future result with both gates genuinely satisfied may
separately authorize a source change to the default/qualifier policy, and that
change must receive normal regression and release-host verification.

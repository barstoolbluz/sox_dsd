# v1 matrix re-bound to the release-default tree

Re-run because promoting mastering v2 to the decode default changed
`src/dsd_public.c`, which the 2026-10-15 v1 sessions pin.
`P15_v1_matrix_rebound_2026-10-15/` therefore binds to the pre-promotion
tree. That evidence is not wrong and is not deleted; it is evidence for the
tree it was measured on.

With this directory, both matrices again bind to one tree:

| matrix | pinned inputs | mismatching |
|---|---|---|
| v1, this directory | 18 | **0** |
| v2, `P15_v2_matrix_rebound_2026-10-20/` | 23 | **0** |

## Coverage, verified against the copies committed here

| observation | v1 | v2 |
|---|---|---|
| scalar full-duration cells | 54 | 27 |
| forced-ISA full-duration jobs | 216 | 108 |
| selected detailed ISA jobs | 96 | 48 |
| graph full-duration cells | 54 | 27 |
| sampled SRC full-duration cells | 54 | 27 |
| sessions | 5 | 5 |

`--require-coverage` exits 0 for both. No cell is qualified and no gate is
closed; the reviewer returns
`OBSERVATION_COVERAGE_COMPLETE_NOT_RELEASE_CERTIFICATE` in both cases.

## This re-bind moved no numbers

Every receipt here was compared with its counterpart in the 2026-10-15
directories: **486 of 486 v1 receipts and 243 of 243 v2 receipts are
bit-identical**, scalar baselines and cross-ISA entries alike. The source
digests each session records are the only thing that changed, which is what
being unbound meant. Measured on a Threadripper 7970X, which carries all
five required ISA tiers.

## What this does not do

`p15_closeout_review.py` still reads `P15_matrix_metrology_2026-10-14/`,
which was superseded on 2026-10-15 and pins eight sources that no longer
match. This directory does not change that; repointing that reviewer is a
separate decision about which evidence a release review rests on.

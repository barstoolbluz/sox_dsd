# v1 matrix re-bound to the extended-instrument tree

Re-run because extending the instrument for v2 changed four of the 17 inputs
the earlier v1 sessions pin: `p15_graph_integration.py`,
`p15_matrix_contract.py`, `p15_matrix_instrument.py` and
`p15_numerical_reference.py`. `P15_R3_matrix_2026-10-15/` therefore binds to
the pre-extension tree. That evidence is not wrong and is not deleted; it is
evidence for the tree it was measured on.

With this directory, **both matrices bind to one tree**, which is what a
release decision needs:

| matrix | pinned inputs | mismatching |
|---|---|---|
| v1, this directory | 17 | **0** |
| v2, `P15_v2_matrix_2026-10-15/` | 22 | **0** |

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

## Correction to commit 0b3f50c1

That commit's message, and our report of it, stated that the v1 matrix "is
being re-run against the extended instrument". It was not. We had decided to
run it and had not started it; nothing was running when the operator asked.
The run recorded here began afterwards. The claim was false when written and is
corrected here rather than left standing.

## Standing position

Three of the four conditions recorded in
`docs/dsd/amendments/P15_V2_DEFAULT_POLICY_2026-10-15.md` now have evidence
bound to the current tree: the v1 matrix, the v2 coefficient certificate, and
v2 end-to-end metrology. The **SRC acceptance envelope remains absent**, and we
propose none. Promotion of v2 to default is not authorised by this directory.

349 MB. Figures are from one host and are not a property of the code alone.

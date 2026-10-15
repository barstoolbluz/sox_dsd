# 3x9x2 matrix re-run against R3, and the v2 coefficient certificate

Run because R3's decoder changes unbound the R2 matrix receipts. Four of the
17 source digests the R2 sessions pinned had moved, so those 54 cells were
evidence for R2 and not for the tree carrying the v2 candidate. Against R3 the
same 17 digests match with **zero** mismatches, checked before the run started.

**No gate is closed here.** Every cell reports `qualified: false` and
`release_gate_closed: false`, and the reviewer returns
`OBSERVATION_COVERAGE_COMPLETE_NOT_RELEASE_CERTIFICATE`.

## Coverage, verified against the copies committed here

| observation | count |
|---|---|
| scalar full-duration cells | 54 |
| forced-ISA full-duration jobs | 216 |
| selected detailed ISA jobs | 96 |
| graph full-duration cells | 54 |
| sampled SRC full-duration cells | 54 |
| sessions | 5 |

`p15_matrix_receipt_review.py --require-coverage` exits 0 on this directory.

## The v2 coefficients certify independently

`certify_p15_r3_filters.py` reuses the separately authored P06 high-precision
extremum and coherent-image certifier against the production C99 hex words, not
the R3 generator. 3 of 3 banks and 3 of 3 profiles pass:

| profile | passband ripple | stopband | alias rejection |
|---|---|---|---|
| `decode.mastering.v2.dsd64` | 4.680e-09 | -188.61 dB | -187.09 dB |
| `decode.mastering.v2.dsd128` | 4.312e-09 | -189.30 dB | -187.78 dB |
| `decode.mastering.v2.dsd256` | 5.842e-09 | -188.59 dB | -182.84 dB |

Receipts in `v2-fir-certificate/`.

## What this does NOT establish, and it matters for promotion

**The matrix does not measure v2.** Its 54 cells are 27 `mastering` plus 27
`wideband`, both v1. The instrument cannot target v2 at all: its CLI offers
`--profile {mastering,wideband}` and `p15_matrix_contract.py:19` sets
`PROFILES = ('mastering', 'wideband')`. So there is no v2 cell, no v2
end-to-end metrology, and no v2 entry in the worklist the reviewer checks
against.

So of the three conditions we recorded in
`docs/dsd/amendments/P15_V2_DEFAULT_POLICY_2026-10-15.md` as apparently
required before v2 can be promoted to default:

| condition | state |
|---|---|
| matrix re-run against R3 sources | done, coverage complete, **v1 profiles only** |
| v2 coefficient certification | **passes**, 3/3 banks and profiles |
| SRC acceptance envelope | still absent |
| *(new)* v2 end-to-end metrology | **not possible with the current instrument** |

The fourth row is the finding of this run. Re-binding the matrix to R3 was
necessary and is not sufficient: a filter certificate plus a v1 matrix does not
qualify a v2 decoder end to end. Either the worklist and instrument gain a v2
profile axis, or the design authority states that the filter certificate plus
the existing cells suffice. That is a determination for them; we are reporting
what the instrument can and cannot see.

## Preservation

The R2 matrix evidence in `P15_matrix_metrology_R2_2026-10-14/` is untouched
and remains valid for the R2 tree. This directory supersedes it as the binding
receipt for the current tree, not as a correction of it.

349 MB, because excluding the raw arrays is what made the matrix unverifiable
two rounds ago. Figures are from one host and are not a property of the code
alone.

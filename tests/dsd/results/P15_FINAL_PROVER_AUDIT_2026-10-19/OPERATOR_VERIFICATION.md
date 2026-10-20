# Operator verification of the spectral closeout, 2026-10-19

`P15_SPECTRAL_FINAL_COMPLETE_2026-10-19.tar.zst`, sha256
`51e7c3b7...`, zstd integrity OK, 51,384 members.

## Their own verifier, and ours

`./VERIFY_BUNDLE.sh` reports 49,323 original members matching and 161
overlay additions matching the additive manifest.

We checked the zero-overlap claim independently against our tree at
cc399928: all 49,323 of our files byte-identical, 162 added, none modified,
none missing, and no `src/` change. The base is our own snapshot
`d058b390...`, which is the authority they name.

## Their new tests, on our tree

| suite | result |
|---|---|
| `test_p15_final_prover_audit` | 17 passed |
| R6-R9 suites, six modules | 65 passed |
| full P15 discover, 311 tests | 2 failures, 1 error, 15 skips |

All three failures are `test_p15_closeout_review`, which has failed
identically since before any of this work and is untouched.

## The decision they recorded

Ideal-operator spectral acceptance **ACCEPTED** as a scoped engineering
assurance decision, with instruction to stop routine spectral campaigns
absent a specific defect. Unconditional mathematical proof remains
CONDITIONAL on the `mpmath.iv` transcendental trusted base and historical
execution identity, both named as explicitly accepted residual risks.
Arbitrary-input FFT4G roundoff NOT DISCHARGED. Overall P15 OPEN.

Worth recording that they found a weakness in the historical receipt
reader, which accepts a fabricated PASS label carrying a contradictory
numeric upper, reproduced it, and contained it behind an independent
read-only checker. The archived receipts pass that checker.

## What we did not do

We did not re-derive the R6-R9 mathematics, and we did not attempt to
discharge either residual risk. Our checks are integrity, scope and test
execution.

## Gates after integration

Unchanged: both substantive gates OPEN, release BLOCKED, v2 off by default.
The acceptance is an assurance-tier decision about the spectral workstream,
not a gate change, and the closeout script correctly does not treat it as
one.

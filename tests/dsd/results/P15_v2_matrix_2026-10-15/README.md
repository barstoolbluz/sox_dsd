# mastering-v2 independent metrology: 27 cells, five tiers

The v2 end-to-end metrology that did not previously exist. The instrument
could not target v2 at all; the extension added a `mastering_v2` profile axis
and `--matrix v2`.

**No gate is closed here.** Every cell reports `qualified: false` and
`release_gate_closed: false`; the reviewer returns
`OBSERVATION_COVERAGE_COMPLETE_NOT_RELEASE_CERTIFICATE`.

## Coverage, verified against the copies committed here

| observation | count |
|---|---|
| scalar full-duration cells | 27 |
| forced-ISA full-duration jobs | 108 |
| selected detailed ISA jobs | 48 |
| graph full-duration cells | 27 |
| sampled SRC full-duration cells | 27 |
| sessions | 5 |

`p15_matrix_receipt_review.py --matrix v2 --require-coverage` exits 0, and the
session binding pins 22 reference inputs with zero mismatches against this tree.

## v2 against the independent reference, beside v1

Scalar tier, maximum absolute deviation from the independently composed
75-digit reference:

| | cells | isolated FIR | full program | program interior |
|---|---|---|---|---|
| **v2** integer-ratio | 15 | 1.99e-16 .. 2.78e-16 | 1.99e-16 .. 2.35e-03 | 1.99e-16 .. 4.07e-05 |
| **v2** fractional | 12 | 1.99e-16 .. 2.78e-16 | 7.07e-05 .. 5.46e-04 | 8.72e-11 .. 4.25e-05 |
| **v1** integer-ratio | 30 | 1.95e-16 .. 2.58e-16 | 1.95e-16 .. 2.42e-03 | 1.95e-16 .. 4.07e-05 |
| **v1** fractional | 24 | 1.95e-16 .. 2.58e-16 | 6.80e-05 .. 6.41e-04 | 8.73e-11 .. 5.90e-05 |

The v2 FIR cascade agrees with the independent reference to machine epsilon,
the same as v1, on a wider passband: 25 kHz against v1's 20 kHz at DSD64. The
end-to-end spreads are also the same order as v1's, and for the same reason:
every deviation above roundoff traces to an SRC stage, concentrated at
finite-file boundaries in the integer-ratio cells.

We read that as v2 behaving no worse than v1 against the reference. We do not
read it as v2 being qualified; the acceptance thresholds for the SRC stage
still do not exist.

## The v1 receipts no longer bind, and that is this round's cost

Extending the instrument changed four of the 17 inputs the v1 sessions pin:
`p15_graph_integration.py`, `p15_matrix_contract.py`,
`p15_matrix_instrument.py` and `p15_numerical_reference.py`. So
`P15_R3_matrix_2026-10-15/` binds to the pre-extension tree and
`p15_matrix_receipt_review.py` correctly reports a source/reference hash
mismatch for it against the current tree.

That evidence is not wrong and is not deleted. It is evidence for the tree it
was measured on. A release decision needs both matrices binding to one tree, so
the v1 matrix is being re-run against the extended instrument; until that lands,
only the v2 receipts here bind.

This is the third time revision-pinning has invalidated otherwise-good
receipts in this phase, and each time it was correct to do so.

173 MB. Figures are from one host and are not a property of the code alone.

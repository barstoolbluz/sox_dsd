# Audit of the corpus/FIR adjudication

Audited `sox_ng-P15-corpus-fir-adjudicated-2026-10-13.tar.gz`, SHA-256
`4e4f84339cfd83fdec6d0a9772fbe65de73122b2c3f926dbe69a7ba30e8774d2`, against
`5d128f43`. We accept the adjudication. Our checks, which have been wrong before.

## Scope verified

Nothing removed, nothing in `src/` touched. One file modified, the P00 manifest.
Seven additions: the handoff, a resume note, an adjudication driver, a
round-off probe, its unit suite, and the results directory. Build clean,
`make check` 0, `make check-dsd` 0 at 36 pass / 0 fail, the adjudication's own
12 tests pass.

## The permitting clause is real, and we checked it rather than taking it

The verdict rests on §8.6, and the design says it in terms:

> For FIR kernels, output count, phase and endpoint behavior are identical.
> **Bit equality is desirable but not mandatory.** ... Graph samples may differ
> by at most one int32 LSB; no extra clipping is allowed.

Line 60 adds "Cross-ISA sigma-delta byte differences alone are not defects",
and §10.6 defines cross-ISA equivalence by gain, phase, THD+N and integrated
noise tolerances rather than byte equality. So a scalar-versus-SSE2 difference
in modulated output is contemplated by the contract, not tolerated in spite of
it.

## Our hypothesis was wrong, and the adjudication corrected it

We proposed the composite's centered encoder prefilter as the dispatch site.
It is not. `src/pcmdsd.c:197` calls `lsx_dsd_fir_scalar` unconditionally, and
the only dispatch in that file is `lsx_dsd_kernel_select(LSX_DSD_SDM, ...)` at
line 141, for the modulator. We confirmed both directly.

The actual chain, as the adjudication sets it out: the corpus pipeline
reconstructs before encoding, reconstruction *is* tier-dispatched, its pre-graph
binary64 values differ by 1.39e-16 to 5.55e-16 against computed bounds of
1.12e-11 to 1.99e-11, and a difference that small can still flip an int32
quantization boundary, which changes the encoded bitstream. That is precisely
the one-LSB latitude §8.6 grants.

This also resolves the apparent contradiction with our own 30-of-30 decode
bit-exactness result. Those compared post-graph files, which are quantized;
the divergence lives in the pre-graph doubles upstream of that quantization.
We had treated identical decode files as implying identical internal values,
which does not follow.

## What the adjudication declines to claim, correctly

It does not assert the round-off path is the sole cause for this recording,
noting that a causal identification would need the private input or an
instrumented reproduction. It also records that its one controlled synthetic
fixture producing byte-identical output across P10, P15 scalar and P15 SSE2 is
a single example and not evidence of cross-ISA byte identity generally. We think
both reservations are right and we have not closed either.

## Repaired on integration

Two incidentals the reviewer also noted. `tests/dsd/__pycache__` was shipped and
is a gitignored build artifact; removed. `CORPUS_FIR_ADJUDICATION_RESUME.md` sat
at the tree root; moved to `docs/dsd/handoffs/` where every other handoff lives.
Neither affects the verdict.

## Disposition

The one-field corpus difference is anodyne: permitted by §8.6, both extrema
inside the required 4 to 24, no other field moved across 18 sources, and no
acceptance criterion engaged. No corrective DSP work, no certificate change, no
new release gate. P15's six release-qualification gates stand where they were,
independently of this.

# Operator verification, 2026-10-17

Checks of the delivered SRC optimization on our hardware. It is on this
branch, `dsd-src-runtime-optimization`, and deliberately not on
`dsd-p00-evidence-baseline`. The reason is in the last section.

## Bit-exactness: 62 of 62 conversions identical

Baseline `-O2 -g` against candidate
`-O2 -g -DLSX_RATE_ORDERED_OPT=1 -ffp-contract=off`, both from the delivered
tree. The binaries differ by 19 KB and the rate objects differ, so the opt-in
really compiled.

| group | comparisons | mismatches |
|---|---|---|
| 4 sources x 11 output rates | 44 | 0 |
| six-channel, 4 rates | 4 | 0 |
| short files, 3 durations x 2 rates | 6 | 0 |
| DSD decode through the SRC, 2 profiles x 4 rates | 8 | 0 |

The set includes a 60-second source, which crosses FIFO block boundaries and
is what would expose a fault in the new incremental carry. It does not.

## Static equivalence

`coef(p, 0, LEN, rem, 0, j)` expands to `coef_p[LEN*rem + j]`, the same
address as the candidate's `c0[j]`. The carry test `r >= L - v` is exactly
`r + v >= L` without an overflowing intermediate and reproduces `div(at, L)`
incrementally; at loop exit `divided.quot/rem` equal the original's
`divided2`, so FIFO consumption and retained phase are unchanged. Each
accumulator still visits `j` in order.

## check-dsd: unchanged by the patch

In-tree, both builds: 208 PASS, 11 FAIL, identical failure sets. Ten are
`No module named 'jsonschema'`; the eleventh is a cascade from it, a file an
earlier step did not write. All are P14 report schema tests. `bit_exact_chunk_continuity_and_golden` and
`decoder_latency_components_and_byte_identity` both PASS. Logs are beside
this file.

`make check` exits 2 on both builds out-of-tree: `test/Makefile.am` compiles
`samples.c` with no `$(srcdir)` prefix, and a DSD test reads
`ROOT/src/soxconfig.h`, which is generated into the build tree. Both are
pre-existing and unrelated.

## Speedups: real, and smaller than reported

Prepared physical host, Threadripper 7970X, governor performance, boost 0,
pinned cpu 8, 9 interleaved repetitions per arm, whole-CLI user time, the
same scope as the delivered tables.

| conversion | delivered (KVM guest) | here (bare metal) |
|---|---|---|
| 44100 -> 48000 | 1.268x [1.211, 1.302] | 1.095x |
| 48000 -> 44100 | 1.283x [1.184, 1.346] | 1.103x |
| 44100 -> 96000 | 1.376x [1.326, 1.415] | 1.135x |
| 48000 -> 192000 | not tabulated | 1.004x |
| 44100 -> 192000 | not tabulated | 1.051x |

Direction agrees in every case, but the improvement is about a third of the
delivered one: the gain over unity is 35.4%, 36.4% and 35.9% of the delivered
gain in the three comparable cases. Read as speedup figures instead, that is
86%, 86% and 83%. Either ratio is consistent, which suggests something
systematic rather than noise. The delivered report labels its own
numbers "Local virtual-host CLI measurements; no physical qualification", so
the scope was stated correctly.

Our per-arm spreads were 1.2% to 4.9%, straddling the 2% the AMD
performance record treats as the threshold for a gate-grade timing, so these
are indicative and not gate-grade either. We did not instrument where the difference goes.

The delivered counts already say the win is case-specific: of 72 CPU cases,
41 have intervals including 1.0 and 2 fall below it.

## Why this is not on the evidence branch

`p15_src_bound_operator.py:37` pins `src/rate_poly_fir0.h` in the SRC
operator source identity. Changing that file, even behaviour-preservingly,
changes the per-file digest map `source_identity()` returns, which
`verify_pair` requires to equal the frozen `operator-binding.json`
`source_sha256` map. The current map carries `rate_poly_fir0.h` at
`c1626c26...`, the frozen receipts carry `928f0059...`. Verified
consequences:

- `source_operators(canonical_plan('1000'))` returns 24 realizations on the
  unpatched tree and raises `UnboundOperator` on the patched one. The
  continuum campaign cannot run.
- `test_p15_final_obligations.py` fails on the patched tree, including in the
  delivered tree itself.
- The 5112 campaign receipts on `dsd-p00-evidence-baseline` were produced
  under the previous source identity.

That campaign is the critical path for the only substantive gate still open,
so the optimization waits here until the stage-bound receipts are re-derived
against the new source. Re-binding is a source-bound mathematical derivation
and not ours to produce.

## One question back

The header requires `-ffp-contract=off` in prose but enforces only
`__FAST_MATH__` and `FLT_EVAL_METHOD == 0` as `#if` guards. We built with
contraction off, so nothing here speaks to a contracted build. Should that be
a hard guard too?

## Scope

Opt-in candidate. The default build is unchanged and compiles the block out.
Nothing here certifies P15, promotes a default, or closes a gate.

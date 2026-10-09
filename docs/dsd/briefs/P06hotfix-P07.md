# Combined round: recover P06's read regression, then implement P07

Work in the attached tree, `sox_ng-P06hotfix-P07-666e7635.tar.gz`, SHA-256
`a0bc9bfd334809617f9719954d9bcc884db91db8540c100609d2bf30da8ef0d4`, no `.git`.
It contains P00 through P06 accepted. `docs/dsd/DSD_DESIGN.md` and
`docs/dsd/IMPLEMENTATION_PLAN.md` remain the authority.

Two jobs, in this order, because the second makes the first unmeasurable if
they are mixed.

## 1. P06 failed its throughput gate

One workload regresses past the design's 5% limit with its whole confidence
interval beyond the threshold, measured on a prepared host at 0.43% noise:

```
dff-6ch-repack-small   +5.65%   95% CI [+5.50%, +5.89%]
```

That is DFF, six channels, repack, with `--buffer 32`. Every DSF workload is
unchanged within half a percent, and the large-buffer DFF workloads are
unchanged or faster, so it is specific to small-capacity DFF repack.

**Outcome wanted:** that workload comes back inside the 5% gate with its whole
interval below the limit, without giving back any of P06's numerical results —
the filter certification still passes, `run.py --phase P06` stays at 36 pass /
0 fail, and `make check` stays clean. If the cost proves irreducible, say so
with evidence and propose the deviation the design would require, rather than
relaxing the threshold.

**Certify it in isolation, before P07 exists in the tree.** The control is P05
at `149ea582` against P06 plus only your fix. If P07's changes are present,
the comparison conflates two phases and tells you nothing about either; P07
touches `rate.c` and `effects.c`, which are plausibly on the same timing paths.
The P02 hotfix round took exactly this approach and its handoff is worth
reading: `docs/dsd/handoffs/P02_DFF_READ_HOTFIX.md`.

Method, host preparation and the recorded evidence are in
`tests/dsd/BENCHMARKING.md`, `tests/dsd/benchprep.sh` and
`tests/dsd/results/P06/bench-read-prepared-host-2026-10-09/`.

## 2. P07, per its own SOW

Then implement P07 from `docs/dsd/sows/P07.md`, with `DSD_DESIGN.md` sections
3.3-3.4 and 6.4-6.6 as the authority.

**Outcomes wanted:**

1. Every explicit conversion works up to 705.6 kHz, with exact output counts
   from checked integer arithmetic, and the intermediate length rounded once
   rather than twice.
2. Public `rate` behavior is unchanged, and nothing claims that float output
   escapes the int32 graph limits.
3. The final SRC matches an independent reference at the 48 kHz-family ratios.
   The design treats these as two different tolerances: graph samples may
   differ by at most one int32 LSB with no extra clipping, stated in section 8,
   while "final SRC comparisons have their own measured numerical tolerance,
   not a claimed FIR-only proof". Do not borrow the FIR bound for the SRC
   comparison.
4. P07's own throughput gate is measured and stated, baseline P06-plus-hotfix
   against P06-plus-hotfix-plus-P07.

Return one complete source tree with `docs/dsd/handoffs/` entries for both the
hotfix and P07, and a regenerated `tests/dsd/results/P00/P00_SHA256SUMS.txt` if
file hashes move.

## Surplus, if you have room

`make check-dsd` dies with a bare `ModuleNotFoundError` on any host without
`mpmath` or `numpy`: `tests/dsd/test_decode.py` and
`tests/dsd/certify_filters.py` import both at module scope and
`tests/dsd/generate_coeffs.py` imports `mpmath`, none guarded. The project's
standard, which P00's harness follows, is that a missing tool is a named unrun
gate rather than a crash. P07 adds more numerical tests, so this compounds.
Whatever shape you choose, a numerical gate must remain impossible to pass
silently while unrun.

The `src/dsdiff.c` tab-versus-space inconsistency is dropped from this round:
it has been offered twice, it is cosmetic, and this round already carries two
substantial jobs.

Situational notes, possibly wrong or incomplete — trust the tree over them:

- The gate is 5% median regression, admissible only when measurement noise is
  under 2%, and the verdict comes from the confidence interval rather than the
  median. A straddling interval is inconclusive, not a pass. The harness now
  enforces that; it did not when P06 was first measured, which is why this
  regression initially read as +4.98% and passing.
- Short runs dilute a per-sample cost. This one measured +3.28% at 15 pairs
  with default fixtures and +5.65% at 40 pairs with larger ones. If your fix
  looks successful at small sizes, confirm it at larger ones before believing
  it.
- `-t null` workloads need `--null-extra-arg=--dsd-layout-loss
  --null-extra-arg=warn` on both arms from P04 onward, or they exit 2 and drop
  out of the gate.
- Unattributed and recorded as such: P06 also made `dff-6ch-null-large` 11.12%
  faster and `dff-6ch-repack-large` 5.62% faster, on paths its decode work
  should not touch. Linker layout or instruction-cache effects are likelier
  than real improvement. The slowdown may share that cause; profiling would
  settle it, reading the diff did not.
- P01 through P05 throughput gates are certified green on a prepared host, and
  P06's is the only failing one. Note that P02's needed a hotfix to get there,
  so `tests/dsd/results/P02/` holds both a failing record from the original
  measurement and a passing one from
  `DFF-read-hotfix-certification-2026-10-09`; the second supersedes the first.
- Please return a source tree rather than a built one, and keep
  machine-specific paths out of recorded results.
- Please leave previously recorded evidence as delivered, and flag anything
  here you find to be mistaken.

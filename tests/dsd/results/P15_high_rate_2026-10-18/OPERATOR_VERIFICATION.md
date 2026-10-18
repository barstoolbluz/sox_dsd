# Operator verification of the high-rate delivery, 2026-10-18

`sox_ng_P15_high_rate_FULL_SOURCE_2026-10-18.tar.gz`, SHA-256
`6737e55a...`, verified on arrival. 37,764 files, exactly as declared.

## The headline reproduces from the receipts

We recomputed the coverage union from the receipts rather than reading their
JSON. Keying each interval by cell, mode, lo and hi:

| population | claimed | recomputed |
|---|---|---|
| campaign-proper PASS | 6835 | 6835 |
| 600 s budget sample | 36 | 36 |
| high-rate candidate PASS | 1148 | 1148 |
| of those, originally OPEN | 1082 | 1082 |
| of those, originally passing | 66 | 66 |
| **union** | **7917** | **7917** |

## The four complete cells are genuinely complete

Not merely counted: checked against `canonical_plan('1000')`.

| cell | canonical | covered | missing |
|---|---|---|---|
| dsd256.mastering.pcm384000 | 232 | 232 | 0 |
| dsd256.wideband.pcm384000 | 334 | 334 | 0 |
| dsd256.mastering_v2.pcm384000 | 258 | 258 | 0 |
| dsd256.wideband.pcm192000 | 188 | 188 | 0 |

1,012 intervals with no canonical gap in any of the four.

## Integrity

All 35 operator-source pins byte-identical to ours. No `src/` change. Six
prover modules modified, none of them production audio. Nothing of ours
missing. Every shared file matches the pristine extract byte-for-byte except
the P00 inventory, which we regenerate.

## Two defects we found

**The delivered P00 inventory was stale.** The six modified prover modules
were not re-hashed into it, so each failed the tree's own inventory check,
which in turn broke `test_p15_current_closeout` and both
`test_p15_src_envelope_review` cases. Regenerating the inventory clears all
three. A packaging miss rather than a code defect; we regenerated it here.

**A one-interval accounting discrepancy.** The delivery cites an explicit
prior union of 6,873 from "four third-pass locals". The archive carries two
third-pass PASS receipts, only one of them novel, giving 6,872. That
propagates: 7,935 rather than 7,936, and 3,581 remaining rather than 3,580.
Immaterial to the result, but the figure is not what the delivered receipts
support. The primary accounting above is exact.

## Tests

222 P15 tests on the integrated tree: 2 failures and 1 error, all three in
`test_p15_closeout_review`, which fails identically on our tree before this
delivery and is untouched. 15 skips are executable-dependent.

## Not re-run here

Their matched baseline-versus-candidate timings, the 927-job final campaign,
and the 22 retries under larger budgets. We verified dispositions and
coverage, not their performance measurements.

## Scope

No gate changes. Both open gates stay open, release BLOCKED, v2 off by
default. Their own report says the same.

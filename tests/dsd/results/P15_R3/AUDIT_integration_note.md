# Audit of the R2 re-adjudication plus the R3 v2 decoder candidate

Audited the six-part archive `sox_ng-P15-R3-R2-reconciled-source-2026-10-15`,
joined SHA-256
`4209167009fca15ab01f511514f93aaa5eea9f16f4761312b430cc5dac832a6c`, against
our `81d141b8`. Our checks, which have been wrong before.

## Custody

Six transport parts, 00 through 05, no gaps, 361,070,933 bytes joined matching
the sum of the parts. `gzip -t` and a full `tar t` both clean before extraction.

This bundle spans **two** of their rounds. It is anchored to
`sox_ng-P15-R2-readjudicated-source-2026-10-14.tar.gz`, which we never
received: our tree carried 7,802 manifest entries and had no
`docs/dsd/amendments/`. So integrating it brings in the R2 re-adjudication,
including the granted Intel amendment, as well as the R3 decoder work.

Nothing was removed: 18 files modified, 18 added, 0 deleted. Manifest 7,831
entries, every one verifying.

## The Intel amendment was granted, feature-scoped

`docs/dsd/amendments/P15_INTEL_AVX512_SCOPE_2026-10-14.md` records **APPROVED,
FEATURE-SCOPED**, with the operative language in `DSD_DESIGN.md` §10.7.

It confirms the reading we checked rather than assumed: "Section 13's existing
optional hardware gaps did not include this one." We had looked for a reading
in which the requirement already failed to apply and reported that we could not
find one; that was correct.

It also states the gate "remains **UNRUN** after this amendment. Its absence
was not, and is not, reclassified as a test success." We read that as the right
disposition and have not recorded it as a pass anywhere.

## The v2 decoder candidate

New `src/dsd_coeffs_v2.h`, 230 lines, additive. Verified unchanged: P10's
frozen `src/dsd_coeffs.h`, `src/pcmdsd_coeffs.h`, `src/pcmdsd_guards.h`
including its certificate constant, `src/sdm.c`, `src/pcmdsd.c` with the
admission envelope line intact, and `src/dsd_dispatch.c`.

The public ABI change is additive and safe: a new enum value
`SOX_DSD_DECODE_MASTERING_V2 = 3`, with 0 and 1 unchanged and 2 reserved for
the private legacy profile. No struct renumbering.

Defaults are unchanged **for now**, and that is a temporary gate rather than
settled policy. `DSD_DESIGN.md` names v2 as the intended default for DSD64,
DSD128 and DSD256, with v1 reached by explicit conservative selection, and the
operator has confirmed that in
`docs/dsd/amendments/P15_V2_DEFAULT_POLICY_2026-10-15.md`. Our earlier wording
here presented the v1 default as the settled outcome; it is not. We checked the
current resolution by execution:

| invocation | resolves to | passband |
|---|---|---|
| default | `decode.mastering.v1.dsd64` | 20000 Hz |
| `--dsd-decode mastering` | `decode.mastering.v1.dsd64` | 20000 Hz |
| `--dsd-decode wideband` | `decode.wideband.v1.dsd64` | 35280 Hz |
| `--dsd-decode decode.mastering.v2.dsd64` | `decode.mastering.v2.dsd64` | **25000 Hz** |
| `dsdpcm -p decode.mastering.v2.dsd64` | `decode.mastering.v2.dsd64` | **25000 Hz** |

v2 is reachable only by explicit versioned ID and produces different output
from v1. Gates: build clean, `make check` 0, `make check-dsd` 0 at 36 pass /
0 fail.

## A defect we thought we had found, and did not

We first observed `--dsd-decode decode.mastering.v2.dsd64` accepted with exit 0
while the report said v1 and the output was byte-identical to v1, and began
writing it up as a silent fallback. A control run showed `--dsd-decode
wideband` behaving the same way, which did not fit, and testing without an
explicit `dsdpcm` effect in the chain resolved it: the global option governs
the decode the planner inserts, and an explicit effect's own `-p` takes
precedence. That is correct precedence and the report truthfully states what
ran. **There is no defect; we were holding it wrong.** Recorded because the
near-miss is the useful part.

## What R3 invalidates, correctly

`p15_readjudication.py` reports `INVALID EVIDENCE: session 1: source/reference
hash mismatch` on the tree as shipped, and identically in their own pristine
extract, so this is not an artefact of our integration. The cause is
revision-pinning working as designed, the same mechanism as the P10 certificate
verifier: the R2 matrix sessions pin 17 source digests and four have moved,
`src/dsd_decode.c`, `src/dsd_plan.c`, `src/dsd_public.c` and
`tests/dsd/test_p15_instrument.c`.

The consequence matters more than the message: **the R2 matrix evidence no
longer binds to the current tree.** 54 cells, 216 forced-ISA jobs and 96
detailed comparisons were measured against R2 sources that R3 has changed. The
matrix would have to be re-run against R3 to be evidence for R3. We are not
treating the existing receipts as covering the v2 candidate.

## Disposition, theirs not ours

ACCEPTED AS AN UNQUALIFIED V2 DECODER CANDIDATE. P15 FIRST RELEASE: BLOCKED.
P16: NOT AUTHORIZED. Defaults remain v1, and the v2 profile exists to permit
qualification without promotion.

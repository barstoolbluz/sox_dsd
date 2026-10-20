# v2 promoted to the decode default, 2026-10-20

Implements the operator decision of 2026-10-15 — "promote v2 to the default
without modifying the preserved v1 coefficients or unrelated encoder
behavior" — now that the design authority has recorded its engineering
acceptance and withdrawn the remaining formal-proof obligation as a release
blocker.

On a branch, not on `dsd-p00-evidence-baseline`. The reason is in the last
section.

## The change

Two lines of production source, both pure default selection.

`src/dsd.c`, `dsd_getopts`: the effect parser is shared between `dsdpcm` and
`pcmdsd`, and `LSX_DSD_PROFILE_MASTERING` and `LSX_DSD_ENCODE_MASTERING` are
both enum zero, so an unconditional change would have handed the encoder an
invalid profile. The default is therefore conditioned on `is_encode` and the
encoder keeps exactly the value it had.

`src/dsd_public.c`, `init_options_defaults`: the library default, which the
CLI does not use.

Coefficients, the profile registry, and the encoder are untouched. v1 stays
selectable with `-p mastering`.

## Verified

The default resolves to v2 at every native rate:

| native | profile | effective passband |
|---|---|---|
| 2822400 | `decode.mastering.v2.dsd64` | 25000 Hz |
| 5644800 | `decode.mastering.v2.dsd128` | 48000 Hz |
| 11289600 | `decode.mastering.v2.dsd256` | 66000 Hz |

`-p mastering` still resolves to `decode.mastering.v1.dsd256` at 40000 Hz.

The encoder is bit-identical before and after at all three native rates.
Our first attempt to check that compared files that were never created,
because the production `sox_ng` refuses to encode at all; the real encoder is
`test/sox_p10_candidate` and that is what the comparison used.

## Why this is on a branch

`src/dsd.c` and `src/dsd_public.c` are both in the 35-entry pinned source set
in `p15_src_bound_operator.py`. Editing them unbinds every stage-bound
operator receipt, exactly as the SRC optimization did to `rate_poly_fir0.h`.
`source_operators(canonical_plan('1000'))` now refuses with
`UnboundOperator`, and the DSD suite goes from 3 failures / 12 errors to 35 /
74, dominated by the 24-stage binding tests.

Those are not tests asserting the old default. They are the source-identity
binding doing its job. The fix is to re-derive the stage-bound receipts
against the new source, which is the authority's work, not ours.

## The thing that actually blocks a release

Separate from all of the above and not addressed here: `src/dsd_plan.c:123`
gates encoder activation on `lsx_pcmdsd_qualified(hz)`, so the shipping
binary refuses to encode DSD and emits "P10 mastering profile is unqualified;
qualification evidence blocks activation". Decode works. Encode does not.
Whether that predicate should now return true is a production decision that
has not been taken.

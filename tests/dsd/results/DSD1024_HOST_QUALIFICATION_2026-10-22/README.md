# DSD1024 host qualification, 2026-10-22

Threadripper 7970X. The same treatment DSD512 received, applied to
`encode.mastering.v2.dsd1024`, the corrected seventh-order candidate. The
defective eighth-order v1 remains blocked and untouched.

## Results

| check | result |
|---|---|
| training reproduction | **exact**, all 8 coordinates |
| `verify` | PASS 17 |
| holdout | PASS, 36 cases, 0 failures |
| ISA five-tier full-scale DC | 10/10 |
| 3,600-second nominal soak | **PASS_SOAK_INPUT_GATE** |
| commercial source | **not possible, see below** |

Soak: 162,570,240,000 native frames, min28 7, max28 21, longest run 5, zero
nonfinite states, zero overloads, 6.93% guard utilisation.

## The training reproduction is the strongest result here

Seventeen unguarded training cases rendered on our own executable produce
`training_max_abs_state` identical to the delivered values across all eight
coordinates:

    [1.8534, 3.3004, 16.3191, 155.1718, 2271.2354, 51700.4554, 2348476.4224, 0.0]

and therefore the same derived bounds, `[32, 64, 512, 4096, 65536, 1048576,
67108864, 16]`. Independent arithmetic reproduction on different hardware and
a different binary, not merely agreement on a verdict.

## ISA: five tiers, scalar-trained bounds hold

| | scalar | sse2 | avx1 | avx2 | avx512 |
|---|---|---|---|---|---|
| peak guard utilisation | 5.21% | 5.22% | 5.22% | 5.22% | 5.22% |

Full-scale DC, both polarities, roughly 19x headroom, zero nonfinite states,
longest run 4 throughout. **Exactly two distinct bitstreams per polarity:
scalar alone, with all four vector tiers byte-identical to each other** — the
same structure found at DSD512.

The vector tiers use marginally *more* state than scalar here, 5.22 against
5.21. That reinforces the correction recorded in the DSD512 ISA evidence:
"vector is always more conservative" was an artefact of two DC fixtures, not
a property of the kernels. What holds is the narrower claim: scalar-trained
bounds are satisfied on every tier tested.

## What cannot be done, and why it inverts the DSD512 order

**No DSD1024 media exists** — not in the operator's library, torrents or
scratch. The 12-track commercial decode qualification that DSD512 has cannot
be performed at all.

This reverses the sequence. For DSD512, read could be qualified first and
independently against commercially mastered material. For DSD1024 there is
nothing to read, so write must come first, and any later read qualification
would rest on media this encoder produced itself. That is circular evidence
and the authority should rule on its admissibility before anyone invests in
it.

## Provenance note for the harness

The frozen guard and its training receipts are inseparable: `freeze` refuses
unless the guard header is still the pre-freeze placeholder, and `verify`
refuses if the receipts backing the stored proof are replaced. A delivered
tree therefore cannot be host-re-qualified from scratch without the original
placeholder header. The DSD512 helper sidesteps this by deleting both the
guard and the results directory; DSD1024 ships no such helper. Our fresh
training receipts are retained under `training-reproduction/` and the
delivered chain was restored before `verify` and `adjudicate`.

## Scope

Nominal synthetic material, one host, scalar and four vector tiers at one
native rate. `qualified=0` stands, no certificate, no capability enabled, all
twelve P18 high-rate rows still disabled.

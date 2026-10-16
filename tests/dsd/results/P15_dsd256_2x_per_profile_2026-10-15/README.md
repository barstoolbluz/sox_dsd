# DSD256 2x target, matched per profile to its own passband

Supplies the evidence `P15-DSD256-direct-2x-and-matched-comparator` asked for.
**It does not close the gate and we do not claim it does.**
`p15_current_closeout.py:280` carries that gate's status as a hardcoded `OPEN`
with its `evidence` field pointing at the superseded R2 file, so the reviewer
will keep reporting it open regardless of what we measure. Whether this
evidence discharges it, and whether the reviewer should be repointed here, is
for the design authority.

## Our error

The gate's text: "R2 staged control sinc -20000 is not matched to v1 40 kHz nor
v2 66 kHz; v2 needs a qualified 66/80 kHz comparison and direct 2x
measurement."

Correct. We matched the control to 20 kHz, which is the passband of neither
profile at DSD256. Queried from the binary, v1 reports
`effective_passband_hz: 40000` and v2 reports `66000`. Our control therefore
over-filtered both, doing more work than the decoder and flattering the ratio.

This was the third error on this one gate: first `rate -v` then `sinc`, which
cannot undo prior aliasing; then `-r` fixing the output rate so a trailing
`rate` never applied; now the passband figure itself.

## The fix

`bench_dsd256_2x.py` no longer takes a passband. It asks the decoder, per
profile, via `--dsd-report effective_passband_hz`, and matches the control to
that. A hard-coded number was wrong twice, so there is no longer a number to
get wrong.

Validated before measuring, energy above each profile's own edge:

| arm | above its edge |
|---|---|
| v1 decoder, 40 kHz | 0.0000% |
| v1 matched control, 40 kHz | 0.0000% |
| v2 decoder, 66 kHz | 0.0000% |
| v2 matched control, 66 kHz | 0.0000% |
| legacy direct | 0.0023% above 40 kHz and above 66 kHz |

## Result

15 repetitions per arm after 3 warmups, CPU 8, clock sampled per arm,
confidence intervals from an independent bootstrap whose seed and iteration
count are recorded in the JSON.

| profile | output | vs legacy direct | vs matched control |
|---|---|---|---|
| v1, 40 kHz | 352800 | 3.78x [3.69, 3.82] | 3.80x [3.71, 3.80] |
| v1, 40 kHz | 176400 | 3.89x [3.82, 3.90] | 3.92x [3.84, 3.92] |
| v2, 66 kHz | 352800 | 3.70x [3.63, 3.70] | 3.70x [3.63, 3.70] |
| v2, 66 kHz | 176400 | 3.74x [3.74, 3.82] | 3.74x [3.74, 3.82] |

All eight clear the 2.00x target at the interval lower bound. v2 costs about 2
to 4 percent against v1 for 26 kHz more passband, which we read as the expected
price of the wider filter rather than a regression.

For v2 the matched and unmatched controls agree to the third digit, because at
66 kHz the control is barely filtering anything the direct path keeps. That is
the §10.7 question answered for both profiles: the speedup is not a
bandwidth artefact.

## Scope

Measurement only. Nothing here qualifies v2 or authorises promotion, and
`P15-v1-and-v2-composite-SRC-acceptance` remains open and is not ours to close.
Figures are from one host and are not a property of the code alone.

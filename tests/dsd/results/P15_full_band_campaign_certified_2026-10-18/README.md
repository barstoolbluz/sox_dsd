# P15 full-band campaign, fully certified (2026-10-18)

Every one of the 11,516 canonical intervals carries a PASS certificate.
Nothing OPEN, nothing missing.

    PYTHONPATH=tests/dsd python3 tests/dsd/p15_full_band_campaign.py \
      --output <dir> --start <i*206> --limit 206 --interval-seconds 300

56 shards on the Threadripper, using the prover delivered in
`sox_ng_P15_high_rate_FULL_SOURCE_2026-10-18`.

| verdict | count |
|---|---|
| `PASS-LOCAL-STOP-SOURCE` | 8666 |
| `PASS-LOCAL-BAND` | 2850 |
| `OPEN` | 0 |
| missing a receipt | 0 |

Verified against `canonical_plan('1000')` rather than by counting files:
every canonical interval has a receipt and every receipt is a PASS. The
48 kHz family, which held every remaining interval and stood at 24.7%,
is 4685 of 4685.

## Against the three preceding runs

| run | coverage | OPEN |
|---|---|---|
| 2026-10-17 partial | 5112 of 11516, 43 wedged, 6361 unattempted | 731 |
| 2026-10-18 complete | 11516 | 4681 |
| this run | 11516 | **0** |

The difference is the prover, not the hardware or the budget. The previous
implementation could not finish at any budget we tried; this one cleared the
entire residue in well under an hour and appears not to have needed the
300 s allowance.

## One campaign, one prover version

Earlier coverage was a union stitched across four deliveries at different
proof versions. This is a single uniform run, which is why we re-ran all
11,516 rather than only the 3,527 that were outstanding.

## What we verified, and what we did not

We verified coverage and disposition: that every canonical interval is
present and certified. We did not independently re-derive the mathematics
behind any individual certificate. The receipts carry aggregate outward
bounds and counters rather than per-leaf transcripts, as the delivery's own
report states.

## Scope

Local continuous-interval certificates under the unchanged section 8.6.1
limits. This completes the spectral half of
`P15-v1-and-v2-composite-SRC-acceptance` locally. It does not close the
gate: the arbitrary-input FFT4G execution-roundoff obligation is open, and
the disposition is the authority's. Release remains BLOCKED and v2 off by
default.

# P15 full-band campaign, partial run (2026-10-17)

5112 of 11516 interval receipts. The campaign was stopped, not completed.
`P15-v1-and-v2-composite-SRC-acceptance` remains OPEN and nothing here
changes it.

    PYTHONPATH=tests/dsd python3 tests/dsd/p15_full_band_campaign.py \
      --output <dir> --start <i*206> --limit 206

56 shards over the canonical 11516-job plan, one per core, on the
Threadripper. Receipts are deterministic: recomputing an interval produced a
byte-identical file, and no receipt contains a clock, host, seed or timing.
Contention therefore affects duration, not verdicts.

## Result

| verdict | count |
|---|---|
| `PASS-LOCAL-STOP-SOURCE` | 3989 |
| `PASS-LOCAL-BAND` | 392 |
| `OPEN` | 731 |
| receipts | **5112** |
| non-terminating | **43** |
| never attempted | **6361** |

The first 5112 receipts came at roughly 300/min. Then the rate fell to zero
and stayed there.

## The 43

At the stop, 43 shards each had one interval that had run about 3h05m
elapsed, 3h01m CPU, 97% CPU, 226-231 MB RSS, and returned nothing. They were
computing, not blocked. `--max-nodes` and `--max-paths` bound the search
structure rather than runtime, so a hard interval does not fail fast; it
runs until something kills it.

The remaining 6361 were never attempted. A worker walks its shard in order,
so one non-terminating interval stops the 205 behind it. Those 6361 are
unknown, not hard.

**All 43 are 48 kHz-family output rates: 48000, 96000, 192000, 384000.
None is a 44.1 kHz-family rate.** The 44.1 kHz family returned 4420
receipts; the 48 kHz family returned 692. The split is the fractional
native-to-output ratio.

`SUMMARY.json` lists all 43 by cell, mode, rate and interval.

## What we are not claiming

That the 43 cannot be proven, that the 6361 are hard, or that 14.3% is the
true OPEN rate for a completed campaign. Only the 43 were observed to
run without returning. The rest is unmeasured.

We may also have the cause wrong. The 44.1/48 split is what the data shows;
that exact-rational denominators are what blows up is our reading of it, and
we have not instrumented the proof to confirm where the time goes.

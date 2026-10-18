# P15 full-band campaign, complete coverage (2026-10-18)

Every one of the 11,516 canonical intervals has a receipt. This is the first
complete run; the 2026-10-17 partial reached 5,112 and stalled.

    PYTHONPATH=tests/dsd python3 tests/dsd/p15_full_band_campaign.py \
      --output <dir> --start <i*206> --limit 206 --interval-seconds 60

56 shards, one per core group, on the Threadripper at tree ee78b89f.

## Result

| verdict | count |
|---|---|
| `PASS-LOCAL-STOP-SOURCE` | 5495 |
| `PASS-LOCAL-BAND` | 1340 |
| **proven** | **6835** |
| `OPEN` | 4681 |

The 40.6% OPEN rate supersedes the 14.3% from the partial run. That earlier
figure was computed over only the cheap 44% that completed, and we flagged at
the time that it should not be extrapolated. It should not have been.

## The OPEN set is two different things

    3907  interval_wall_clock_budget_exhausted
     774  operator_path_precondition

The second kind is a structural refusal. More wall-clock does not touch it.

It concentrates on one output rate. The eight cells holding the most OPEN
intervals are all `pcm384000`, across every profile and every native rate.
`SUMMARY.json` carries the full breakdown by cell and by output rate.

## What a bigger budget buys: measured, not assumed

48 intervals that returned OPEN/timeout at 60 s, spread across the 12
worst-affected cells, re-run at 600 s. Receipts in `budget-sample/`.

| | |
|---|---|
| converted to `PASS-LOCAL-BAND` | 36 |
| timed out again | 12 |

So three quarters of the timeouts are budget-bound rather than
unprovable at this method. We have not extrapolated that into the headline
counts above, and it is a sample of 48.

If the ratio held across all 3907, roughly 2900 would convert and about 1000
would not; with the 774 structural refusals that would leave a residue near
1800. That is arithmetic on a sample, not a measurement, and the only way to
know is to run the full 600 s pass.

## Scope

Local continuous-interval certificates under the unchanged section 8.6.1
limits. Nothing here closes a gate. `P15-v1-and-v2-composite-SRC-acceptance`
remains OPEN, release BLOCKED, v2 off by default.

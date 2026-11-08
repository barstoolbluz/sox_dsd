# Eighth-order v1 encoder at DSD512 and DSD1024 (2026-11-07)

From this change, the default encoder at DSD512 and DSD1024 is `encode.mastering.v1.dsd512` / `.dsd1024`, the eighth-order recurrence used at DSD64–256. It replaces the seventh-order v2 CLANS-7 that P21 bound on 2026-10-23.

## Why v1 was held back

v1 failed two checks, both at the old 0.5 modulator mapping:

- **DSD1024:** on 1.6 s of full-scale DC (P17 training fixtures `04-dc-positive` and `05-dc-negative`), the state ran away at native frame 33,108,316 (`docs/dsd/handoffs/P19_DSD1024_V2_CORRECTION_2026-10-21.md`).
- **DSD512:** in a 3,600-second nominal soak, the minimum count of ones in a 28-bit window was 6, against the gate of 7–22 (`tests/dsd/results/P19_OPERATOR_QUALIFICATION_2026-10-22/`).

v2 CLANS-7 passed both checks. It costs noise above 40 kHz. On a 997 Hz tone with binary64 input, its residual was about 41 dB higher at DSD512 and 37 dB higher at DSD1024 (`docs/dsd/experiments/DSD512_SDM_ORDER_STUDY_2026-10-22.md`).

## What changed

Since 1.1.0, the default encode applies a 0.9 gain after interpolation and clips at 0.45. Under that mapping, v1 passes both checks.

Evidence is in `tests/dsd/results/V1_HIGH_RATE_ENCODE_2026-11-07/`.

The tests ran on the release source with v1 bound first. They used `tests/dsd/test_p10.c` with `P10_CLI_GAIN=1`, which calls `lsx_pcmdsd_set_gain(lsx_pcmdsd_default_warn_gain())` and `lsx_pcmdsd_set_clip(1)`. The diff is in `gates/build.diff`.

That switch exists only in the test build; it is not part of this change. Every gained run logs `P10_CLI_GAIN gain=0.9… clip=0.45…` to stderr.

### DC (`gates/dc/`)

| Case | Mapping | Result |
|---|---|---|
| P17 DC fixtures, 1.6 s, both polarities, both clocks | 0.5 (control) | All 4 reproduce the P17 output digests. DSD1024 runs away at frame 33,108,316. |
| Same fixtures | 0.9 gain, 0.45 clip | 4/4 complete |
| 60 s DC at source levels 1.0, 0.9, 0.8 and 0.7, both polarities, both clocks, unguarded and guarded | 0.9 gain, 0.45 clip | 32/32 complete |

None of the gained cases had a failure, a non-finite state, or an `excursions28` outside 4–24.

Negative DC at levels 1.0 and 0.9 reaches `min_ones28` 5–6. At 0.8 and below, the minimum is 7 or more. The 7–22 gate applies to the nominal soak program, not to full-scale DC. P20 recorded the same minimum of 6 for v2 CLANS-7 on negative DC.

### Soak (`gates/soak/`)

Each run is 3,600 s of the nominal program (`--soak-nominal-v2`), run by `p17_soak_run.py` and assessed by `p17_soak_assess.py --require-sustained`.

| Run | Mapping | Clock | min / max ones28 | Longest run | Assessor |
|---|---|---|---|---|---|
| `d512-control` | 0.5 | DSD512 | 6 / 22 | 10 | FAIL |
| `d512-cli` | 0.9 gain, 0.45 clip | DSD512 | 7 / 21 | 8 | PASS_SOAK_INPUT_GATE |
| `d1024-cli` | 0.9 gain, 0.45 clip | DSD1024 | 7 / 21 | 8 | PASS_SOAK_INPUT_GATE |

`d512-control-final.state` is byte-identical to the operator's `P19_OPERATOR_QUALIFICATION_2026-10-22/soak/d512-v2-final.state`. The intermediate per-minute snapshots are omitted; their digests are in each `*-assess.json`.

### Real tracks (`real-tracks/`)

A build of 1.1.0 with the same binding (`real-tracks/build.txt`) encoded 200 tracks (100 CD, 100 hi-res) through `sox IN -r RATE -t dsf /dev/null`, as decoded and raised to a 0 dBFS peak, at DSD512 and DSD1024.

All 800 runs exited 0 with no `FAIL` line. Track identities are hashes; the audio is private and not included.

## Limits

- The soak passes sit at the gate's lower edge (min 7).
- One deterministic soak program, one host, and the default build's kernel tiers.
- The v2 rows stay qualified and are reachable by exact id from the library. They are no longer in `dsd_rates`, so the CLI cannot select them.

# Eighth-order v1 encoder at DSD512 and DSD1024 (2026-11-07)

From this change, the default encoder at DSD512 and DSD1024 is `encode.mastering.v1.dsd512` / `.dsd1024`, the eighth-order recurrence used at DSD64–256. It replaces the seventh-order v2 CLANS-7 that P21 bound on 2026-10-23.

## Why v1 was held back

v1 failed two checks, both at the old 0.5 modulator mapping:

- **DSD1024:** on 1.6 s of full-scale DC (P17 training fixtures `04-dc-positive` and `05-dc-negative`), the state ran away at native frame 33,108,316 (`tests/dsd/results/P17_qualification_2026-10-21/guards/training/45158400/`; `docs/dsd/handoffs/P19_DSD1024_V2_CORRECTION_2026-10-21.md` gives "approximately 33.1 million").
- **DSD512:** in a 3,600-second nominal soak, the minimum count of ones in a 28-bit window was 6, against the gate of 7–22 (`tests/dsd/results/P19_OPERATOR_QUALIFICATION_2026-10-22/`).

v2 CLANS-7 passed both checks, at a cost in noise. On a 997 Hz tone with binary64 input (`tone-997--6` in `tests/dsd/phases/p20_audio_compare.py`), its fitted residual was 40.99 dB higher at DSD512 and 37.47 dB higher at DSD1024 (`tests/dsd/results/P20_OPERATOR_QUALIFICATION_2026-10-22/README.md`). At DSD512, 99.97% of that residual lies between 40 and 88.2 kHz (`docs/dsd/experiments/DSD512_SDM_ORDER_STUDY_2026-10-22.md`).

## What changed

Since 1.1.0, the default encode applies a 0.9 gain after interpolation and clips at 0.45. Under that mapping, v1 passes both checks. In the nominal soak the gain alone does it: the program peaks at 0.36 under the gain, so the clip never engages.

Evidence is in `tests/dsd/results/V1_HIGH_RATE_ENCODE_2026-11-07/`.

The tests ran on tag `sox_dsd-1.1.0` with v1 bound first (`gates/build.txt`). They used `tests/dsd/native/test_p10.c` with `P10_CLI_GAIN=1`, which calls `lsx_pcmdsd_set_gain(lsx_pcmdsd_default_warn_gain())` and `lsx_pcmdsd_set_clip(1)`. The diff is in `gates/build.diff`.

That switch exists only in the test build; it is not part of this change, so the soaks cannot be rerun from this tree as is. The guarded DC renders can: `--render` mode `guarded-cli` applies the same gain and clip with the guard bounds. The unguarded (`training`) renders have no equivalent mode. Every gained run logs `P10_CLI_GAIN gain=0.9… clip=0.45…` to stderr.

### DC (`gates/dc/`)

| Case | Mapping | Result |
|---|---|---|
| P17 DC fixtures, 1.6 s, both polarities, both clocks | 0.5 (control) | All 4 reproduce the P17 output digests. DSD1024 runs away at frame 33,108,316. |
| Same fixtures | 0.9 gain, 0.45 clip | 4/4 complete |
| 60 s DC at source levels 1.0, 0.9, 0.8 and 0.7, both polarities, both clocks, unguarded and guarded | 0.9 gain, 0.45 clip | 32/32 complete |

None of the gained cases had a failure or a non-finite state, and every one has `excursions28` = 0 (no 28-bit window outside 4–24).

Some DC cases at levels 1.0 and 0.9 fall outside the 7–22 band that the soak gate applies to its nominal program:
- negative DC at levels 1.0 and 0.9 reaches `min_ones28` 6 at DSD1024, and 5–6 at DSD512;
- positive DC at level 1.0 at DSD512 reaches `max_ones28` 23.

At 0.8 and below, every case is within 7–22. For comparison, P20 recorded a minimum of 6 for v2 CLANS-7 on negative DC (`docs/dsd/handoffs/P20_DSD512_V2_CORRECTION_2026-10-22.md`); v1 at DSD512 reaches 5.

### Soak (`gates/soak/`)

Each run is 3,600 s of the nominal program (`--soak-nominal-v2`), run by `p17_soak_run.py` and assessed by `p17_soak_assess.py --require-sustained`.
`gates/soak/launcher.log` is an **empty, zero-byte placeholder**; it is
not independent launch evidence. The individual `*-execution.json`,
`*-stdout.log`, `*-stderr.log`, and `*-assess.json` receipts are the
available run evidence. Their limitations and recorded host fields still
apply; no missing launch log has been reconstructed.

| Run | Mapping | Clock | min / max ones28 | Longest run | Assessor |
|---|---|---|---|---|---|
| `d512-control` | 0.5 | DSD512 | 6 / 22 | 10 | FAIL |
| `d512-cli` | 0.9 gain, 0.45 clip | DSD512 | 7 / 21 | 8 | PASS_SOAK_INPUT_GATE |
| `d1024-cli` | 0.9 gain, 0.45 clip | DSD1024 | 7 / 21 | 8 | PASS_SOAK_INPUT_GATE |

`d512-control-final.state` is byte-identical to the operator's `P19_OPERATOR_QUALIFICATION_2026-10-22/soak/d512-v2-final.state`. The intermediate per-minute snapshots are omitted; their digests are in each `*-assess.json`.

### Real tracks (`real-tracks/`)

A build of 1.1.0 with the same binding (`real-tracks/build.txt`) encoded 200 tracks (100 CD, 100 hi-res) through `sox IN -r RATE -t dsf /dev/null` at DSD512 and DSD1024, at two levels: as decoded, and raised to a 0 dBFS sample peak.

All 800 runs exited 0 with no `FAIL` line. This is an **encode-completion**
result, not evidence of lossless preservation of input peaks: in the 400
`peak0` runs, 194 emitted SoX's input-stage `balancing clipped` warning
(97 distinct tracks at each rate), with 1 to 3,936 clipped input samples
reported per run. This clipping occurred upstream of `pcmdsd` and is
separate from the 0.45 modulator clip/warn count. These runs cannot prove
that the sample-peak normalization preserved the original PCM waveform.
Track identities are hashes; the audio is private and not included.

## `--dsd-clip error` keeps the gain at DSD512/1024

`--dsd-clip error` turns off the 0.45 clip, and in 1.1.0 it also turned off the 0.9 gain. With v1 bound, that would leave the encoder at the 0.5 mapping where it fails. So with the high-rate **v1** selected, `--dsd-clip error` keeps the 0.9 gain (`lsx_pcmdsd_strict_keeps_default_gain`). High-rate v2 still uses gain 1 in strict mode as in 1.1.0. The 0.5 envelope is unchanged: for PCM-origin input, the high-rate v1 gain allows a pre-gain interpolated peak up to about 1.11, where the earlier v2 strict path refused those above 1.0. DSD-origin encoding uses a different reference scale. With the gain, sustained PCM input stays at or below 0.45, and only intersample overs between 0.45 and 0.5 reach the modulator. `--headroom DB` still replaces the gain.

`cli-paths/` runs 5 s of full-scale DC (both polarities), a 997 Hz sine hard-clipped at 0 dBFS, and a 0 dBFS 1 kHz square. Each runs under five option sets at all five rates, on 1.1.0 (`sox_dsd-1.1.0.jsonl`) and on an **earlier, pre-v2-pin review
snapshot** (`release-1.1.1.jsonl`). The latter is not evidence from the final
branch. Its FAIL lines contain the old headroom hint because it predates patch
0005; source code with the corrected absolute hint was not used for that run:

- **1.1.0:** DC completes under every option set at every rate, with v2 at DSD512/1024 and v1 below.
- **Historical pre-v2-pin snapshot, `--dsd-clip error`:** DC completes at every rate. At DSD512/1024 the clipped sine is now accepted, where 1.1.0 refused it as an overload; its overs stay inside the envelope after the gain.
- **Historical pre-v2-pin snapshot, `--headroom 0 --dsd-clip error`:** this explicitly asks for the 0.5 mapping, and full-scale DC trips the state guard at DSD512 (native frame 107,185,624) and DSD1024 (frame 23,447,904). The encode stops with an error. These runs targeted `/dev/null`; they do not establish that no bytes were written before failure. A separate regression tests removal of a partial regular DSF output.
- **Default, `--headroom 0` and `--auto-headroom`:** these complete every input at every rate on both builds. The clip or the measured cut keeps the input at or below 0.45.
- **Square wave under either strict option set:** refused as an interpolation overload on both builds.

## Limits

- The soak passes sit at the gate's lower edge (min 7).
- One deterministic soak program, one host, and the default build's kernel tiers.
- At DSD512/1024, `--dsd-clip error --headroom 0` with sustained full-scale DC
  reproduces a v1 state-guard failure. Other explicit cuts below 0.91515 dB
  exceed the qualified gain mapping but were **not** individually tested for
  guard failure; the input-dependent outcome must not be assumed.
- This original evidence preceded the v2-pin corrective change. The v2 rows
  remain qualified and are now selectable by exact CLI ID at both rates;
  `--encode mastering` still selects v1.

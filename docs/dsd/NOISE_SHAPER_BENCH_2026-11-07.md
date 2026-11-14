# SoX DSD noise shapers measured through the real conversion chain (2026-11-06)

This report describes two pieces of work on SoX DSD 1.1.0 (commit `27b17b93e`, tag `sox_dsd-1.1.0`) and states what we found. The numbers come from the files named in each section. The interpretation is ours and may be wrong; the tables are there so it can be checked. The evidence files live in the bench's `results/` directory unless another path is given. That directory, the bench tools and the paths shown as `<local>/…` are on the authors' machine and are not published with this repository.

**Updated 2026-11-10 for SoX DSD 1.1.1.**
- 1.1.1 changed the default encoder at DSD512 and DSD1024, so the bench's default route was rerun at those two rates on 1.1.1 (§2, "1.1.1 rerun"). Its rows are added to the DSD512 and DSD1024 tables, and finding 5 covers them.
- Nothing else **in the encoder paths measured by this report** changed in 1.1.1. This does not describe unrelated changes, such as the release's DSD-to-PCM decoder defaults:
  - `src/sdm.c` changed only in a comment, so every legacy shaper row stands.
  - The default profiles at DSD64, DSD128 and DSD256 are unchanged, so their default rows are also the 1.1.1 default.
- Evidence for the rerun is under `results-1.1.1/`. These **27 tagged-1.1.1 benchmark jobs** are distinct from the **800 DSD512/DSD1024 real-track encodes in Run C** (§1), which used an altered 1.1.0 test build rather than the released 1.1.1 executable. Their results should not be described as the same test population.

**Updated 2026-11-13 for rate-specific DSD512 and DSD1024 tables.**
- The eighth-order tables that 1.1.1 first bound at DSD512 and DSD1024 are the DSD256 SDM-8 coefficients run on faster clocks, so their noise-transfer zeros sit at 2 and 4 times their DSD256 frequencies. Round03 re-placed the zeros for each rate, and the 1.1.1 source revised on 2026-11-13 binds `xz-k1p75` at DSD512 and `xz-k2` at DSD1024 (§5). The version number is unchanged; 1.1.1 source from before that revision, including the `sox_dsd-1.1.1` tag as released on 2026-11-09, binds the first tables.
- The same change removed the optional CLANS-7 encoder (this report's "1.1.0 default encoder (v2)") and the v1/v2 labels from the program. The labels stay in this report where they name what was measured.
- The bench's default route was rerun at DSD512 and DSD1024 with the new tables (§2, "Round03 rerun"). Its rows are added to the DSD512 and DSD1024 tables as "1.1.1 default, round03 tables", and finding 5 covers them. The rows labelled "1.1.1 default encoder (v1)" now describe the first 1.1.1 tables, which the revised source no longer uses.
- Nothing else in the encoder paths measured here changed. The patch leaves the legacy filter tables untouched, and on our identity checks the default at DSD64, DSD128 and DSD256 produces the same bits as before (§5).

## Background: what SoX DSD 1.1.0 uses at each rate

- `sox in.wav -r RATE out.dsf` uses the qualified `pcmdsd` encoder: `encode.mastering.v1.*` (the sdm-8 filter) at DSD64, DSD128 and DSD256, and `encode.mastering.v2.*` (a CLANS-7 recurrence) at DSD512 and DSD1024. It scales input by 0.9 (−0.915 dB) and clips interpolated overs at 0.45 in modulator units (0.5 = 0 dBFS), with a warning.
- The **individual low-level filters compared in this bench** are selected through the legacy route `sox in.wav -t dsf -r RATE out.dsf rate -v RATE sdm -f NAME`, where NAME is `sdm-4`…`sdm-8` or `clans-4`…`clans-8`. Users can separately select a **qualified composite encoder profile** with `--encode PROFILE` or `pcmdsd -p PROFILE`; that is not selection of an arbitrary low-level `sdm` filter. The legacy filters' coefficient tables were designed for DSD64, DSD128 and DSD256. At DSD512 and DSD1024 the legacy route uses the DSD256 tables (`sdm_find_filter` in `src/sdm.c` picks the highest design rate at or below the output rate). The legacy route runs without the state guard by default.
- In the source, the unqualified `encode.mastering.v1.dsd512` and `v1.dsd1024` profiles (P17 candidate tables: the legacy DSD256 sdm-8 coefficients bound to the faster clocks) are annotated: "v1.dsd512 failed the sustained nominal gate at min28 6, and v1.dsd1024 is the defective eighth order" (`src/pcmdsd.c`).
- **In 1.1.1** those two v1 profiles were qualified under the default 0.9 gain and 0.45 clip, and bound as the default at DSD512 and DSD1024. This makes the eighth-order v1 the default at all five rates. Run C below was part of that qualification; see `docs/dsd/V1_HIGH_RATE_ENCODE_2026-11-07.md` in the source.
  - The v2 CLANS-7 profiles remained qualified and selectable by exact ID with `--encode`, until the 2026-11-13 revision removed them.
  - The default path's 0.9 gain and 0.45 clip ceiling are unchanged, and so is the legacy route.
  - One gain change does not affect the bench: in strict mode (`--dsd-clip error`), 1.1.1 keeps the 0.9 gain for the v1 default at DSD512 and DSD1024, where 1.1.0's strict mode used unity gain.
- **Since 2026-11-13** the revised 1.1.1 source has one composite encoder, SDM-8 `mastering`, at all five rates, with rate-specific tables at DSD512 and DSD1024 (§5). Strict mode now keeps the 0.9 gain at every rate. The bench uses the default warn mode, so this does not affect it either. The legacy route is unchanged.

## 1. Real-music stability runs

**Inputs.** 200 tracks: 100 CD at 44.1 kHz and 100 hi-res (34 at 96 kHz, 66 at 192 kHz). The source records are in `<local>/sox_dsd-rate-passband/cli-transient-2026-10-30/real/`.

**Command.** `sox [-v G] in.wav -r RATE` with DSF output. Run A wrote DSF files. Runs C and D, and run B after its first 41 tracks, encoded to `-t dsf /dev/null`.

**Levels.** Each track was encoded twice: as decoded (`asis`), and raised with `-v` so its **sample** peak is 0 dBFS (`peak0`). Sample-peak scaling does not measure intersample peaks, and completion of this step does not establish that the original PCM waveform was preserved.

| Run | Build | Rates | Runs | Non-zero exits | Result file (sha256 prefix) |
|---|---|---|---|---|---|
| A | pre-release head `6e511ee` (`<local>/sox_dsd-guard-qual/logs/head.txt`). Per git, it differs from 1.1.0 only in the clip ceiling and gain at the other three rates. | DSD128, DSD256 | 800 | 0 | `<local>/sox_dsd-guard-qual/real-default/results.jsonl` (86b6a11f960853ca) |
| B | 1.1.0 | DSD64, DSD512, DSD1024 | 1,200 | 0 | `<local>/sox_dsd-allrate-qual/real-default/results.jsonl` (57cd4e41174a869f) |
| C | local test build: tag `sox_dsd-1.1.0` plus an uncommitted diff that binds `encode.mastering.v1.dsd512/1024` (sdm-8 order, P17 tables) by default instead of v2. Not for release; diff in `<local>/sox_dsd-sdm8-high-qual/build.txt`. | DSD512, DSD1024 | 800 | 0 | `<local>/sox_dsd-sdm8-high-qual/real-default/results.jsonl` (58444d497a2d350d) |
| D | round03 corpus build B2, a local test build that binds `xz-k1p75` at DSD512 and `xz-k2` at DSD1024 (§5). Not for release. | DSD512, DSD1024 | 800 | 0 | `<local>/sox_dsd-rate-passband/round03-highrate/corpus/results.jsonl` (f9f4cc58ddf18e81), configs `sdm8-k1p75@512` and `sdm8-k2@1024` |

- No run reported a non-zero exit. This establishes completion under the tested conditions, not unconditional modulator stability or preservation of input peaks.
- **Interpolated-sample clipping in the qualified encoder** is warned and clamped at the 0.45 modulator-unit ceiling. The number of tracks that hit this ceiling is the same at every rate: 62 of 200 `asis`. At `peak0` it is 160 (DSD64), 172 (DSD128) and 186 (DSD256, DSD512, DSD1024). The DSD512 and DSD1024 counts pool runs B and C, whose interpolated clip counts are identical (next item). The worst single channel is 68,678,220 clipped interpolated samples, at DSD1024 `peak0`.
- Run D's interpolated clip counts and `-v` gains equal Run C's on all 800 matching runs, and SoX's `balancing clipped` warning appears in 194 of its 400 `peak0` encodes and none of its `asis` encodes, the count Run C reports (last item). Both are set ahead of the modulator, so the new tables do not change them.
- Run C's interpolated clip counts equal Run B's on all 800 matching runs. Both use the same gain and 0.45 ceiling ahead of their different modulators. Matching counts do not establish that the modulators produce identical bitstreams.
- **Separate input-stage clipping:** The high-rate qualification record (`docs/dsd/V1_HIGH_RATE_ENCODE_2026-11-07.md`, “Real tracks”) reports SoX's `balancing clipped` warning in **194 of Run C's 400 `peak0` encodes**, with 1–3,936 clipped *input* samples per affected run. Those events occur upstream of `pcmdsd`; they are not the interpolated-sample counts above. The 800 successful Run C encodes therefore cannot demonstrate lossless preservation of the peak-raised source waveform.

## 2. Shaper bench through the real chain

**Routes.** Each of 18 inputs was encoded through:
- each of the 10 legacy shapers, by the legacy route above;
- the 1.1.0 default encoder (`sox IN -r RATE OUT.dsf`);
- `ref`, the same rate chain with no shaper: `sox -D IN -t s32 -r RATE - rate -v RATE`. This is the 32-bit integer stream the legacy shaper is fed.

**Rates.** All five, except that DSD1024 music was trimmed to 3 tracks to keep the run short: `023f1618…` (192 kHz), `058059e2…` (96 kHz) and `fb82c06c…` (44.1 kHz). DSD1024 music figures therefore cover a different track set from the other rates (§3.1). All 972 jobs in the final results exited 0.

**1.1.1 rerun (2026-11-10).**
- **What ran:** only the default route, at DSD512 and DSD1024, on the `sox_dsd-1.1.1` tag as released on 2026-11-09. Its `src/` tree is `e0080b63`, identical to the released commit (`90fe3df68` before the 2026-11-10 history rewrite, `5aa805eed` after).
- **Same as the original:** host, tools, inputs and the DSD1024 music subset: 27 jobs (18 at DSD512 and 9 at DSD1024).
- **Outcome:** all 27 exited 0. The only warning was the WAV-header note that every original job also printed; no input-clipping warning was observed in these jobs.

**Round03 rerun (2026-11-13).**
- **What ran:** the same 27 default-route jobs, on a local test build of `main` at `e38519b94` with the two round03 tables bound (`results-r03/command.txt`; the build is described in `results-r03/identity-final/README.txt`).
- **The revised 1.1.1 source gives the same bits.** We encoded all 27 jobs' inputs with that build and with the revised source (git tree `88a27418…`), and the DSF files were identical in every case (§5).
- **Outcome:** all 27 exited 0, with only the WAV-header warning.

**Inputs.**
- Synthetic signals, 44.1 kHz mono, 8 s, analysed from 1 s to 7 s:
  - digital silence;
  - 1 kHz sine at −1, −20 and −60 dBFS;
  - CCIF twin tone 19 + 20 kHz at a −1 dBFS peak;
  - DIN 45403 twin tone 250 Hz + 8 kHz, 4:1, at a −1 dBFS peak.
- Music: 12 excerpts, each the loudest 12 s by RMS of one track.
  - The tracks are 6 CD, three 96 kHz and three 192 kHz. Five of the CD tracks are the loud masters that tripped the state guard at DSD256 in an earlier, unreleased build (`<local>/dist-dsd256-guard-handoff/SoX_DSD_DSD256_Guard_2026-11-04/README.md`, "Observed" item 2).
  - Each excerpt was faded over 0.25 s at each end. Four bands were then removed by zeroing FFT bins: 700–1300, 2700–3700, 6800–8800 and 13500–16500 Hz. Last, it was scaled to a −1 dBFS sample peak.
  - Anything in the removed bands after encoding is noise or distortion the encode added under real program load. The inner part of each band, 120 Hz in from each edge, is measured, from 1.5 s to 10.5 s.

**Analysis.**
- Welch PSD of the ±1 bitstream (or the s32 stream for `ref`), in float64, with a Kaiser window (β = 25), 5.38 Hz bins and 50% overlap.
- Levels are in dBFS re a full-scale sine, with 0 dBFS = amplitude 0.5 for one-bit streams and 2³¹ for s32. A −20 dBFS sine reads −20.0 through the legacy route and −20.9 through the default encoder; the difference is its 0.915 dB cut.
- Noise is integrated over 20 Hz–20 kHz with each signal's tones, harmonics and intermodulation products removed, then scaled back to the full band width.
- Distortion figures are line power minus the local median noise (±300 Hz), relative to the tones; for DIN, relative to the 8 kHz tone. "—" means the estimate came out at or below zero: no product rose above the noise. It does not mean the product is absent (§3.2).
- **How we decide whether a distortion reading means anything.** We did not calibrate the estimator. The rule below is our judgment, not something derived from the estimator's statistics. `derived.txt` §H applies it mechanically to every gap against `ref` at DSD256 and up, for the routes §3 discusses (sdm-6, sdm-7, sdm-8, clans-8 and the default) on twelve fields. Its last line checks `ref`'s products at every rate. §3 quotes its verdicts.
  - **What `ref`'s products are.**
    - The synthetic signals repeat exactly: every 441 samples, or 882 for DIN.
    - sox reads them into 32-bit integers by rounding, without dither (`SOX_FLOAT_64BIT_TO_SAMPLE`, called at `src/raw.c:145`). So the rounding error repeats too.
    - That error is a comb of lines every 100 Hz (50 Hz for DIN), not random noise. Every harmonic and intermodulation product the bench measures lies on that comb.
    - `derived.txt` §I simulates this rounding alone, with no `rate` and no shaper, and reproduces `ref`'s readings:
      - its THD on all three sines within 0.24 dB, and its DIN figure within 0.17 dB;
      - its second and third harmonics at −20 and −60 dBFS within 1.0 dB;
      - its largest spur levels within 0.33 dB.
      - The remaining four fields (the second and third harmonics at −1 dBFS, and CCIF d2 and d3) agree within 4.1 dB.
    - Rounded with TPDF dither instead, the same signals lose four of these products, and the rest drop by 7.1 to 18.4 dB (§I).
    - So `ref`'s distortion readings are the input's own rounding lines. Every route carries the same lines: the legacy routes are fed the `ref` stream, and the default reads the same integers and scales them with the signal, then passes them through its own interpolation.
  - **Gap:** the route's reading minus `ref`'s, at the same frequency. The verdicts rest on this comparison.
    - A route that adds nothing at that frequency reads what `ref` reads.
    - A route that adds a product reads above `ref`, or below it if the product partly cancels the input's line.
    - The product adds to the line with an unknown phase, so the gap does not give the product's own size.
  - **Margin** (§G): the product's level per line, minus the record's in-band error spread flat over the product's 102 Hz window.
    - On the synthetic records that error is not flat, so the margin cannot tell a product from a rounding line. `ref`'s largest in-band line sits 7.7 to 10.4 dB above the flat estimate on every synthetic record (§I). Its own third harmonic at −20 dBFS, a rounding line, has a margin of +4.0 to +4.6 dB (§G).
    - What the margin does show is how large a reading is beside the record's total error. We use it only to withhold a verdict, never to make one.
    - On music, at DSD256 and up, the in-band noise of `ref` and the legacy routes on the floor is flat within 0.27 dB across the four notches (§H3). The 1.1.0 default's noise at DSD512 and DSD1024 is less flat, varying by −2.13 to +2.06 dB. The 1.1.1 default's is flat within 0.04 dB (`results-1.1.1/derived.txt` §H3).
  - **Clear of the noise:** a margin of at least 5 dB, which leaves room for that ±2 dB. Half of CCIF d3 lies at 21 kHz, above the band, so for d3 we also require the route's 20–50 kHz noise density to be no higher than its in-band density, taken from its −20 dBFS sine record (§G2).
  - **Established excess:** a gap above `ref` of at least 1.5 dB, with the route's product clear.
    - 1.5 dB is a threshold we chose, not a bound on scatter.
    - On the routes whose own noise lies far below `ref`'s, the readings carry little random scatter: sdm-8's largest gap on any field at DSD256 and up is 0.38 dB (§I). There a gap reflects something the route itself puts at that frequency.
    - Readings above `ref` whose products sit below the noise reach 1.9 dB for sdm-7 and clans-8, 3.0 dB for the default and 10.0 dB for sdm-6 (§H). The rule does not count them. That does not show the products are absent.
  - **Established deficit:** a gap of at most −1.5 dB, with `ref`'s product clear.
    - No `ref` product is clear at any rate (§H), so no deficit can be established.
    - A reading below `ref` would in any case mean the route partly cancels the input's line, not that it adds less distortion of its own.
  - **Consequence:** an established excess means the route adds a product at that frequency. Its size in dB above `ref` is not established.
  - **THD limits:** THD averages 19 harmonics, so one strong harmonic is understated. Each line is clamped at zero before summing, so a THD made only of noise reads high and tracks the noise.
  - **Readings below `ref`.**
    - Among the legacy shapers, 15 readings fall more than 0.5 dB below `ref`, the largest by 14.7 dB (clans-7 CCIF d2 at DSD256). In 36 cases a legacy route shows no product where `ref` shows one (§B).
    - In the 36 "none" cases the route's noise is 3.3 to 88.8 dB above `ref`'s. We read them as masking.
    - In 13 of the 15 below-`ref` cases the route's noise is 1.0 to 13.0 dB above `ref`'s. The estimate subtracts the local noise, so where the route's own noise is comparable to the line, its reading scatters. These 13 may be scatter, partial cancellation, or both.
    - The other two (sdm-7 and sdm-6 at DSD256) are at `ref`'s noise and fall 1.3 and 1.4 dB below it. We read them as partial cancellation by the shaper's own products, not scatter (§I):
      - sdm-7 adds noise 34.7 dB below `ref`'s on that record. Spread flat, that is 29.4 dB below the line, so even wholly in anti-phase it could lower the line by at most 0.30 dB. The noise figure excludes the harmonic lines, so the 1.3 dB needs a line of sdm-7's own at that frequency.
      - sdm-6 adds noise 11.8 dB below `ref`'s, which could lower the line by up to 2.71 dB, so the bound does not settle it. We think scatter unlikely, but did not test it.
    - The default is not fed the `ref` stream, so its readings below `ref` could be real differences, but none passes the rule. Across all rates there are 8 for the 1.1.0 default (5 of them at DSD512 and DSD1024), and 4 with the 1.1.1 default (1 at DSD512 and DSD1024) (§B, and `results-1.1.1/derived.txt` §B).
    - The default's 2 "none" cases are at DSD64, where its noise is 53 dB above `ref`'s.
- Fields not shown in the tables (the second and third harmonics, and THD at −20 and −60 dBFS) are in `results.jsonl`. Figures cited from them come from `derived.txt`.
- The music figure is the mean noise density in the notches, expressed as dBFS over a 20 kHz bandwidth, so it compares directly with the other noise columns.
- Ultrasonic bands are measured on the −20 dBFS sine.
- We did not measure the analyser's own floor. The silence figures far below the 32-bit floor are reported as computed.

**Files.**
- Results: `results.jsonl` (sha256 e5b6c988c5eb2376…).
- Derived figures: `derived.txt`, written by `../tools/derive.py` from `results.jsonl`, the music inputs' WAV headers and the synthetic input WAVs (for §I). It records the sha256 of `results.jsonl`, and its sections are cited as §A to §I, including §E2, §F2, §G2, §H2, §H3 and §H4.
- First pass, before 22 DSD1024 music jobs were rerun: `first-pass.jsonl` and `bench-first-pass.log`.
- Host: `host.txt`, an AMD Threadripper 7970X, x86-64 with AVX-512. It was recorded the day after the run, on the same machine.
- Tools: `../tools/make_inputs.py`, `bench.py`, `dsdpsd.py`, `report.py`.
- **1.1.1 rerun** (`results-1.1.1/`):
  - `results.jsonl` (sha256 3befe5b12ad889a4…) holds the 27 new rows.
  - `combined.jsonl` (sha256 b1ad7d19a66ba9d6…) is the 972 original rows plus the new ones. The 1.1.0 default rows at DSD512 and DSD1024 are renamed `default-1.1.0` there.
  - `derived.txt` and `tables.txt` come from the unmodified `derive.py` and `report.py` run on `combined.jsonl`.
  - `tables-1.1.0.txt` is `report.py` on the original `results.jsonl`, for comparison.
  - Also: `host.txt`, and the log `../logs/bench-1.1.1.log`.
  - The one-job smoke run before the rerun is in `../smoke-1.1.1/results.jsonl`.
  - Figures cited as `results-1.1.1/derived.txt` come from there. Otherwise § references are to the original `derived.txt`.
- **Round03 rerun** (`results-r03/`):
  - `results.jsonl` (sha256 f52ce62b25d02f7f…) holds the 27 new rows.
  - `combined.jsonl` (sha256 7dfc095e26fc2e95…) is the 999 rows of `results-1.1.1/combined.jsonl` plus the 27 new ones. The earlier default rows at DSD512 and DSD1024 are renamed `default-1.1.0` and `default-1.1.1` there.
  - `derived.txt` and `tables.txt` come from the unmodified `derive.py` and `report.py` run on `combined.jsonl`. `report.py` prints values below −299 dBFS as `<fl`; the table below gives the value from `results.jsonl`.
  - The log is `../logs/bench-r03.log`, and the one-job smoke run is in `../smoke-r03/results.jsonl`.
  - Figures cited as `results-r03/derived.txt` come from there.

### Results

At DSD64, DSD128 and DSD256 the "1.1.0 default encoder" row is also the 1.1.1 default (unchanged profiles). At DSD512 and DSD1024 the 1.1.0 row describes the CLANS-7 encoder, which the revised 1.1.1 source no longer has. The "1.1.1 default encoder (v1)" row describes the first 1.1.1 tables, and the "1.1.1 default, round03 tables" row is the current default.

### DSD64 (2822400 Hz)

| route | music notch median | music notch worst | n | silence noise | noise @ −20 dBFS sine | THD @ −1 dBFS (dB) | CCIF d2 (dB) | CCIF d3 (dB) | DIN IMD (dB) | 20–50 kHz | 50–100 kHz | 0.1–1 MHz |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sdm-8 | -140.3 | -140.1 | 12 | -147.3 | -141.5 | -155.4 | — | -150.5 | -140.2 | -49.9 | -18.1 | 5.7 |
| sdm-7 | -138.5 | -138.1 | 12 | -142.3 | -136.9 | -145.9 | -172.5 | -146.3 | -143.8 | -57.3 | -19.9 | 5.9 |
| sdm-6 | -130.0 | -129.6 | 12 | -129.3 | -129.3 | -141.1 | — | -138.2 | -130.4 | -61.6 | -23.3 | 6.0 |
| sdm-5 | -118.2 | -117.9 | 12 | -125.8 | -118.6 | -129.4 | -157.2 | -126.9 | -118.3 | -62.6 | -28.4 | 6.0 |
| sdm-4 | -106.6 | -106.4 | 12 | -107.4 | -108.0 | -118.2 | -136.1 | -116.8 | -123.1 | -63.3 | -34.9 | 6.0 |
| clans-8 | -118.5 | -118.3 | 12 | -123.0 | -121.6 | -133.8 | — | -149.2 | -122.4 | -61.6 | -32.5 | 6.2 |
| clans-7 | -117.2 | -117.0 | 12 | -121.5 | -117.0 | -127.0 | -150.0 | -134.4 | -125.4 | -59.2 | -34.5 | 6.2 |
| clans-6 | -123.3 | -123.1 | 12 | -123.1 | -122.9 | -136.4 | -149.2 | -135.8 | -126.1 | -61.0 | -32.0 | 6.2 |
| clans-5 | -113.8 | -113.6 | 12 | -119.7 | -114.2 | -127.3 | — | -126.1 | -116.5 | -61.3 | -33.9 | 6.1 |
| clans-4 | -105.6 | -105.5 | 12 | -108.8 | -106.9 | -118.0 | — | -117.5 | -123.4 | -63.2 | -37.5 | 6.2 |
| 1.1.0 default encoder | -140.4 | -140.1 | 12 | -147.3 | -141.6 | -156.0 | — | -151.1 | -140.4 | -50.0 | -18.2 | 5.8 |
| no shaper (32-bit chain floor) | -196.4 | -194.7 | 12 | — | -194.6 | -204.4 | -215.3 | -220.8 | -193.8 | -207.4 | -208.6 | -196.3 |

### DSD128 (5644800 Hz)

| route | music notch median | music notch worst | n | silence noise | noise @ −20 dBFS sine | THD @ −1 dBFS (dB) | CCIF d2 (dB) | CCIF d3 (dB) | DIN IMD (dB) | 20–50 kHz | 50–100 kHz | 0.1–1 MHz |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sdm-8 | -190.2 | -189.5 | 12 | -197.9 | -190.5 | -201.4 | -216.7 | -202.8 | -190.0 | -100.7 | -47.0 | -3.2 |
| sdm-7 | -183.3 | -183.0 | 12 | -187.3 | -181.8 | -188.2 | — | -190.8 | -185.2 | -102.4 | -54.6 | -3.0 |
| sdm-6 | -169.1 | -168.7 | 12 | -173.3 | -168.4 | -177.2 | -196.2 | -175.1 | -166.7 | -100.8 | -59.3 | -2.9 |
| sdm-5 | -151.3 | -151.0 | 12 | -158.8 | -151.8 | -159.8 | — | -157.2 | -148.2 | -95.7 | -60.7 | -3.0 |
| sdm-4 | -133.7 | -133.4 | 12 | -136.7 | -135.1 | -142.5 | -160.3 | -142.1 | -148.6 | -90.6 | -61.9 | -2.8 |
| clans-8 | -180.2 | -179.9 | 12 | -185.4 | -181.6 | -194.5 | -210.7 | -198.3 | -180.5 | -95.5 | -54.3 | -2.5 |
| clans-7 | -161.4 | -161.1 | 12 | -165.2 | -160.8 | -165.0 | -188.9 | -167.8 | -162.7 | -86.2 | -50.0 | -3.3 |
| clans-6 | -160.8 | -160.6 | 12 | -162.6 | -160.3 | -171.3 | -188.9 | -170.9 | -161.6 | -94.4 | -58.3 | -2.4 |
| clans-5 | -146.7 | -146.5 | 12 | -152.3 | -147.2 | -157.8 | — | -156.1 | -147.0 | -91.9 | -59.4 | -2.5 |
| clans-4 | -131.0 | -130.8 | 12 | -132.0 | -132.4 | -141.3 | -160.3 | -141.3 | -147.7 | -88.0 | -60.2 | -2.5 |
| 1.1.0 default encoder | -190.4 | -189.9 | 12 | -197.9 | -190.9 | -201.7 | -213.1 | -203.5 | -190.8 | -100.8 | -46.9 | -3.1 |
| no shaper (32-bit chain floor) | -196.5 | -194.7 | 12 | — | -194.6 | -204.3 | -214.5 | -220.2 | -193.9 | -208.2 | -211.7 | -199.1 |

### DSD256 (11289600 Hz)

| route | music notch median | music notch worst | n | silence noise | noise @ −20 dBFS sine | THD @ −1 dBFS (dB) | CCIF d2 (dB) | CCIF d3 (dB) | DIN IMD (dB) | 20–50 kHz | 50–100 kHz | 0.1–1 MHz |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sdm-8 | -196.5 | -194.8 | 12 | -248.8 | -194.6 | -204.4 | -215.2 | -220.7 | -193.9 | -151.9 | -97.8 | -11.2 |
| sdm-7 | -196.5 | -194.7 | 12 | -232.4 | -194.6 | -204.5 | -215.3 | -219.8 | -193.9 | -147.5 | -99.7 | -11.5 |
| sdm-6 | -196.2 | -194.6 | 12 | -212.7 | -194.3 | -203.5 | -214.7 | -210.9 | -195.3 | -139.9 | -98.4 | -11.8 |
| sdm-5 | -184.1 | -183.7 | 12 | -191.5 | -184.4 | -189.7 | — | -187.4 | -178.4 | -128.8 | -93.8 | -12.4 |
| sdm-4 | -160.7 | -160.4 | 12 | -161.4 | -162.3 | -166.6 | -180.7 | -166.1 | -172.5 | -117.6 | -88.9 | -12.8 |
| clans-8 | -196.5 | -194.8 | 12 | -233.6 | -194.6 | -204.4 | -215.2 | -220.5 | -194.0 | -140.1 | -92.5 | -11.8 |
| clans-7 | -193.1 | -192.2 | 12 | -199.5 | -191.7 | -196.6 | -230.0 | -200.7 | -191.0 | -118.7 | -79.4 | -14.5 |
| clans-6 | -181.8 | -180.8 | 12 | -182.4 | -182.6 | -186.7 | -198.4 | -183.1 | -176.8 | -115.9 | -78.4 | -14.8 |
| clans-5 | -164.9 | -164.6 | 12 | -172.8 | -165.3 | -170.8 | -195.4 | -168.8 | -160.3 | -111.1 | -80.0 | -14.7 |
| clans-4 | -152.4 | -151.7 | 12 | -152.3 | -154.7 | -156.6 | -171.7 | -154.5 | -161.2 | -109.7 | -81.1 | -14.9 |
| 1.1.0 default encoder | -197.3 | -195.7 | 12 | -248.8 | -195.5 | -204.4 | -215.7 | -217.9 | -194.0 | -152.0 | -97.8 | -11.2 |
| no shaper (32-bit chain floor) | -196.5 | -194.8 | 12 | — | -194.6 | -204.5 | -215.2 | -220.9 | -193.9 | -208.7 | -215.0 | -202.0 |

### DSD512 (22579200 Hz)

| route | music notch median | music notch worst | n | silence noise | noise @ −20 dBFS sine | THD @ −1 dBFS (dB) | CCIF d2 (dB) | CCIF d3 (dB) | DIN IMD (dB) | 20–50 kHz | 50–100 kHz | 0.1–1 MHz |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sdm-8 | -196.5 | -194.8 | 12 | -252.3 | -194.6 | -204.4 | -215.1 | -220.2 | -193.9 | -208.7 | -151.9 | -15.5 |
| sdm-7 | -196.5 | -194.8 | 12 | -237.0 | -194.6 | -204.4 | -215.1 | -220.6 | -193.9 | -205.9 | -147.6 | -17.2 |
| sdm-6 | -196.3 | -194.6 | 12 | -216.4 | -194.5 | -202.8 | -215.2 | -209.5 | -193.1 | -192.8 | -139.8 | -19.1 |
| sdm-5 | -188.0 | -187.4 | 12 | -194.2 | -187.2 | -194.8 | -218.4 | -192.6 | -179.1 | -173.4 | -128.8 | -22.1 |
| sdm-4 | -164.4 | -163.9 | 12 | -162.5 | -166.8 | -165.2 | -192.2 | -172.8 | -159.4 | -153.4 | -117.6 | -26.9 |
| clans-8 | -196.5 | -194.8 | 12 | -236.9 | -194.6 | -204.3 | -215.1 | -219.6 | -193.9 | -205.3 | -140.1 | -24.9 |
| clans-7 | -194.5 | -193.4 | 12 | -203.1 | -193.3 | -200.2 | -217.5 | -205.6 | -186.5 | -177.6 | -118.8 | -26.7 |
| clans-6 | -183.0 | -181.8 | 12 | -184.0 | -186.4 | -183.8 | -195.4 | -183.6 | -180.9 | -168.4 | -116.2 | -26.1 |
| clans-5 | -169.1 | -168.8 | 12 | -175.8 | -168.5 | -175.7 | -205.1 | -174.1 | -161.0 | -154.6 | -111.0 | -28.7 |
| clans-4 | -155.2 | -154.1 | 12 | -152.6 | -159.2 | -155.2 | -170.8 | -161.2 | -149.0 | -145.9 | -109.7 | -27.0 |
| 1.1.0 default encoder (v2) | -195.1 | -194.0 | 12 | -203.1 | -194.0 | -200.7 | -214.7 | -206.3 | -187.1 | -176.9 | -118.7 | -26.7 |
| 1.1.1 default encoder (v1) | -197.3 | -195.7 | 12 | -252.3 | -195.5 | -204.4 | -215.7 | -217.9 | -194.0 | -209.2 | -151.9 | -15.5 |
| 1.1.1 default, round03 tables | -197.3 | -195.7 | 12 | -261.8 | -195.5 | -204.4 | -215.7 | -218.0 | -194.0 | -208.1 | -150.8 | -15.6 |
| no shaper (32-bit chain floor) | -196.5 | -194.8 | 12 | — | -194.6 | -204.4 | -215.1 | -220.4 | -193.9 | -209.0 | -217.9 | -204.6 |

### DSD1024 (45158400 Hz)

| route | music notch median | music notch worst | n | silence noise | noise @ −20 dBFS sine | THD @ −1 dBFS (dB) | CCIF d2 (dB) | CCIF d3 (dB) | DIN IMD (dB) | 20–50 kHz | 50–100 kHz | 0.1–1 MHz |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sdm-8 | -198.2 | -194.9 | 3 | -256.8 | -194.6 | -204.4 | -215.4 | -220.4 | -193.9 | -209.1 | -218.3 | -28.1 |
| sdm-7 | -198.2 | -194.8 | 3 | -239.3 | -194.6 | -204.4 | -215.4 | -218.6 | -193.9 | -209.1 | -208.6 | -39.0 |
| sdm-6 | -198.1 | -194.8 | 3 | -218.5 | -194.6 | -202.7 | -215.4 | -220.4 | -191.9 | -207.3 | -192.9 | -45.9 |
| sdm-5 | -193.0 | -191.5 | 3 | -198.8 | -190.7 | -199.5 | -215.2 | -188.9 | -183.7 | -189.3 | -173.4 | -49.4 |
| sdm-4 | -165.9 | -165.4 | 3 | -162.6 | -167.3 | -165.0 | -192.4 | -172.7 | -156.9 | -169.5 | -153.4 | -52.7 |
| clans-8 | -198.2 | -194.8 | 3 | -241.2 | -194.6 | -204.3 | -215.4 | -220.1 | -193.8 | -209.1 | -207.6 | -46.6 |
| clans-7 | -196.9 | -194.1 | 3 | -205.5 | -193.8 | -202.4 | -215.1 | -197.5 | -189.3 | -199.6 | -177.4 | -43.7 |
| clans-6 | -184.3 | -183.0 | 3 | -188.2 | -188.5 | -183.1 | -212.7 | -199.7 | -174.8 | -186.8 | -168.3 | -42.0 |
| clans-5 | -174.9 | -174.6 | 3 | -180.6 | -173.2 | -181.3 | -209.3 | -170.5 | -166.0 | -169.8 | -154.4 | -47.5 |
| clans-4 | -156.3 | -155.2 | 3 | -152.7 | -159.8 | -154.9 | — | -161.1 | -146.5 | -161.6 | -145.5 | -46.0 |
| 1.1.0 default encoder (v2) | -197.4 | -194.9 | 3 | -205.5 | -194.5 | -202.9 | -216.0 | -198.4 | -189.9 | -199.5 | -177.5 | -43.8 |
| 1.1.1 default encoder (v1) | -198.9 | -195.8 | 3 | -256.7 | -195.5 | -204.4 | -215.7 | -217.9 | -194.0 | -209.4 | -221.7 | -28.1 |
| 1.1.1 default, round03 tables | -198.9 | -195.8 | 3 | -302.8 | -195.5 | -204.4 | -215.7 | -218.0 | -194.0 | -209.4 | -202.5 | -28.2 |
| no shaper (32-bit chain floor) | -198.2 | -194.9 | 3 | — | -194.6 | -204.4 | -215.4 | -220.5 | -193.9 | -209.1 | -221.0 | -206.8 |

"silence noise" for `ref` is "—" because the 32-bit path carries digital silence as exact zeros.

## 3. What we found

1. **Through the legacy route, the 32-bit sample path sets the measured noise floor.** This is the floor of the *experiment's integer-reference and rate chain*, not a fundamental DSD noise floor or a general ceiling on higher-precision processing.
   - With any signal present, no legacy-route encode reads lower noise than `ref` by more than 0.0002 dB, at any rate, on any input or track (`derived.txt` §H4).
   - The `ref` row:
     - With the −20 dBFS sine, it is −194.6 dBFS.
     - As the music-notch median it is −196.4 to −196.5 dBFS on the 12 excerpts at DSD64 to DSD512, and −198.2 at DSD1024. The DSD1024 figure reflects its 3-track subset: the median of `ref` on those tracks is −198.1 to −198.2 at every rate (`derived.txt` §E). The floor is not lower at DSD1024.
     - Per track, `ref`'s notch floor matches quantising the input to 32 bits at its source rate, within 0.33 dB (`derived.txt` §E2). In theory that floor is −194.85 dBFS at 44.1 kHz, −198.23 at 96 kHz and −201.24 at 192 kHz.
     - So the medians depend on the mix of source rates. The 12-excerpt median lies between the CD and 96 kHz floors, and the DSD1024 subset median is its 96 kHz track.
   - Which shapers sit on this floor with a signal present:
     - From DSD256 up, sdm-6, sdm-7, sdm-8 and clans-8 do (§3.3), and only digital silence shows their own floors.
     - The lower-order shapers stay above it. At DSD256, sdm-5 reads −184.4 and sdm-4 −162.3 dBFS on the −20 dBFS sine.
     - At DSD64 and DSD128, every shaper's noise lies well above `ref` (§3.2).
   - Some legacy-route distortion readings fall below `ref`. §2 explains how we read them: as scatter where the route's own noise is high, and as partial cancellation by the shaper's own products where it is not.
   - The default encoder does its own interpolation rather than using the `rate` stream. In absolute terms it reads up to about 1 dB below `ref`: at DSD256, −195.5 vs −194.6 on the −20 dBFS sine, and −197.3 vs −196.5 on the music median.
   - Its signal is lower by the same amount (−20.92 vs −20.00 dBFS), so relative to the signal it matches `ref` within 0.14 dB (`derived.txt` §A):
     - on the sine, the noise is 174.62 dB below the tone for the default and 174.56 dB for `ref`;
     - adding the 0.92 dB level difference to the music median gives −196.37 vs −196.51.
   - Our reading is that the default's 0.915 dB input cut scales the noise from quantising the input to 32 bits along with the signal. It fits §E2: `ref`'s floor matches that quantisation, and at DSD256 the default reads 0.61 to 0.99 dB below `ref` on each track. We have not confirmed it in the code.
2. **On silence, sdm-8 has the lowest in-band noise of any shaper at every rate. With a signal present, its lead is visible only at DSD64 and DSD128; above that it ties with the floor.**
   - DSD64 music notch: sdm-8 −140.3, sdm-7 −138.5, sdm-6 −130.0, clans-6 −123.3, clans-8 −118.5, clans-7 −117.2 dBFS.
   - DSD128: sdm-8 −190.2, sdm-7 −183.3, clans-8 −180.2.
   - sdm-8 also reads lowest on THD and CCIF d3 at both rates, and sdm-7 reads lower than sdm-8 on DIN at DSD64 (−143.8 vs −140.2 dB).
     - At these rates the noise is shaped, so §G's flat-noise margins do not apply to the shapers and the rule of §2 cannot be checked for them.
     - A THD made of noise tracks the noise, so sdm-8's lower THD may simply follow its lower noise.
     - We treat none of these distortion rankings as established. The noise ranking stands.
   - At DSD128, sdm-8 shows a CCIF d2 product at −216.7 dB where sdm-7, sdm-5 and clans-5 show none. This does not count against sdm-8, because `ref` reads −214.5 dB at the same place. Any such product would be in the 32-bit stream before any shaper, and in our reading the other shapers' higher noise hides it. `ref`'s noise is flat at every rate (`derived.txt` §H3), so §G does apply to `ref`: its reading sits 1.1 dB below its window noise (`derived.txt` §G), so the product itself is not established.
   - The 1.1.0 default encoder matches sdm-8 at these rates within about 0.6 dB, on THD and on noise in absolute terms. Relative to its 0.92 dB lower signal, its noise is 0.5 to 0.8 dB higher than sdm-8's (`derived.txt` §A).
3. **From DSD256 up, sdm-6, sdm-7, sdm-8 and clans-8 sit on the 32-bit floor for noise, within 0.8 dB of `ref`, whenever a signal is present.**
   - **Noise with a signal** (`derived.txt` §H2), across the signal inputs and every music track: sdm-7, sdm-8 and clans-8 are within 0.01 dB of `ref`, and sdm-6 is within 0.78 dB.
   - **Silence** separates them. At DSD1024 the floors are sdm-8 −256.8, clans-8 −241.2, sdm-7 −239.3 and sdm-6 −218.5 dBFS.
   - **Distortion.** `derived.txt` §D lists every field more than 0.8 dB above `ref`, and §H applies the rule of §2:
     - sdm-8 has no field more than 0.8 dB above `ref`.
     - clans-8's third harmonic at −1 dBFS is 1.3 and 1.5 dB above `ref` at DSD512 and DSD1024. sdm-7's CCIF d3 is 1.1 and 1.9 dB above at DSD256 and DSD1024. Neither product is clear of the noise, so neither gap is established.
     - sdm-6 has one established excess: the third harmonic at −1 dBFS, 8.5, 11.1 and 11.7 dB above `ref` at DSD256, DSD512 and DSD1024. Its product stands 6.4 to 8.9 dB clear of its noise. As §2 explains, the size of that excess in dB above `ref` is not established.
     - sdm-6's other gaps are not established:
       - CCIF d3, by 10.0 and 10.9 dB at DSD256 and DSD512. Its margins are −0.8 and +0.8 dB, and at DSD256 its 20–50 kHz noise density is 52.7 dB above its in-band density.
       - THD, by 1.0 to 1.7 dB;
       - DIN, by 0.9 and 2.0 dB;
       - one harmonic at −60 dBFS (the third at DSD256 and DSD512, the second at DSD1024), by 1.6 to 3.6 dB.
4. **At DSD512 and DSD1024 the 1.1.0 default (v2 CLANS-7) sits 1.5 and 0.9 dB above the floor on the music median, and up to 3.65 dB on single tracks, rising with the source rate. It also adds distortion products.** The first 1.1.1 release kept this encoder as an option selectable by exact ID; the 2026-11-13 revision removed it. Finding 5 covers the 1.1.1 default.
   - **Noise.**
     - Music-notch median: −195.1 vs −196.5 at DSD512 and −197.4 vs −198.2 at DSD1024. Computed from unrounded values, that is 1.5 and 0.9 dB above `ref` in absolute terms (`derived.txt` §A).
     - Relative to its 0.92 dB lower signal, the gaps are 2.4 and 1.8 dB on music, and 1.5 and 1.0 dB on the −20 dBFS sine.
   - **The gap grows with the source rate** (`derived.txt` §E2). At DSD512 it is 0.70 to 0.79 dB on the CD tracks, 2.03 to 2.23 dB on the 96 kHz tracks and 3.55 to 3.65 dB on the 192 kHz tracks. At DSD1024 it is −0.06, +0.87 and +1.74 dB on its three tracks. These are absolute figures. Relative to the signal they are 0.92 dB larger: 4.46 to 4.56 dB on the 192 kHz tracks at DSD512.
   - **Distortion.** `derived.txt` §C lists every field against `ref`, and §H applies the rule of §2. Each excess below gives the gap above `ref`, then the margin.
     - Established at DSD512:
       - the third harmonic at −1 dBFS (15.2 dB above `ref`; margin 10.8 dB);
       - at −60 dBFS: THD (13.7; 13.2), the second harmonic (12.9; 13.2) and the third harmonic (15.2; 8.3).
     - Established at DSD1024:
       - the third harmonic at −1 dBFS (9.7; 5.7);
       - THD at −60 dBFS (13.9; 13.8);
       - CCIF d3 (22.1; 10.7).
     - Caveats on these margins:
       - The CCIF d3 margin at DSD1024 passes the rule, but it may be overstated. The noise at 18 and 21 kHz was not measured, and the evidence points both ways:
         - on music, the default's in-band noise at DSD1024 rises to 2.06 dB above its mean in the 13.6–16.4 kHz notch (§H3);
         - its 20–50 kHz average is 6.8 dB below its in-band density (§G2).
       - The second and third harmonics lie at 2 and 3 kHz. The default's noise on music is below its mean in the notches measured at 1 and 3 kHz (§H3), so those margins are, if anything, understated. At 2 kHz this is inferred, not measured.
       - THD's 19 harmonics span 2–20 kHz, where that noise reaches 1.94 dB (DSD512) and 2.06 dB (DSD1024) above its mean. Its margins of 13.2 and 13.8 dB leave room for that.
     - Not established:
       - CCIF d3 at DSD512 (14.1; margin 2.1, and its 20–50 kHz noise density is 15.3 dB above in-band);
       - DIN (6.8 and 4.0; margins 4.5 and 2.3);
       - THD at −1 dBFS (3.7; margin 1.0 at DSD512, and 1.4; margin −0.6 at DSD1024);
       - the second harmonic at −60 dBFS at DSD1024 (3.8; margin 4.7);
       - the −20 dBFS fields.
     - As §2 explains, the established entries are products the default adds. Their sizes in dB above `ref` are not established.
   - The default reads more than 0.5 dB below `ref` on 7 fields at DSD256 to DSD1024. None is established, because no `ref` product is clear of the noise. The two largest:
     - the third harmonic at −60 dBFS at DSD1024, 6.9 dB below, where the default's product is 13.2 dB under its noise;
     - the third harmonic on the −20 dBFS sine at DSD512, 2.7 dB below, where `ref`'s product has a margin of 4.4 dB, under the 5 dB threshold.
   - At DSD256, §H's only distortion excess for the default is CCIF d3, 3.0 dB above `ref`. It is not established: the margin is −7.5, and its 20–50 kHz density is 41.8 dB above in-band.
   - Through the legacy route, sdm-8 and clans-8 match `ref` within 0.8 dB on the CCIF d3, DIN and −1 dBFS THD columns at these rates.
5. **In 1.1.1 the default (eighth-order SDM-8, first tables and round03 tables alike) sits on the experiment's 32-bit floor at DSD512 and DSD1024, as it already did at DSD256, and has no distortion excess established by this report's detection rule.**
   - **Noise** (`results-1.1.1/derived.txt` §A):
     - Relative to the signal it matches `ref` within 0.01 dB on the −20 dBFS sine.
     - On the music median it is within +0.15 dB (DSD512) and +0.26 dB (DSD1024).
     - Its absolute readings are lower than `ref`'s by its 0.915 dB input cut, as at DSD256 (finding 1): −197.3 vs −196.5 and −198.9 vs −198.2 on the music median.
   - **Per track** it reads −0.95 to −0.59 dB from `ref` at DSD512, and −0.93 to −0.66 dB at DSD1024 (`results-1.1.1/derived.txt` §E2).
     - Relative to the signal that is −0.04 to +0.33 dB. The largest values are on the 96 kHz tracks, the same pattern as at DSD256.
     - The 1.1.0 default's gap, which rose to 3.65 dB on 192 kHz sources, is gone.
   - **Distortion.** At these rates the only gap above `ref` larger than 0.8 dB, the threshold §H lists, is CCIF d3: +2.5 dB at DSD512 and +2.6 dB at DSD1024 (`results-1.1.1/derived.txt` §C, §H). No other field reads more than 0.7 dB above `ref`. **“Not established” does not mean absent:** the estimator was not calibrated, and the rule's thresholds are judgments, not statistical confidence bounds.
     - Neither CCIF d3 gap is established: the margin is −7.5 dB at both.
     - The default reads +3.0 dB at DSD256, also not established.
     - Finding 4 established seven products for the 1.1.0 default: four at DSD512 and three at DSD1024. None of them is established for the 1.1.1 default. Six are within 0.7 dB of `ref`, and the seventh, CCIF d3 at DSD1024, is the unestablished +2.6 dB above.
   - **On silence** it matches legacy sdm-8: −252.3 vs −252.3 dBFS at DSD512 and −256.7 vs −256.8 at DSD1024.
   - **Just above the audio band** it is far quieter than the 1.1.0 default: −209.2 and −209.4 dBFS in 20–50 kHz, against −176.9 and −199.5.
   - **Above 100 kHz** it carries more energy than the 1.1.0 default (finding 6).
   - **With the round03 tables** (`results-r03/`), the default reads the same in-band as with the first 1.1.1 tables whenever a signal is present, lower on silence, and differently above the band:
     - **With a signal:** every §A and §E2 figure is unchanged at both rates. Every distortion field in §C is within 0.4 dB of the first tables' reading. CCIF d3 is +2.4 and +2.5 dB above `ref`, still not established (margin −7.6 dB, §H).
     - **On silence:** −261.8 dBFS at DSD512 and −302.8 at DSD1024 (as computed; `report.py` prints values below −299 as `<fl`), against −252.3 and −256.7 with the first tables. Both are below every legacy shaper's silence floor (sdm-8: −252.3 and −256.8).
     - **Above the band:** 20–50 kHz on the −20 dBFS sine reads −208.1 at DSD512, against −209.2 with the first tables and −209.0 for `ref`. 50–100 kHz reads −150.8 and −202.5, against −151.9 and −221.7. We read the 19.2 dB rise at DSD1024 as the cost of moving the zeros down from 4 to 2 times their DSD256 frequencies, which lifts the shaped noise sooner above the audio band; we have not checked this against the transfer function. The band is still far below the 0.1–1 MHz energy (finding 6).
6. **Ultrasonic energy.**
   - At DSD512 and DSD1024, sdm-8 puts the most energy in 0.1–1 MHz of any legacy route: −15.5 and −28.1 dBFS, against −26.7 and −43.8 for the 1.1.0 default.
   - The 1.1.1 default reads the same as sdm-8 there: −15.5 and −28.1 dBFS, which is 11.2 and 15.7 dB more than the 1.1.0 default.
   - The round03 tables do not change this: −15.6 and −28.2 dBFS (`results-r03/`). We expected this: every zero sits at k times its DSD256 frequency, the highest of which is 21.2 kHz (`zeros_hz` of the k = 1 design in the coefficient JSON, §5), so no table here has a zero above about 85 kHz. The measured change in this band is 0.06 dB at DSD512 and 0.03 dB at DSD1024.
   - This agrees with the 2026-10-23 DSD1024 audit (`tests/dsd/ntf_dsd1024/ADVERSARIAL_AUDIT_R1_2026-10-23.md`), which measured SDM-8 at 14.94 dB more raw power than CLANS-7 in 0.5–1 MHz. That audit tested the research SDM-8, not these tables (§4), so the two agree only in direction.
   - At DSD64 to DSD256 the 0.1–1 MHz figures of all shaper routes and the default lie within 4 dB of each other.
   - In-band rank does not predict ultrasonic rank: clans-8 is on the floor in-band at DSD1024, yet reads −46.6 dBFS in 0.1–1 MHz, less than any default row.
   - At DSD64, sdm-8 and the default have the most noise just above the audio band: −49.9 and −50.0 dBFS in 20–50 kHz, against −57.3 to −63.3 for the other shapers.
7. **No shaper failed on any input in the final results.** That includes the 12 loud music excerpts at a −1 dBFS peak, at every rate.
   - Because the legacy route runs unguarded, a clean exit alone would not prove stability. The notch floors show no sign of divergence.
   - In the first pass, 22 DSD1024 music jobs failed and were rerun:
     - 20 had `sox` exit with `xmalloc: out of memory` under the bench's own per-process address-space cap (its first-pass value was not recorded);
     - 2 were `ref` jobs where the analyser received no output, and their cause was not recorded.
     - The rerun used a 24 GiB cap (`SOX_AS_LIMIT` in `tools/bench.py`).
   - The bench did not test sustained near-full-scale DC. The 2026-10-23 audit found that, without a guard, SDM-8 at DSD1024 goes nonfinite on full-scale DC: it passes at 0.95 and fails at 0.99.
8. **Memory cost of the legacy route** (`memory.txt`). Peak RSS of one `sox` process:
   - up to 8.54 GB at DSD1024 and 4.27 GB at DSD512, depending on input;
   - about 10 MB for the 1.1.0 default encoder at both rates (the 1.1.1 default's was not recorded);
   - the same for `rate -v RATE` alone, with no shaper, so the memory is in the `rate` effect.

## 4. Limits

- This is one host. The bench used one build (1.1.0), plus 1.1.1 and a round03 test build for the default route at DSD512 and DSD1024 only; the stability runs used four builds (§1). The bench used 12 music excerpts (3 at DSD1024), and the stability runs 200 tracks.
- No DAC or analog filter was measured. Whether noise above 100 kHz matters depends on hardware we have not characterised.
- **Narrowband lines.** The bench records the largest in-band line relative to the median noise. These readings appear in `results.jsonl`, but we have not investigated them:
  - On silence, low-order shapers show lines well above their own noise. clans-4 reads 29.6 dB (1044 Hz, −156.1 dBFS) at DSD256, 33.4 dB (2110 Hz) at DSD512 and 25.2 dB (4237 Hz) at DSD1024. clans-6 reads 23.7 dB (323 Hz) at DSD256 and 17.9 dB (684 Hz) at DSD512. sdm-4 reads 21.9 dB (334 Hz) at DSD512.
  - With the −20 and −60 dBFS sines, the lines near 9.55 kHz and 12.1 kHz, at about −208 dBFS, appear in `ref` at every rate. At DSD256 and up they also appear in the default route, which does not use the `rate` stream (`derived.txt` §F2). So they arise before both routes split. We think they come from quantising the input to 32 bits.
  - Of 33 readings centred on 48.4 Hz, 19 exceed 10 dB, ranging from 10.0 to 25.4 dB. They occur at all five rates, on silence and with signals (`derived.txt` §F, §F2).
    - They are not evidence of a 48 Hz line. The detector's window there spans 0 to 96.9 Hz, so it includes DC and the bins below 20 Hz that the noise band excludes.
    - We have not separated DC from any line in that window.
  - The detector's search starts at 16.1 Hz, below the band edge. The only records centred there are the five `ref` silence runs. Their spectrum is all zeros, so they carry no reading.
- The distortion estimator was not calibrated. The synthetic inputs were rounded to 32 bits without dither, so `ref`'s distortion readings are the input's own rounding lines. Every route is compared against those lines, not against a clean input (§2).
- The legacy shapers at DSD512 and DSD1024 run the DSD256 tables. Run C's sdm-8-order profiles use the same coefficients (the P17 candidate tables are the legacy DSD256 sdm-8 words), and Run D's are the round03 tables (§5). None of them is the research SDM-8 the audit tested. Results for one do not transfer to the others without checking.
- The round03 stability evidence (§5) is one-hour DC soaks at the operating level, short DC runs and 400 real-track encodes per rate (200 tracks at two levels). Four-hour soaks at the operating level and one-hour noise soaks of the finalists were started and stopped after a few minutes, before any finished; we decided not to run them. As with the first 1.1.1 tables, this shows bounded behaviour under tested conditions, not stability for any duration or signal. No coefficient certificate covers the new tables, and SoX's plan and report output give `null` for it at DSD512 and DSD1024.

## 5. Round03: rate-specific SDM-8 tables at DSD512 and DSD1024 (2026-11-11 to 2026-11-13)

Evidence is under `<local>/sox_dsd-rate-passband/round03-highrate/` unless another path is given. The research harness labels the candidates "screening" and "unqualified"; they describe the harness's own status, and nothing below is a formal qualification of the tables (§4).

**Design.** Each candidate keeps the DSD256 SDM-8 feedback coefficients `a` and multiplies every resonator coefficient `g` by (k/m)², where m is the clock's ratio to DSD256 (2 at DSD512, 4 at DSD1024). That places the noise-transfer zeros at k times their DSD256 frequencies. The first 1.1.1 tables are the case k = m, labelled `base`. k ran from 1 to 3 at DSD512 and from 1 to 3.5 at DSD1024. The chosen tables are `xz-k1p75` at DSD512 and `xz-k2` at DSD1024; their coefficient hashes are 07f187c77d15c886… and 777f361c07376cff…, the sha256 of Python's `json.dumps` of `a` and `g` as hex strings and `order` as an integer, with sorted keys and default separators (`<local>/sox_dsd-rate-passband/research/tests/dsd/shaper_optimization/stagec_sdm8_zero_rescale.json`). Rescaled CLANS-7 tables were screened alongside.

**Native screen** (`summary/stage1-table.txt`, from `summary/cells-*.json`). The harness drives the modulator directly at its native rate, with no PCM chain, so its figures are not comparable with §2's. Its readings cluster at about −287.7 dBFS, which we take to be its floor.
- In-band noise, in dBFS, up to 22.05 kHz, 40 kHz and 48 kHz:

| table | DSD512 22.05k | 40k | 48k | DSD1024 22.05k | 40k | 48k |
|---|---|---|---|---|---|---|
| `base` (first 1.1.1 tables) | −252.1 | −248.9 | −233.2 | −256.5 | −252.2 | −252.0 |
| `xz-k1` | −287.4 | −226.3 | −210.9 | −287.7 | −276.9 | −261.7 |
| `xz-k1p75` | −261.6 | −251.2 | −223.5 | −287.7 | −287.8 | −273.8 |
| `xz-k2` | (= `base`) | | | −287.6 | −287.7 | −282.3 |

- At DSD1024, `xz-k2` is within 0.1 dB of the harness floor to 40 kHz and lowest of all candidates to 48 kHz.
- At DSD512 no candidate is lowest in every cell. `xz-k1` is lowest to 22.05 and 24 kHz, `xz-k1p75` to 40 kHz, and `xz-k2p5` to 48 kHz (−233.4), with `base` at −233.2. `xz-k1p75` is 9.7 dB noisier than `base` to 48 kHz.
- In every cell the best SDM-8 candidate reads lower than the best CLANS-7 candidate.
- The screen's stress programmes failed once each for DSD512 `xz-k2p5` and DSD1024 `xz-k3p5`, and never for the chosen tables.

**Short DC runs** (`probes/dc-ensemble/`). Each run is 1.6 s of DC at ±0.9, ±0.95, ±0.99, ±0.999, ±0.9999, ±0.99999999995595 or ±1.0, with fade-ins of 0, 0.05 or 0.1 s: 42 runs per table. On this scale ±0.9 is 0.45 modulator units, where full-scale PCM lands after the 0.915 dB cut.
- At ±0.9, none of the 108 runs across the 18 SDM-8 tables in the ensemble (the 16 screened above plus two `opt-global-b15` tables outside this design) failed or left the 28-sample ones-density bounds. At ±0.95, 2 of 108 failed.
- Counting failures and density excursions, with the two separate ±1.0 probe runs in `native/` added (44 runs per table), `xz-k1p75` misbehaved in 7 of 44 runs at DSD512 and `xz-k2` in 8 of 44 at DSD1024, against 10 and 11 for `base`. All of them were at ±0.99 or above.

**One-hour soaks at the operating level** (`<local>/sox_dsd-rate-passband/logs/round03-soak-op-1h.log`). DC at ±0.9 for one hour of native time, in each polarity.
- DSD512: `xz-k1`, `xz-k1p75` and `xz-k2p5` completed both polarities. `base` failed on negative DC after 19.4 minutes of native time, and `xz-k1p25`, `xz-k1p5` and `xz-k3` each failed one polarity.
- DSD1024: `base`, `xz-k1` to `xz-k2` and `xz-k3` completed both polarities. `xz-k2p5` failed positive at 55.0 minutes and `xz-k3p5` negative at 5.8 minutes.
- At ±0.9999, above the operating level, one-hour soaks of `xz-k1`, `xz-k1p75`, `xz-k2` and `base` all failed within 6.3 s of native time (`<local>/sox_dsd-rate-passband/logs/round03-soak-final-policy*.log`). That is expected: the 0.915 dB cut exists because SDM-8 is not run there.
- Failure is not monotonic in k. One hour per polarity is a short test; it does not rank the tables that passed.

**Real music** (Run D, §1). Nine configurations, five of them CLANS-7, each encoded the 200 tracks at both levels: 3,600 runs on three local test builds, all with exit 0 (`corpus/results.jsonl`, `corpus/configs.json`). The two chosen tables account for 800 of them. The corpus did not separate the candidates.

**Choice.** We bound `xz-k2` at DSD1024 on the native screen. At DSD512 the choice between `xz-k1` and `xz-k1p75` was a judgment: `xz-k1` is quieter in the audio band and misbehaved in fewer short DC runs (2 of 44 against 7), `xz-k1p75` is quieter to 40 kHz, and both passed their operating-level soaks and the corpus.

**Integration** (`final-source/`). The revised 1.1.1 source (git tree `88a27418…`) binds the two tables in their own header. On our host it passed `make check-dsd-cli` and a strict `make check-dsd` (`build.txt`).
- The 27 default-route bench jobs give bit-identical DSF files from the final source and from the build §2 measured (`results-r03/identity-final/` in the bench directory).
- At DSD64, DSD128 and DSD256 in warn mode, and through the legacy `rate … sdm -f clans-7` route at DSD64 (with `--encode legacy` on the revised source), the revised source matched the earlier build bit for bit on a synthetic stereo signal. The patch leaves the legacy filter tables in `src/sdm.c` untouched.

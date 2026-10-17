## Production performance results

The accepted evidence covers **70 distinct configurations: 49 primary cases and 21 revised controls**, plus **2 diagnostic repeat records** identified by `case.repeat_of`. The primary/control configurations contribute 2,520 accepted conversions, including 2,100 timed conversions. The repeats contribute 132 accepted conversions, including 120 timed conversions. The combined total is 2,652 accepted conversions and 2,220 timed conversions across 72 case records. A diagnostic repeat is another observation of an existing configuration, not an additional distinct workload.

Accepted counts exclude partial rows and failed or truncated conversions. The recovered complete primary cases, replacement final short case, revised controls, and diagnostic repeats keep their separate source receipts. Every accepted conversion passed output-length and baseline-versus-candidate signed-32 sample-identity checks at matching parameters and buffer settings.

| CPU interval classification | Records | Wholly above 1 | Includes 1 | Wholly below 1 |
| --- | --- | --- | --- | --- |
| Primary configurations | 49 | 15 | 33 | 1 |
| Revised controls | 21 | 14 | 6 | 1 |
| All distinct configurations | 70 | 29 | 39 | 2 |
| Diagnostic repeat records | 2 | 0 | 2 | 0 |

These are counts of per-case descriptive intervals. The combined configuration row includes the primary and control rows; it is not a third set of tests. Repeat rows are kept separate, and the intervals are not simultaneous family-wise confidence bounds. Ratios are original time divided by candidate time, so values above one favor the candidate.

CPU relative MAD exceeds 2% in 129 of 140 primary/control arm distributions and 4 of 4 repeat arm distributions. Each arm distribution is the set of repeated baseline or candidate timings for one case. The virtual host was not qualified for frequency, interference, or isolation; these observations describe this run and are not a prepared physical-host performance guarantee.

### Representative PCM conversions

All seven rows use stereo PCM and very-high quality (`rate -v`). CPU times are independent arm medians in seconds. The paired ratio is computed from the timing pairs and need not equal the ratio of those two medians.

| Conversion (kHz) | Input audio (s) | Baseline CPU (s) | Candidate CPU (s) | Paired CPU speedup [95% interval] |
| --- | --- | --- | --- | --- |
| 44.1→48 | 60 | 0.239553 | 0.185416 | 1.26756× [1.21118, 1.30206] |
| 48→44.1 | 60 | 0.232348 | 0.183329 | 1.28295× [1.18365, 1.34608] |
| 44.1→96 | 60 | 0.346831 | 0.249034 | 1.37577× [1.32606, 1.41481] |
| 48→88.2 | 60 | 0.367287 | 0.279832 | 1.31168× [1.25622, 1.40362] |
| 176.4→192 | 45 | 0.670977 | 0.538381 | 1.25277× [1.17063, 1.33077] |
| 384→44.1 | 45 | 0.484589 | 0.460592 | 1.06367× [0.99702, 1.08199] |
| 44.1→88.2 | 60 | 0.170737 | 0.165286 | 1.02486× [0.976614, 1.05572] |

The following absolute values use **baseline → candidate** in each cell. Audio seconds per clock second measure conversion throughput; the audio duration does not multiply by channel count. Peak RSS is the median of per-child `wait4` maxima and includes the process-launch footprint.

| Conversion (kHz) | Audio s / CPU s | Audio s / wall s | Median peak RSS (KiB) |
| --- | --- | --- | --- |
| 44.1→48 | 250.466 → 323.597 | 249.978 → 322.952 | 31784 → 31784 |
| 48→44.1 | 258.233 → 327.28 | 257.64 → 326.538 | 32324 → 32332 |
| 44.1→96 | 172.995 → 240.931 | 172.75 → 240.441 | 29684 → 29688 |
| 48→88.2 | 163.36 → 214.414 | 162.716 → 214.131 | 29992 → 30020 |
| 176.4→192 | 67.0664 → 83.5839 | 67.0244 → 83.5087 | 33736 → 33616 |
| 384→44.1 | 92.8622 → 97.7004 | 92.7866 → 97.6072 | 34736 → 34604 |
| 44.1→88.2 | 351.418 → 363.007 | 350.525 → 362.053 | 29072 → 29064 |

### PCM buffer and quality controls

All twelve accepted PCM controls passed the execution, output-length and sample-identity checks. Buffer values are application bytes, not internal FIR input lengths. The reverse small-buffer control uses 128 bytes after the inherited 32/64-byte truncation was diagnosed; the valid forward control retains 32 bytes.

| Conversion (kHz) | Control | Input audio (s) | Paired CPU speedup [95% interval] |
| --- | --- | --- | --- |
| 44.1→48 | buffer 32 bytes; `rate -v` | 10 | 1.10481× [1.09983, 1.1164] |
| 48→44.1 | buffer 128 bytes; `rate -v` | 10 | 1.13151× [1.08026, 1.17969] |
| 44.1→48 | buffer 256 bytes; `rate -v` | 30 | 1.1942× [1.11637, 1.2203] |
| 48→44.1 | buffer 256 bytes; `rate -v` | 30 | 1.16942× [1.10179, 1.25112] |
| 44.1→48 | quality `rate -l` | 30 | 1.29349× [1.27972, 1.31721] |
| 48→44.1 | quality `rate -l` | 30 | 1.16306× [1.08669, 1.20812] |
| 44.1→48 | quality `rate -m` | 30 | 1.05304× [1.00083, 1.08535] |
| 48→44.1 | quality `rate -m` | 30 | 1.17961× [1.1508, 1.21956] |
| 44.1→48 | quality `rate -h` | 30 | 1.29488× [1.2025, 1.36555] |
| 48→44.1 | quality `rate -h` | 30 | 1.19805× [1.16909, 1.27983] |
| 44.1→48 | quality `rate -u` | 30 | 1.23296× [1.1043, 1.26912] |
| 48→44.1 | quality `rate -u` | 30 | 1.21229× [1.19965, 1.22468] |

### Native DSD and stereo continuity observations

The first table keeps all three six-channel mastering-v2 decodes to 176.4 kHz, including unfavorable results. These native-family observations must not be presented as evidence that every DSD route benefits from the rational-FIR change.

| Source | Baseline CPU (s) | Candidate CPU (s) | Paired CPU speedup [95% interval] |
| --- | --- | --- | --- |
| DSD64 | 0.888736 | 0.933293 | 0.975706× [0.928325, 0.997304] |
| DSD128 | 1.7875 | 1.81235 | 0.995395× [0.938507, 1.05284] |
| DSD256 | 3.35218 | 3.35566 | 0.996032× [0.97529, 1.04173] |

Four DSD256 stereo continuity controls retain both mastering versions and 176.4/352.8 kHz outputs. Their comparator is this session's frozen CLI. They do not replace the historical physical-host comparison or transfer its speedup to a rebuilt legacy comparator.

| Mastering profile | Output (kHz) | Baseline CPU (s) | Candidate CPU (s) | Paired CPU speedup [95% interval] |
| --- | --- | --- | --- | --- |
| v1 | 176.4 | 1.08791 | 1.07437 | 0.990731× [0.970026, 0.996971] |
| v1 | 352.8 | 1.10515 | 1.12058 | 0.99408× [0.960009, 1.02319] |
| v2 | 176.4 | 1.13979 | 1.12038 | 0.995659× [0.91235, 1.03766] |
| v2 | 352.8 | 1.14221 | 1.14437 | 1.00299× [0.972197, 1.01333] |

The five explicit DSD FIR dispatch controls (scalar, SSE2, AVX1, AVX2, AVX-512) have paired median CPU ratios from 1.01213× to 1.02941×. Their complete intervals and absolute timings remain in `BENCHMARK_TABLES.md`; every below-one interval is also listed below.

### Every unfavorable CPU or wall interval

The following table includes every accepted original or diagnostic-repeat observation whose CPU **or** wall 95% interval lies wholly below one. An original adverse result stays here even when its repeat has an interval that includes one. A short wall-only result is identified explicitly; it does not establish a sustained CPU-throughput regression.

| Case | Evidence set | Clock | Baseline median (s) | Candidate median (s) | Paired speedup [95% interval] | Interpretation |
| --- | --- | --- | --- | --- | --- | --- |
| `pcm_short_88200` | Primary | Wall | 0.00370104 | 0.0038623 | 0.966509× [0.929514, 0.998642] | Short wall-only observation |
| `dsd64_mastering.v2_176400` | Primary | CPU | 0.888736 | 0.933293 | 0.975706× [0.928325, 0.997304] |  |
| `dsd64_mastering.v2_176400` | Primary | Wall | 0.889288 | 0.933726 | 0.975512× [0.928357, 0.997604] |  |
| `dsd256_mastering_v1_176400_stereo_continuity` | Control | CPU | 1.08791 | 1.07437 | 0.990731× [0.970026, 0.996971] |  |
| `dsd256_mastering_v1_176400_stereo_continuity` | Control | Wall | 1.08851 | 1.07486 | 0.990807× [0.969939, 0.997071] |  |

### Thirty-pair diagnostic repeats

The recorded policy selected sustained cases whose original per-case CPU interval lay wholly below one. Each diagnostic uses 30 timing pairs and retains the same conversion parameters. The table reports **every** diagnostic alongside its original 15-pair observation, for both clocks. This is a stability check on selected cases, not replacement evidence or a correction for testing many cases.

| Original case | Original CPU ratio [95% interval] | Repeat CPU ratio [95% interval] | Original wall ratio [95% interval] | Repeat wall ratio [95% interval] |
| --- | --- | --- | --- | --- |
| `dsd64_mastering.v2_176400` | 0.975706× [0.928325, 0.997304] | 0.983373× [0.951577, 1.00279] | 0.975512× [0.928357, 0.997604] | 0.982593× [0.95142, 1.00292] |
| `dsd256_mastering_v1_176400_stereo_continuity` | 0.990731× [0.970026, 0.996971] | 1.01044× [0.980686, 1.04566] | 0.990807× [0.969939, 0.997071] | 1.01039× [0.980651, 1.04571] |

The repeat of `dsd64_mastering.v2_176400` has a CPU interval that includes one. The original wholly below-one CPU interval was not reproduced in this repeat; this is **not proof of no regression**, and the original result remains part of the evidence.

The repeat of `dsd256_mastering_v1_176400_stereo_continuity` has a CPU interval that includes one. The original wholly below-one CPU interval was not reproduced in this repeat; this is **not proof of no regression**, and the original result remains part of the evidence.

The full per-case medians, dispersion, throughput, RSS and intervals are in `BENCHMARK_TABLES.md`. The authoritative full-precision values are in `benchmark-summary.json`; narrative tables use six significant digits. The consolidated summary used for this section has SHA-256 `f8c98b616ccc2ba67e98539cfc8a734f38c6b6dc44294b4be8303707a88ea56e`.

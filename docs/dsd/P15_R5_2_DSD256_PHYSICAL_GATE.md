# SoX-NG P15 R5.2 — DSD256 matched physical gate review

19 October 2026. **Physical release gate OPEN.** This source-only R5.2 supplement does not alter production DSP or P15 R5.1 seven-part adjudication. It adds an independent receipt checker, an executable physical-host runbook, and deterministic tests.

## What was actually found

A **physical** AMD Ryzen Threadripper 7970X measurement was recorded on 16 October 2026 under `tests/dsd/results/P15_ps_matched_physical_2026-10-16/{comparator,bench}`. The original `README.md` reports governor `performance`, boost disabled, CPU 8 pinned, 15 repetitions per arm, and two warmups. The machine facts are **operator-reported**, not independently hardware-attested. Three command arms were measured per cell: six-channel DSD256 `dsdpcm`, legacy direct `rate -v`, and a staged `rate -v 352800` → full-passband `sinc` → final `rate -v` control. The matched control uses v1 P/S 40/80 kHz and v2 P/S 66/80 kHz, not the older 20-kHz control. All passband edge bins are included.

The new independent source-specific `p15_r52_physical_benchmark_review.py` recomputed **8/8** recorded 95% bootstrap comparisons and found every lower bound above 2.0. Worst lower bounds: 3.6289395223× versus direct and 3.6405070252× versus P/S-matched, both on mastering v2 at 352.8 kHz. It verified the exact four-cell command definitions, retained benchmark and comparator JSON SHA linkage, passband metadata, checksum-list consistency, and the eight source files the original receipts actually hashed. All eight original source files match the R5.1 tree.

**Limits:** Historical audio WAV/DSF payloads and executable binaries have been deleted. Only their claimed digests and the raw timing arrays remain. The external identity of the physical host cannot be verified from JSON assertions. The source inventory is **not a complete compilation dependency closure**: it omits `src/rate_poly_fir0.h`, which was edited on 17 October 2026 (opt-in guarded optimized path), and it omits the benchmark/comparator Python script hashes and compiler/linker flags. Those differences do not disprove the earlier measurements. They do make it unsound to relabel them as timings from the final R5.1 executable. The R5.1 OpenMP FFT cache writer-lock correction has also not been integrated into a final production binary. Physical gate remains OPEN pending final-binary binding and prospective measurement, or an independently justified exact execution-identity equivalence.

## Newly executed independent local control verification (NOT PHYSICAL)

Host: virtual AMD EPYC 9V74 x86_64, KVM CPUID `hypervisor`, 5 virtual processors. Full SoX built from identical R5.1 production C, with Autotools `--disable-shared --without-libltdl`, GCC `-O2 -g -ffp-contract=off -fno-fast-math`, OpenMP available. The P10 qualification-wrapper encoder requires static linking; the first shared-library build correctly refused profile activation, and the second static build succeeded.

On freshly generated 6-second broadband DSD256 mono fixture, the comparator verified all four full passbands (no post-hoc exclusion):

| Cell | Absolute difference, dB | Outcome |
| --- | ---: | --- |
| v1 176.4 kHz | 0.00107426436 | matched diagnostic |
| v1 352.8 kHz | 0.00077433800 | matched diagnostic |
| v2 176.4 kHz | 0.00618437885 | matched diagnostic |
| v2 352.8 kHz | 0.00349793531 | matched diagnostic |

`--verify-only` reproduced all source/binary/fixture hashes and waveform comparisons. An independent fresh wrong-cutoff fixture (20 kHz center) failed all four comparisons: maximum abs differences 14.26–76.45 dB; `--verify-only --selftest-wrong-cutoff` reproduced this failure. Positive and negative receipt artifacts are packaged separately with original WAV/DSF payloads, each archive under 140 MB.

Actual benchmark on this VM: `--dry-run` returned `physical_host_admissible:false`, `status:NO_TIMING_PERFORMED`; attempting the real physical run exited **2** with `OPEN: physical prepared host required; VM results not admissible`. No timed physical JSON was created. The new physical-host wrapper also refused the VM before creating its result directory.

## Adversarial validation

`PYTHONPATH=tests/dsd python3 -m unittest -q test_p15_r52_physical_benchmark_review test_p15_final_obligations` **14/14 PASS**. Mutations rejected: altered P/S cutoff command, modified CI, changed source identity, excluded high-passband edge, missing cell, and forged VM host. Independently recomputed all 8 bootstrap confidence bounds. An explicit `--require-release` attempt exits **2**, even when historical receipt arithmetic is correct. No tolerance or gate threshold was tuned.

## Reproduce historical review from R5.1 + R5.2 source root

```sh
PYTHONPATH=tests/dsd python3 -m unittest -q test_p15_r52_physical_benchmark_review test_p15_final_obligations
python3 tests/dsd/p15_r52_physical_benchmark_review.py --output /tmp/P15_R52_HISTORY.json
python3 tests/dsd/p15_r52_physical_benchmark_review.py --output /tmp/P15_R52_HISTORY.json --require-release # exit 2, OPEN
```

## Prospective final-bin PHYSICAL procedure (requires operator access)

First integrate/qualify the R5.1 FFT4G reader/writer corrective or enforce an independently proven exclusive-use configuration. Build **final source** on the chosen physical CPU, and retain executable hashes and compiler/ISA/FP flags. For the qualification-wrapper encoder, use the supported static-link configuration; do not turn off production release gating. Configure and build with the exact flags chosen for the release, including `-ffp-contract=off` if required by the arithmetic proof. Confirm binaries and their build sources are the final artifact identities, not development builds from an unrelated checkout.

On the isolated physical host, prepare CPU with `sudo tests/dsd/benchprep.sh prepare --cpu 8` (adjust CPU), inspect `benchprep.sh status` and `benchprep.sh noise`, and retain governor, turbo, affinity, microcode, thermal and frequency records. Run:

```sh
# From this source tree (adjust paths, CPU and output parent):
./tests/dsd/p15_r52_run_physical_benchmark.sh \
  "$(realpath src/sox_ng)" "$(realpath test/sox_p10_candidate)" \
  8 /absolute/fresh/p15-dsd256-physical-r52

# After results have been secured:
sudo tests/dsd/benchprep.sh restore

# Independent local review of the newly retained RAW audio/timing receipts:
python3 tests/dsd/p15_r52_physical_benchmark_review.py \
  --historic /absolute/fresh/p15-dsd256-physical-r52 \
  --current-sox src/sox_ng --current-candidate test/sox_p10_candidate \
  --output /absolute/fresh/p15-dsd256-r52-review.json
```

The runbook's fresh result directory contains both comparator audio and benchmark six-channel fixtures. Do **not** delete these files as done in 2026-10-16: the reviewer will recompute spectral agreement directly from preserved WAV audio and verify all fixture checksums. The runbook and reviewer deliberately **do not promote P15 acceptance**. The independent release adjudicator must check exact deployed source and binary linkage, actual host/noise qualification and confidence limits. Results at or below 2.0 in any required bound are not a pass. New release-specific evidence should be signed/offline sealed without editing original history.

## Seven-part R5.2 gate disposition

1. Continuous-frequency spectral inventory: PASS (inherited R5.1).
2. Independent complete ideal-operator spectral proof: CONDITIONAL (unchanged).
3. Source and execution provenance: CONDITIONAL (historical performance limited; final binary not bound).
4. Arbitrary-input FFT4G execution roundoff: CONDITIONAL (locking correction pending release).
5. End-to-end same-operator numerical acceptance: CONDITIONAL (unchanged).
6. **Physical DSD256 matched 2x: OPEN**, with historical measured-scoped 8/8 positive and locally verified control methodology.
7. **Overall P15: OPEN.**

Do not substitute this physical performance check for the incomplete composite spectral interval proof or release-runtime proof.

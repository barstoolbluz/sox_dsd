# P02 DFF read throughput hotfix: source-only handoff

**Date:** October 9, 2026  
**Input:** `sox_ng-hotfix-149ea582.tar.gz`, SHA-256 `e99eb6a2e88613e1ba14654ef046d4a5ce6ca4beb3aeeccbee737cce1cdbf2d0`  
**Scope:** P02 DSDIFF reader hotfix in the P00-P05 accepted tree, **not** P06.  
**Functional disposition:** PASS against executable tests and byte-equivalence checks.  
**Controlled-host 5% throughput gate:** **INCONCLUSIVE, not accepted**: host and per-workload measurement noise exceed 2%.

## Cause and corrective implementation

P02 retained channel-byte clusters and checked partial-consumption state on each eight-frame expansion. The check and bit-offset accounting stayed in the hot loop even for the normal large-buffer, byte-aligned path. This is a source-level performance hypothesis, corroborated by paired A/B timings, not a claim of profiler-level causation.

In `src/dsdiff.c`, `dff_read()` uses two paths:

1. For a saved partial cluster or a non-byte-aligned seek, `dff_read_fragment()` completes the remaining bits using the original P02 `bit_pos`/`cluster_valid` state, advancing that state exactly as P02 did. Tail requests below eight frames use the same helper and retain leftover bits for the next read. Zero-length audio still returns immediately, even with following MANF metadata.
2. Once byte-aligned, complete eight-frame clusters use the original P01-style channel-byte expansion and require no per-cluster saved-state bookkeeping. The reader returns to the fragment helper only for a trailing partial cluster. Byte order, bit order, channel interleaving, sample polarity, seeks, and the existing output length contract remain unchanged.

No public API, format writer, DSP effects, implicit conversion, P03/P04/P05 policy, or baseline test fixture has changed.

The benchmark now rejects a disappearance of any of the **six previously comparable** P01/P02 repack cases. Formerly the harness silently classified a changed output as `not-comparable`, removing it from the gate. The separate `tests/dsd/check_hotfix_equivalence.py` independently compares output bytes against the supplied P05 tree, including intentionally noncomparable P01/P02 small six-channel cases. `tests/dsd/bench_hotfix_dff.py` supplies a P05-before/after CPU-time comparison that holds P04's explicit layout-loss permission constant.

## Executed validation

The supplied P05 tree and the hotfix were separately built using `autoreconf -fi`, `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'` and `make -j3`. The authenticated P01 archive and the accepted P02 archive (with only this reader hotfix applied) were also compiled with the same generated configuration header. Builds completed successfully with no compiler warnings in the final compilation.

| Check | Observed result |
| --- | --- |
| `make check` | PASS, 73 OK / 8 inherited VOID / 0 FAIL |
| `make check-dsd` | PASS |
| P05 runner | 36 pass / 0 fail / 0 skip / 0 xfail / 0 xpass |
| P02 streaming, extent, forward-only, and CLI | 706 pass / 0 fail |
| P02 DoP capacity | 29 assertions pass |
| P05 planning unit + CLI | 168 assertions + 155 cases pass |
| Full output byte-equivalence vs input P05 tree | 8/8 exact SHA-256 and size matches: DFF/DSF, 2ch/6ch, large/small capacities |
| P01-vs-P02-hotfix benchmark | 544/544 commands execute; zero errors; six comparable repack outputs still identical |
| Paired P05-before/after DFF benchmark | 4/4 workloads favor hotfix in two independent runs; full repack hashes match |

## Measured throughput and certification

### Authentic P01 versus isolated P02-hotfix

The P01 baseline is `sox_ng-P01-throughput-evidence-2026-10-08.tar.gz` (SHA-256 `aff43474769dff63e746cfe0931e780c1258610519a7fae09f4e1b75bc8740c6`). The P02 control is `sox_ng-P02-legacy-pad-warning-fixed-2026-10-08.tar.gz` (SHA-256 `2cc0a01fd422d078a541f0a26ff602051392ca10888014ef19fab931fd92976e`), patched **only** in the DFF reader so that a P04/P05 channel-layout policy difference does not invalidate the P02 measurement. Both use identical generated `src/soxconfig.h` (SHA-256 `343986f0946985a342d25d39ba62df1688a78d2881baf93d84505118a6808145`). `bench_read_p02.py` ran 15 paired samples per arm and two warmups on CPU 1, with full 16,777,216-frame large fixtures and 131,072-frame small fixtures on tmpfs.

| P02 gate workload | Change vs P01 | Measurement noise | Qualification |
| --- | ---: | ---: | --- |
| `dff-2ch-null-large` | +4.93% | 18.37% | Inconclusive |
| `dff-6ch-null-large` | -4.42% | 8.73% | Inconclusive |

All six named comparable P01/P02 repack cases remain byte-identical, and the intended small-capacity six-channel P02 differences remain excluded. Other rows (including DSF controls) are retained in `p01-versus-p02-optimized.json`. The overall benchmark status is `incomplete`, **not** `pass`. In particular, the observed +4.93% should not be used to assert the 5% gate is met: its noise is almost four times the threshold itself.

### Matched supplied-tree P05 before and after

A second, independent check compared the supplied P05 tree with the P05 hotfix, applying `--dsd-layout-loss warn` to both arms when routing to the null sink. P04 requires that explicit permission for DFF inputs with named channel layouts; omitting it produces an invalid comparison. Each case used 16,777,216 frames, large buffers and CPU 1. The first run used 25 pairs, the second used 15.

| P05 matched workload | First run | Repeat |
| --- | ---: | ---: |
| `dff-2ch-null-large` | -8.21% | -10.88% |
| `dff-6ch-null-large` | -8.38% | -8.77% |
| `dff-2ch-repack-large` | -4.82% | -7.98% |
| `dff-6ch-repack-large` | -4.21% | -4.01% |

The paired output files hashed identically for both repack workloads. Every corresponding noise estimate exceeded 2%, so these corroborate the direction of the optimization but **cannot certify** the historical 5% gate.

The host preparation probe returned a 25.6% spread on CPU 1. Other CPU probes remained above 2% (3.0% minimum). The virtualized build host lacks the governor/boost/SMT controls specified in `tests/dsd/BENCHMARKING.md`. Benchmark artifacts are intentionally scrubbed of build paths.

### Final throughput acceptance procedure

On a **prepared, controlled host** (the machine where the original P02 +6% result was obtained, or equivalent), build the P01 baseline and an isolated P02 + this single-file DFF reader patch, using **the same** compiler, flags and generated configuration. Then, with the physical CPU appropriately prepared and `benchprep.sh noise` below 2%, run:

```sh
tests/dsd/benchprep.sh status
tests/dsd/benchprep.sh noise --cpu N
python3 tests/dsd/bench_read_p02.py \
  --baseline-sox /path/to/P01/src/sox_ng \
  --sox /path/to/P02-plus-reader-hotfix/src/sox_ng \
  --cpu N --pairs 25 --warmups 2 --large-frames 16777216 \
  --results /path/to/new-measurements
```

The DFF null-decode large cases must both be under or equal to the design's 5% regression bound and their respective measurement noise must be **strictly below 2%**. Check all other unchanged comparable workloads as specified by the design; confirm the six named P01/P02 repack hashes still match. Do not approve if the bench marks a comparable workload `not-comparable`. Run `check_hotfix_equivalence.py` against the original and delivered P05 binaries separately. For matched P05 speed analysis (not P02 qualification), use `bench_hotfix_dff.py` with the two P05 binaries and the same pinned CPU.

No relaxation of the performance threshold is proposed: the optimization is functional, and the residual measurement uncertainty is a host limitation, not proof of irreducible overhead.

## Source artifact, evidence, and restart point

- Delivered changes: `src/dsdiff.c`, `tests/dsd/bench_read_p02.py`; new `tests/dsd/check_hotfix_equivalence.py`, `tests/dsd/bench_hotfix_dff.py`, this handoff, and the new `tests/dsd/results/P02/DFF-read-hotfix-2026-10-09/` evidence folder.
- Original evidence in `tests/dsd/results/P00` through `P05` remains byte-for-byte unchanged. Historical SHA manifests are retained rather than silently rewritten; the new hotfix `SHA256SUMS.txt` covers the delivered tree.
- The delivered archive contains source and persisted evidence only, with no `.git`, object files, executable builds, temporary fixtures, or Python caches.
- **Continuation state:** corrective source implementation complete; functional and output identity gates pass. The **only outstanding acceptance action** is independent controlled-host throughput qualification. The P02 reader correction may be transferred to the standard P05 continuation tree without adopting a P06 feature or reverting P02 small-read semantics.

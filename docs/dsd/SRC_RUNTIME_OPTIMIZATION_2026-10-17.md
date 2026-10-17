# sox_ng production SRC optimization — 2026-10-17

## Decision and delivered implementation

The retained implementation accelerates the existing production rational FIR
sample-rate converter. It changes one pre-existing source file,
`src/rate_poly_fir0.h`, by adding 68 lines and deleting none. The original
implementation remains recoverable byte for byte and remains the ordinary
build's default. The measured candidate is enabled explicitly with
`-DLSX_RATE_ORDERED_OPT=1` under the strict floating-point build contract below.

The main result is a meaningful improvement in common production PCM
conversions, with exact baseline-versus-candidate sample results under the
stated conditions. The common 44.1→48 and 48→44.1 kHz stereo cases have paired
median CPU speedups of approximately 1.27× and 1.28×. The implementation is a
completed, tested optimization candidate suitable for controlled opt-in
evaluation. P15 certification, default promotion, and prepared physical-host
performance qualification remain separate, outstanding decisions.

There are measured limitations. Very small isolated FIR calls retain roughly
4–5 ns of extra latency. Two sustained DSD cases have unfavorable
original CPU intervals and were selected for separate diagnostic repeats. Other
paths are dominated by unchanged DSP and often show little or no improvement.
The report preserves those observations rather than describing the patch as
universally faster.

### Identities

| Item | SHA-256 |
| --- | --- |
| Attached complete baseline archive | `f827eeb830a68f54b99c50ad6073ba1a0febec5478403a37a49f79d4e2f484fc` |
| Frozen rational-FIR header | `928f005912f35ca0612a37c99a9a6343be8dea51e23cd41f5286b9f85fede6ff` |
| Final candidate rational-FIR header | `c1626c26f7ba8d64f2b69752906948b527923745313d13c41f78c47046552591` |
| Measured frozen CLI | `fad06a388cbf112945a1e66a8f4fd6213a156f9a5f8919a66efe7ed1dd94a004` |
| Measured candidate CLI | `750ea8d25c563ee5f12ebb587b4613f8669c441a3f7b8c8057ef92ce76774f42` |
| Minimal production patch | `354f6c0c824587c9a5767e544bdd139105541810b5fa45cea5de78dbb05d81e8` |

All evidence paths below are relative to
`tests/dsd/results/SRC_RUNTIME_OPTIMIZATION_2026-10-17/`, unless another
repository path is written explicitly. The complete tables and exact stored
numbers are in `BENCHMARK_TABLES.md` and `benchmark-summary.json`. Rounded
numbers in this narrative are presentation values, not replacements for the
machine-readable measurements.

## What was expensive and what changed

Source inspection and execution measurements identified the non-interpolated
rational FIR as a profitable target. In the corrected link-only sampling
profile, `vpoly0` accounted for about 48% of sampled executable time in the
44.1→48 kHz very-high-quality case. FFT kernels were also significant. High
downsampling ratios had a different mix, with the existing `h12` half-band
stage accounting for roughly 30–42% in the profiled routes. The eight DSD
profile screens were dominated by the already optimized sparse half-band
reconstruction and frame-processing code; rational SRC was a much smaller
component in the DSD256 v2→384 kHz screen.

These are sampled attribution observations, not hardware-counter measurements
or complete accounting of shared-library and kernel time. The original profile
screens accidentally used CLI-only `-pg` instrumentation. Those executables and
receipts remain identified separately. The corrected SRC profiles use a
link-only `-pg` executable whose CLI and library objects are uninstrumented.
The normal benchmark executables are unprofiled. See
`work-evidence/src-profiles-linkonly/`, `agent_dsd/profile-screens/`, and
`METADATA_CORRECTIONS.md` for the full provenance.

The inherited rational kernel computes the quotient and remainder of its
integer phase clock with `div` for each output, then performs one serial FIR
dot product. The candidate makes two related changes:

1. It decomposes the initial clock and clock increment once per stage call,
   then advances the exact quotient/remainder with additions, a comparison,
   and a conditional carry. This removes per-output integer division without
   approximating the rational rate or constructing a new schedule table.
2. It computes two independent output dot products together. Each individual
   output keeps the inherited tap order and accumulation order. Independent
   accumulators expose more instruction-level parallelism while retaining the
   floating-point operation graph for every sample.

The final generated code uses scalar multiplies and packed additions whose
lanes belong to separate output samples. It does not use a horizontal reduction
or FMA in the affected functions. This is a compiler observation for the tested
build, supplementing the source argument rather than constituting a general
compiler proof. Static disassembly is retained in
`work-evidence/final-rate-disassembly.txt` and
`work-evidence/final-assembly-observations.json`.

The change adds no persistent state, allocation, coefficient preparation,
transfer-function change, FFT implementation, external dependency, threading,
public ABI, or command-line option. It retains the existing portable code
instead of adding an architecture-specific kernel. The candidate is used only
when the existing output-capacity bound exceeds two; smaller bounds execute
the inherited loop. That call-level guard was investigated to reduce tiny-call
costs, but does not restore the old function's compiled layout or prologue.

The candidate's `rate.o` text section grows from 31,433 to 36,121 bytes, an
increase of 4,688 bytes. Its data and BSS sections do not grow. In the final
default-off build, both `rate.o` text and linked CLI text are byte-identical to
the frozen baseline. Debug/path information makes a whole-file executable hash
a different question. These results are in `work-evidence/code-size.json` and
`agent_build/default-off-evidence/summary-guard2.json`.

## Measurement method and scope

The measured environment is a Linux x86_64 KVM virtual host reporting an AMD
EPYC 9V74 80-Core Processor. Nine logical CPUs are exposed, with a cgroup quota
of eight CPUs and 8 GiB memory. CLI comparisons are pinned to CPU 0 and use
`--single-threaded`. GCC 13.3.0 builds both arms with
`-O2 -g -ffp-contract=off`; only the candidate adds the opt-in macro. Existing
per-file DSD ISA flags and runtime dispatch are preserved. There is no global
`-march=native` or new ISA requirement. The helper build includes FFT4G and
bundled codecs; unavailable external codecs and OpenMP are excluded in both
arms. Exact source, configuration, compiler, linker, and executable records
are retained with each build.

The runner extends the existing DSD fixture/profile infrastructure rather than
replacing its mathematical tools. PCM stimulus is deterministic, bounded
signed-32 random data; DSD stimulus uses the inherited deterministic DSF
generator with exact logical bit lengths. It is a runtime corpus, not a claim
that synthesized DSD bits are a music-quality or spectral-certification
reference. Every accepted conversion checks exit status, timeout, exact output
length, and no-dither signed-32 output hash against the frozen build. Those
checks remain outside the child timing interval.

Each ordinary case has a preflight pair, two warmup pairs, and 15 measured
pairs. Arm order is randomized and interleaved with a recorded seed. The
speedup is the median of the paired baseline/candidate time ratios; it is not
the ratio of the two independently computed arm medians. CPU time is child
user plus system time from Linux `wait4`; wall time includes launch, processing,
I/O, and drain. Short workloads expose initialization overhead, while sustained
workloads amortize it. Absolute audio and output-sample throughput are reported
for both clocks. The complete tables also report medians, median absolute
deviations, relative MAD, and per-run peak-RSS summaries.

The 95% intervals are per-case percentile bootstrap intervals using 4,000
resamples of the paired ratios. They describe observed run variation and are
not simultaneous family-wise bounds across the matrix. The VM was not a
prepared physical benchmark host: frequency policy, boost, isolation and
interference were not qualified. A real `perf_event_open` attempt for CPU cycles
returned ENOENT; hardware cycles, cache misses and bandwidth counters are
therefore marked unavailable. No claim about measured cache behavior follows
from the source-level explanation. Peak RSS includes the process-launch
footprint and must not be read as isolated DSP heap usage.

The corpus spans both common sample-rate families; integer and fractional
ratios; 88.2, 96, 176.4, 192, 352.8 and 384 kHz DSD outputs; DSD64/128/256;
mastering v1/v2 and wideband v1; mono, stereo and six channels; short streams;
and sustained inputs. Controls vary application buffer size, four additional
rate qualities, all five available DSD FIR dispatch tiers, and four DSD256
stereo native-family continuity combinations. This provides different FIR,
FFT, block and memory workloads without asserting universal coverage.

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

The paired ratios in the continuity table are medians of matched per-run ratios, not quotients of the displayed arm medians; their apparent direction can therefore differ. The raw pairs are retained.

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

## Alternatives and the retained tradeoff

Real alternatives were implemented and measured before selecting the final
patch. The same-executable actual-FIFO benchmark includes the original,
recurrence-only and final paired kernels. For sustained 4,096-input calls, the
final paired arm is 1.42–1.92× faster than the original and 1.30–1.79× faster
than the recurrence-only arm across the tested cases. These observations favor
combining exact scheduling and independent output work. They reduce confounding
from unrelated changes in executable layout; they do not isolate an exact
additive benefit for each source change because function layout, setup and
register allocation still differ. The benchmark uses real production stage and
FIFO structures but reuses fixed input windows, so these are stage results,
not whole-file speedups. All 765 final rows are retained, with two warmups and
15 timing rounds for each of 15 cases and three arms.

The final tiny-call cost is real. At 26 taps and L/M=80/147, one input takes
29.044 ns in the original versus 33.491 ns in the candidate; two inputs take
31.510 versus 36.416 ns. Those are about 15.3% and 15.6% increases in median
time, or 4.45 and 4.91 ns. The corresponding paired speedups are both about
0.861×, with intervals below one. Empty calls are approximately neutral.
Eight-, 32-, and 128-input cases improve by about 1.47×, 1.52× and 1.50×.
The final whole-CLI small-buffer controls are faster, but that does not erase
the isolated latency regression or qualify a one-sample-at-a-time embedder.
The default-off build remains available to users whose workload is dominated
by such calls. Native mastering DSD routes that do not contain this rational
FIR already avoid its execution; a finer runtime FIR dispatch cannot remove a
whole-binary timing difference on those routes. Code placement and VM variation
remain possible explanations, not measured causes. The retained diagnostic
repeats and later prepared-host gate are the appropriate limits on adoption.

A temporary comparison of different small-call thresholds had an incomplete
final experimental case, which is explicitly marked and excluded from the
threshold decision. Its apparently neutral small-call behavior did not predict
the final executable's layout cost. The complete final stage measurements
supersede the earlier prototypes. No source change was made merely to chase a
favorable result from an incomplete measurement.

A four-output half-band batching prototype had mixed isolated results. More
tellingly, its whole-binary screen reported about 1.167× improvement on a
44.1→48 kHz route without that half-band stage. That negative control exposed
layout or other whole-binary confounding, so the extra half-band change was
rejected. A FIFO allocation-retention prototype showed no consistent benefit
with intervals overlapping one, while broadening memory-lifetime semantics
across effects; it was also rejected. These source variants, their executables,
commands and raw screens remain in `agent_src/`, `screen-variants/` and the two
`work-evidence/screen-*` directories. They are not final-candidate receipts.

An FFT4G rewrite, a different FIR reduction, or integration of another DSP
library was not justified by this evidence. Such changes would enlarge the
numerical, licensing, portability and maintenance review surface while the
ordered rational kernel already offered a useful production improvement.
DSD reconstruction remained dominated by its already optimized native code;
that implementation was preserved. This is a choice of scope supported by
measurement, not a claim that every unchanged subsystem is optimal.

## Validation and observed inherited behavior

The final focused exact regression reports 768,060 checks, including 53,856
direct cases, 288 streaming cases and 50 private binary64 API cases. It compares
5,409,850 binary64 sample words exactly, with no empirical error tolerance.
The test compiles actual `rate.c` and uses real FIFOs, instantiates frozen-header
reference functions, and checks an independent wide-integer clock oracle.
Inputs exercise zeros and signed zeros, subnormals, cancellation, values near
full scale, broader finite values, irregular input lengths, output-capacity
limits, retained phase and FIFO state. Kernel checks cover four rounding modes;
the full private adapter cases use nearest rounding. This tests the claimed
equivalence directly instead of introducing a high-precision reference for a
new transfer function that the patch does not implement.

All 16 invoked existing focused regression suites pass on the final candidate,
including relevant P07, P11/P12, P13, P14, planner/failure/DoP, decoder streaming,
P15 v1 and P15-R3 v2 checks. The generic conversion run has 148 successful
checks and skips seven unavailable optional formats. The sample-conversion
probe passes. These are the suites actually run, not a claim that every test
in the full repository or every optional codec was exercised.

The full 216-object candidate library and exact test pass with AddressSanitizer
and UndefinedBehaviorSanitizer, with empty stderr. LeakSanitizer was unavailable
because it explicitly rejected the ptrace environment; the failed diagnostic
is retained and leak detection alone was disabled for the successful ASan/UBSan
run. Leak checking is UNRUN, not PASS. Additional O3 and x87 fallback checks
pass for the focused test translation unit linked against baseline support;
they do not qualify complete O3 or x87 application builds. Existing ISA tests
and the forced-tier controls require the host's available scalar, SSE2, AVX1,
AVX2 and AVX-512 tiers. Other platforms must record unavailable tiers as UNRUN.

The buffer controls discovered an inherited edge case. For 10 seconds of
48 kHz stereo converted to 44.1 kHz, both frozen and candidate builds exit zero
but emit only 2,220 output frames with a 32-byte application buffer, instead
of 441,000. At 64 bytes both emit 2,234 frames. At 128 and 256 bytes both emit
the expected length, and baseline/candidate hashes match at each setting.
The hashes at 128 versus 256 bytes differ in both builds. Thus the exact CLI
claim is equivalence between builds at matching conversion parameters and
buffer settings, not whole-CLI invariance across every buffer size. The
affected scheduler/kernel streaming proof has a narrower scope.

The first control run correctly stops at that frozen-baseline length failure;
it remains a FAIL receipt. The revised reverse control uses 128 bytes and keeps
the successful 32-byte forward case. No length or equality test was relaxed.
Truncated conversions are excluded from accepted throughput claims. The
diagnostic record is in `work-evidence/small-buffer-diagnosis/`; the original
case list, failed receipt and revision rationale are retained. Fixing this
inherited whole-pipeline edge case would be a separate source change and is
not concealed inside the optimization.

## Numerical equivalence and P15 status

The retained optimization is **classification 1: bit-exact relative to the frozen implementation under the stated build and execution conditions**. The sole production change is `src/rate_poly_fir0.h`, final SHA-256 `c1626c26f7ba8d64f2b69752906948b527923745313d13c41f78c47046552591`. It changes integer phase scheduling and evaluates two independent rational FIR outputs together. Coefficients, interpolation policy, FFT4G, halfband filters, native DSD reconstruction and ISA dispatch remain unchanged. The full argument is in `docs/dsd/SRC_RUNTIME_OPTIMIZATION_PROOF_2026-10-17.md`; exact original header bytes remain in `tests/dsd/reference/src_optimization/`.

### Why the introduced numerical error is zero

Write the original integer clock as `A=qL+r` and its increment as `M=uL+v`, with `L,M>0` and `0≤r,v<L`. The candidate uses `c=(r≥L−v)`, then updates `q+=u+c` and `r+=v−cL`. This is exactly the quotient and remainder of `A+M`. The subtraction form avoids constructing a potentially overflowing `r+v`. Induction therefore gives the same input start, coefficient phase, output count, consumed input and retained phase as the original division-based loop. The proof covers valid stage states where the original integer operations are defined.

Each output still begins at positive zero and accumulates coefficient-first products in ascending tap order. Pairing interleaves two complete dot products; it does not split or reassociate either output's reduction. The second output's input window is checked before its pointers are formed, and an odd tail uses the original scalar arithmetic. Corresponding rounded operations therefore receive identical operands. Under the contract below, the error introduced by this transformation is exactly zero. For finite compared outputs, that implies zero absolute difference and zero ULP difference; relative difference is zero where the reference is nonzero. Signed zeros are compared by their bits. This is a conditional source-level proof argument, supported by tests and disassembly, not a machine-checked compiler proof. It says nothing new about the original filter's absolute error against an ideal real-arithmetic response.

The option requires `LSX_RATE_ORDERED_OPT=1`, no `__FAST_MATH__`, and `FLT_EVAL_METHOD==0`. Compared builds also use `-ffp-contract=off` and prohibit reassociation. Contraction cannot be detected portably by the preprocessor, so the build flag is part of the qualification contract. Execution assumes finite supported audio values, valid nonoverlapping stage storage, nontrapping arithmetic and the same floating-point environment. Unknown or excess evaluation precision selects the original implementation; ordinary builds remain on that default path. Calls whose reserved output bound is at most two also use the original body. Compiler correctness is an assumption, supported by generated-code inspection and differential tests rather than a formal compiler proof.

### Operator identity is separate from certification

The reviewed exporter comparison covers all 24 nonidentity P15 rate pairs: 43 initialized stages, 59,854 coefficient words and 123,904 FFT-bin words agree exactly, together with graph and scheduling metadata. Twelve graphs contain the modified rational FIR family: each of 88.2, 176.4 and 352.8 kHz to each of 48, 96, 192 and 384 kHz. The other twelve provide unchanged-family controls. Exporting initializes and describes stages; it does not execute their FIR functions. Actual execution is established separately by the kernel, adapter and CLI evidence. Raw snapshots and comparison metadata are at `work-evidence/operator-identity-final-reviewed/`.

All 24 captures nevertheless carry a shared source identity that includes the changed header. Existing source-bound receipts therefore cannot be presented as candidate receipts, even for an unchanged execution route or a default-off build. The original receipts, source pins and campaign outcomes remain archival records for their original identities. A reviewed equivalence bridge could reuse mathematical bounds for the identical operator and coefficient words; the current raw-hash checks do not implement that bridge automatically. The new captures and equivalence argument make the change reviewable without rewriting historical evidence.

Zero introduced error does not close the outstanding arbitrary-input FFT4G arithmetic bound or full composite spectral obligations. The original 0.0001 dB passband-ripple and −160 dB coherent-alias requirements remain unchanged. Empirical sample equality, coefficient identity and faster execution are insufficient to certify those absolute bounds. **P15 release/default promotion remains false.** The detailed obligation mapping is in `docs/dsd/SRC_RUNTIME_OPTIMIZATION_P15_ASSESSMENT_2026-10-17.md`.

The eight historical physical P/S-matched DSD256 comparisons retain their historical `PASS-SCOPED` status. Their native mastering routes reconstruct to 176.4 kHz; final 176.4 kHz uses identity SRC and 352.8 kHz uses a DFT stage. Those native paths do not execute the modified header. A rebuilt legacy comparator can execute the optimized rational SRC, however, so historical speedup ratios do not automatically transfer to that changed comparator. Current virtual-host observations provide no new physical-host qualification.

## Evidence integrity, reproduction and integration

All 15,498 original regular files from the attached archive were compared
against their original hashes. The intended production header is the only
modified pre-existing file; none is missing. Original coefficients, provers,
receipts, build files and frozen handoffs remain intact. New evidence and
documentation are additive. The preserved reference header and reverse patch
recover the frozen source without relying on this conversation.

The production patch applies to the exact frozen header and reverses to its
original bytes. A separate support patch contains the new tests, build and
benchmark utilities, reference headers and documentation. Large raw results
and measured executables are delivered in the full repository and evidence
archive rather than embedded in the review patch. New generated audio and
compiler intermediates are omitted where deterministic regeneration is
sufficient; all original attached repository files remain in the full bundle.
Internal and external SHA-256 manifests identify the delivered files and
archives without circular self-hashes.

The primary runner printed a final PASS message but its on-disk receipt
remained RUNNING with 1,761 of the expected 1,764 rows. The cause of that
receipt persistence gap was not established. The saved receipt is preserved
unchanged. A reproducible extraction verifies and retains its 48 fully
complete cases, with parent hash and explicit derivation metadata. The final
short DSD256 case was rerun as a complete 36-conversion case in a new directory.
No missing times were reconstructed and no partial case was silently counted
as complete. The runner now fsyncs its final JSON and writes a separate
completion record containing its hash. The consolidated summary checks the
actual saved rows and identical executable identities.

The full reproduction procedure is
`docs/dsd/SRC_RUNTIME_OPTIMIZATION_REPRODUCE_2026-10-17.md`. It covers restoring
the frozen source, identical strict builds, numerical tests, sanitizers,
operator capture, the exact primary and revised control corpora, diagnostic
repeat policy and profile interpretation. The helper is deliberately limited
to Linux x86_64 and uses the repository's retained generated configuration;
normal configure builds and additional toolchains require their own results.
The exact original commands and build hashes remain authoritative for this
session's measurements. New runs must write new receipts rather than edit old
source bindings.

The continuation checkpoint records the implementation and artifact identities,
test and benchmark outcomes, inherited small-buffer issue, outstanding physical
and P15 obligations, and the file-saving approval block. No production default,
P15 status or P16 authorization was promoted by this work.

# Reproducing the production SRC optimization

This procedure builds and tests the opt-in rational-FIR candidate. It does not
promote a P15 default or produce a spectral/arithmetic release certificate.
The associated report and proof state the numerical contract and remaining
qualification work.

## Build contract and platform

The measured configuration is GCC 13.3.0 on GNU/Linux x86_64, with:

```text
-O2 -g -ffp-contract=off
```

The candidate adds `-DLSX_RATE_ORDERED_OPT=1`. Do not add fast math,
reassociation, or contraction when relying on the bit-exact claim. The
preprocessor also requires a defined `FLT_EVAL_METHOD == 0`; otherwise it
retains the inherited path. The macro alone cannot check a compiler's
contraction setting. GCC documents the contraction option in its
[optimization options](https://gcc.gnu.org/onlinedocs/gcc-13.4.0/gcc/Optimize-Options.html).

`tools/build_src_optimization.py` is a small development build helper for this
environment, where autotools was unavailable. It uses the supplied repository's
retained generated Linux configuration and Automake source lists, then builds
216 library objects and the requested probes. Bundled codecs and FFT4G are
included; external codec dependencies and OpenMP are absent. The isolated DSD
ISA translation units retain their existing per-file flags and runtime dispatch.
This helper is restricted to Linux x86_64 and is not a substitute for normal
configure/platform qualification. A normal configured build can carry the same
strict compiler flags without a new configure option.

Requirements for this procedure are Python 3, GCC, GNU binutils, and the
Python packages already used by the existing tests, including NumPy and SciPy. The
benchmark runner uses Linux `wait4`; the profile runner additionally uses
`gprof`. Choose a CPU allowed by the host's affinity mask. CPU 0 was used for
the final CLI corpus in this session.

## Recover the exact frozen production source and build both versions

Run these commands from the parent of the extracted `sox_ng` directory. Use
fresh destination names if the examples already exist.

```bash
cp -a sox_ng sox_ng_frozen
cp sox_ng_frozen/tests/dsd/reference/src_optimization/rate_poly_fir0.h \
   sox_ng_frozen/src/rate_poly_fir0.h

python3 sox_ng/tools/build_src_optimization.py \
  --source sox_ng_frozen --build /tmp/src-opt-baseline \
  --cflags='-O2 -g -ffp-contract=off'

python3 sox_ng/tools/build_src_optimization.py \
  --source sox_ng --build /tmp/src-opt-candidate \
  --cflags='-O2 -g -ffp-contract=off' \
  --extra-cflags=-DLSX_RATE_ORDERED_OPT=1
```

The frozen header must hash to
`928f005912f35ca0612a37c99a9a6343be8dea51e23cd41f5286b9f85fede6ff`.
The candidate header must hash to
`c1626c26f7ba8d64f2b69752906948b527923745313d13c41f78c47046552591`.
Only that pre-existing file differs from the input archive. Restoring it also
restores every original P15 pinned source byte; added documentation, test and
measurement files do not change those original bytes. The production patch
can alternatively be reversed in the recovered copy.

Both builds emit `build-record.json`, `build-inputs.json`, and
`compile_commands.json`. These record compiler flags, source/header/config
hashes, commands and binary hashes. The helper detects source changes during
compilation. A different build directory, toolchain or linker can change the
executable hash, especially its debug information; use the newly produced
identity records rather than relabeling the archived binary.

## Numerical and existing regression tests

The new probe includes real `rate.c` and compares it with functions instantiated
from the exact frozen headers. All sample comparisons use raw binary64 bytes,
without a tolerance. It also checks output counts, independent integer clock
formulas, FIFO state, irregular streaming, and the private binary64 adapter.

```bash
/tmp/src-opt-candidate/test/dsd_test_src_optimization

python3 sox_ng/tests/dsd/results/SRC_RUNTIME_OPTIMIZATION_2026-10-17/agent_build/validate_existing.py \
  --source sox_ng --build /tmp/src-opt-candidate \
  --results /tmp/src-opt-existing-tests

python3 sox_ng/tests/dsd/compare_src_optimization_operators.py \
  --baseline /tmp/src-opt-baseline/test/dsd_test_p15_src_stage_export \
  --candidate /tmp/src-opt-candidate/test/dsd_test_p15_src_stage_export \
  --results /tmp/src-opt-operator-identity
```

The displayed existing-suite command requires all five DSD ISA tiers available
on the measured host: scalar, SSE2, AVX1, AVX2 and AVX-512. The small session
driver requests every tier and does not skip unsupported ones. On a host lacking
a tier, run the supported commands individually from the retained receipt and
record the unsupported tier as UNRUN; do not report the full 16-invocation result.
The generic conversion tests and exact commands are retained in the validation
receipts as well.

The operator comparison checks 24 initialized stage graphs and exact serialized
coefficient/FFT words. It does not execute audio or prove spectral inequalities.

For the fully instrumented address/undefined-behavior check:

```bash
python3 sox_ng/tools/build_src_optimization.py \
  --source sox_ng --build /tmp/src-opt-sanitize --probes src_optimization \
  --cflags='-O2 -g -ffp-contract=off -fsanitize=address,undefined -fno-omit-frame-pointer' \
  --extra-cflags=-DLSX_RATE_ORDERED_OPT=1

ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 \
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
  /tmp/src-opt-sanitize/test/dsd_test_src_optimization
```

Leak detection was disabled here only because LeakSanitizer explicitly rejected
the ptrace environment. Its original error is retained and leak checking is
marked UNRUN. AddressSanitizer and UndefinedBehaviorSanitizer remained enabled
through all 216 library objects. Enable leak checking on a host that supports it.

The additional GCC O3 and x87 checks in `agent_dsd/correctness-final/results.json`
compile the focused test translation unit against the baseline support library;
they are not claims of full O3 or x87 application qualification. Their exact
commands are retained. The x87 case uses `-mfpmath=387
-fexcess-precision=standard` and verifies the conservative fallback.

## Repeated production benchmarks

The following uses the exact final corpus, rather than the runner's shorter
built-in sustained durations. Each case has one output-identity preflight,
two warmups, and 15 randomized/interleaved timing pairs. Use empty result
directories; the runner refuses to overwrite prior evidence.

```bash
python3 sox_ng/tests/dsd/bench_src_optimization.py \
  --baseline /tmp/src-opt-baseline/sox_ng \
  --candidate /tmp/src-opt-candidate/sox_ng \
  --cases sox_ng/tests/dsd/results/SRC_RUNTIME_OPTIMIZATION_2026-10-17/work-evidence/final-cases.json \
  --results /tmp/src-opt-final-paired --cpu 0 --repetitions 15 --warmups 2

python3 sox_ng/tests/dsd/bench_src_optimization.py \
  --baseline /tmp/src-opt-baseline/sox_ng \
  --candidate /tmp/src-opt-candidate/sox_ng \
  --cases sox_ng/tests/dsd/results/SRC_RUNTIME_OPTIMIZATION_2026-10-17/work-evidence/controls-cases-validated.json \
  --results /tmp/src-opt-controls --cpu 0 --repetitions 15 --warmups 2
```

The 49 primary cases cover PCM integer/fractional conversions, 44.1/48 kHz
families, high-rate downsampling, mono/stereo/six-channel work, short streams,
DSD64/128/256, versioned mastering v1/v2 and wideband v1 profiles, and all six
requested DSD PCM output rates, using automatic available-ISA dispatch.
Twenty-one controls vary the audio buffer, rate quality, and all five DSD FIR
dispatch tiers, and include four DSD256 stereo continuity comparisons at
mastering v1/v2 and 176.4/352.8 kHz. The exact controls command also requires all five
tiers. On a host without one, use an explicitly recorded case list containing
only supported tiers and record the omitted cases as UNRUN; retain its distinct
corpus identity. Every timed output is
hashed, checked for the expected length, and compared with the frozen
baseline before deletion. Deterministic fixture generators and fixture hashes
are retained; large generated audio payloads are intentionally omitted from
the evidence bundle.

The case field `buffer` is passed to the existing `--buffer BYTES` option;
the 32-, 128- and 256-byte controls are application buffer settings, not promises
that an internal FIR is invoked with exactly that many input samples. The original
32-byte reverse conversion produced truncated output in the frozen baseline.
Direct checks reproduced the same bytes in the candidate at 32 and 64 bytes;
128 and 256 bytes produced the expected length. The revised corpus uses 128 bytes
for that reverse case and preserves the successful 32-byte forward case. See
`work-evidence/controls-corpus-revision.json` and `small-buffer-diagnosis/`.
The output-length check was not relaxed. Whole-CLI hashes can differ across
buffer sizes in both builds; the exact CLI comparison is between the two builds
at matching parameters.

The runner records wall time, per-child user/system CPU time, output throughput,
launcher-inclusive peak RSS, faults and context switches. CLI times include
startup, filter construction, input/output and drain; short cases expose those
costs, while sustained cases amortize them. RSS comes from Linux `wait4` and can
include the Python launch footprint, so it is not an isolated DSP heap measure.
The separate C benchmark isolates reused-buffer stage processing and records
setup separately:

```bash
taskset -c 0 /tmp/src-opt-candidate/test/dsd_test_src_optimization \
  --benchmark > /tmp/src-opt-real-fifo.jsonl
```

Its three arms are the original kernel, a test-only recurrence alternative,
and the paired production candidate in the same executable. It uses real FIFO
operations and carries phase across calls, but reuses a fixed input window;
therefore its speedup is a kernel observation, not whole-file throughput.

## Attribution and interpretation

`tests/dsd/profile_src_optimization.py` accepts PCM case JSON and the emitted
`sox_dsd_profile_linkonly` executable. In that target `-pg` is applied only at
link time: CLI and library objects are uninstrumented. Retained earlier
screens used a different executable with CLI-only instrumentation and must
keep that label. Samples cover the executable's sampled code, not all shared
libraries, kernel time or a measured count of cache misses. Some neighboring
symbols can share coarse sample bins.

Speedups are medians of paired baseline/candidate ratios. The reported 95%
intervals use 4,000 paired percentile bootstrap resamples and describe this
run's variation; they are not simultaneous confidence bounds across the
entire matrix or guarantees on a different host. Keep all cases, including
neutral and negative results. Preserve the existing frozen physical DSD256
evidence as historical PASS-SCOPED evidence; these local virtual-machine
measurements do not replace it or transfer its ratio to a changed comparator.

All historical command paths in raw receipts identify the original workspace.
The evidence indexes map those prefixes to the corresponding archived folders.
When rerunning, supply paths to the newly built executables and write new
receipts; do not edit old hashes or source pins.

## Receipt recovery and diagnostic repeats

The original primary runner printed completion but its saved receipt remained
`RUNNING`, with 1,761 of 1,764 rows. Its 48 complete cases were extracted by
`work-evidence/extract_complete_primary.py` into `primary-completed/`, retaining
the original hash and exclusion record. The final `dsd256_short` case was
rerun in full into `primary-last-case/`. No missing times were reconstructed.
The original receipt remains untouched. The runner now writes and fsyncs a
separate completion record containing the measurement hash; verify that hash
when using a new completed run.

The original control receipt in `work-evidence/final-controls/` remains `FAIL`
for the inherited truncation. The revised 21-case receipt is in
`work-evidence/final-controls-validated/`. The final report and summary use
these explicit sources rather than relabeling either original receipt.

The repeat policy is in `work-evidence/repeat-policy.json`: after the completed
primary and revised control sets, repeat every sustained case whose paired CPU
95% interval is entirely below one, using 30 pairs and two warmups. The selection
script and resulting case list are retained. Run the same benchmark command with
`--cases .../work-evidence/repeat-cases.json --repetitions 30 --warmups 2`, writing
a new results directory. Original and diagnostic estimates must both be reported.

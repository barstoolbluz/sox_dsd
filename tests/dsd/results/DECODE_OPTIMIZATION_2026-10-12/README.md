# Decoder optimization evidence and reproduction

This directory is an evidence collection, not additional production machinery.
The current decision report and resume checkpoint are at the source root.
`BENCHMARK_SUMMARY.json` indexes paired results; `VALIDATION_SUMMARY.json` records
scope and every known unavailable/blocked gate. Raw failures were not removed.

## Layout

`measurements/` holds actual CLI timings, inputs, output hashes, CPU/wall/RSS
observations, diagnostics and sampled profiles. Output WAV files were hashed
and removed after each run; reproduce them with the recorded commands/fixtures.
The source fixtures and executable hashes remain. `experiments/` contains the
five-file source overlays for independent/rejected variants. `variants/` contains
the measured executables, static libraries and build receipts; the profiling
executables must accompany their gmon files. `validation/` holds numerical,
streaming, differential and sanitizer evidence. `receipts/` contains command
logs and exit statuses. `inherited/` preserves the older resume checkpoint.

Timing commands in the original receipts name their original working paths.
They are provenance, not portable shell snippets. Collection-time helper scripts
are retained under `tools/` with the same caveat. The relocation-aware entry point
is `tools/reproduce_decode_optimization.py`. It was exercised from a fresh source
extraction in smoke mode: both release builds and the new scalar unit passed.

## Rebuild independent variants and repeat timings

Use Linux with GCC, autotools (including autoreconf), make, Python 3.12+ with
NumPy, and GNU time at `/usr/bin/time`. The recorded build detects the optional
system dependencies available on this host; configure summaries retain them.
Select an allowed CPU and only tiers the qualification host actually supports.
For the full matrix, the following example also needs adjacent allowed CPU 2:

```sh
python3 tests/dsd/results/DECODE_OPTIMIZATION_2026-10-12/tools/reproduce_decode_optimization.py \
  --input /absolute/path/sox_ng_performance_investigation.tar.gz \
  --work /absolute/path/new-measurement-directory \
  --cpu 1 --tiers scalar sse2 avx1 avx2 avx512 --matrix
```

The tool validates the exact input hash, refuses an existing work directory,
builds all variants before timing, writes command logs and then runs independent
FIR/count/control screens plus before/after production cases. `--smoke` builds
only baseline/combined and runs the scalar optimization unit, without making a
performance claim. The `--matrix` run expands tier coverage in some cases beyond
the original matrix. A physical host still requires independently recorded
power/governor/thermal state, adequate isolation and the governing noise gate;
the tool does not issue a physical qualification certificate.

A single paired case can be run without rebuilding all prototypes:

```sh
python3 tests/dsd/bench_decode_optimization.py \
  --results /absolute/path/new-paired-results \
  --variants baseline=/absolute/path/before/src/sox_ng combined="$PWD/src/sox_ng" \
  --native-rate 2822400 --pcm-rate 88200 --channels 2 --seconds 2 \
  --tiers scalar sse2 avx1 avx2 avx512 --cpu 1
```

The delivered helper now explicitly enables `--multi-threaded` for `--threads 2`.
The old execution-time copy is preserved as `tools/bench_decode_optimization.executed.py`.
The original incorrectly labeled two-thread receipt is not parallel evidence;
use `dsd256-six-channel-explicit-two-threads/paired.json`. Later helper changes
also make baseline ordering explicit, validate nonempty diagnostics, retain
failed invocation commands and avoid hard-coding a KVM label on future hosts.
They do not change the timed single-thread decoder command.

## Validation

```sh
make check
make check-dsd DSD_PHASE=P14 DSD_RESULTS="$PWD/tests/dsd/results/new-local-validation"
make -C test dsd_test_decode_optimization
for tier in scalar sse2 avx1 avx2 avx512; do
  test/dsd_test_decode_optimization "$tier" || exit 1
done
```

The full gate ledger distinguishes new execution from historical receipt checks.
In particular, neither historical P10 source-binding failure nor generic
sanitizer/harness blockers has been relabeled PASS. GCC's five-tier scoped
ASan+UBSan pass requires `ASAN_OPTIONS=detect_leaks=1:halt_on_error=1:detect_stack_use_after_return=0`;
its raw default-mode failure and unchanged-baseline reproduction remain beside
that pass. The additional CLI run is ASan-only, not full UBSan. Exact compiler,
linker and runtime flags are in `validation/sanitizer*/...commands.json`.

No measured ARM/non-x86, 32-bit, new physical Intel/AMD/older-AVX, hardware-counter
or fresh QEMU/one-hour result is implied. Existing accepted long-run evidence is
preserved for the separate P15 qualification review, not claimed as rerun here.

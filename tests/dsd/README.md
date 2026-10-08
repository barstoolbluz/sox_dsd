# DSD phase evidence harness

P00 freezes independent reference inputs and baseline failures. The scripts run
against the built repository, not a pip installation and not the native writer
under test. The repository's DSD design and the active SOW govern acceptance.

## Entrypoints

From the repository root after the configured static build:

```sh
make check
make check-dsd
python3 tests/dsd/run.py --phase P00 --results tests/dsd/results/P00
python3 tests/dsd/measure.py --phase P00 --results tests/dsd/results/P00/numeric
python3 tests/dsd/bench.py --phase P00 --results tests/dsd/results/P00/bench
```

`make check-dsd DSD_PHASE=Pxx` selects the future phase's required expected-
failure lifetimes; future phases add cases to `run.py`, never weaken the
existing registry. `--mode unit|integration|all`, `--only 'glob'`, and explicit
`--sox`/`--probe` paths are available for development. A selected suite with
zero tests is a failure. An expected failure pins the complete independently predictable returned
bit slice as well as count and position. In particular, the DFF MANF xfail
checks the extra ASCII `M` byte; the multichannel seeks check their displaced
slices; WAV checks all 433 observed zeros. DFF writer fingerprints pin only
deterministic trailing bytes beyond the separately known uninitialized first
cluster. `integration_xfail_audio_mutation_rejection` verifies that mutating
such returned audio does **not** preserve an xfail **before its designated
repair phase**. Once the phase arrives, the mutation test stops requiring
the old defect and its ordinary regression requires a hard pass.
`unit_P01_xfail_mutation_transition` verifies that policy for a corrected P01
writer while keeping later P03 reader and P04 Type 5 checks active. Every expected failure
has a defect ID, a future repair phase and an executable fingerprint. An early fix is XPASS (failure), an
unrecognized failure is FAIL, and an old defect surviving its repair phase is
FAIL. `make check` remains an independent generic regression gate, but exit zero
is **not** full coverage: the P00 host skipped seven format groups and returned
`VOID` for eight generic regressions. They are **unrun**, not passes. The
line-by-line evidence, prerequisites and reproducible reconciliation script
are under `results/P00/build/corrective-generic-coverage.*` and
`corrective-coverage-reconcile.py`. Run missing checks on hosts with the
appropriate format/tool/Windows support, not by changing production handlers.

## Reference separation and count semantics

`reference/fixtures.py` writes containers directly from per-channel timelines
with a frozen seed, never from the SoX writer. `reference/verify.py` separately
parses on-disk chunk extents, bit order and DoP markers. Its chronology is
compared against independent hand constants and the fixture manifest. `frames`
means chronological frames **per channel**; public SoX sample counts are
`frames * channels`. The DSF Type 4 and Type 5 distinction is explicit.

`fixtures/manifest.json` records SHA-256 of every fixture and the hash of its
chronological interleaved bits, source/license, rate, channels, role order and
expected operation. DSF payload block padding does not add logical frames;
DFF final bytes complete partial frame groups using the approved 0x69 pattern.
DoP transport files store PCM24 little-endian words (payload LSB, payload MSB,
marker) and count 16 DSD frames per output transport frame. Synthetic PCM
WAVs are source stimuli, not a DSD numerical-quality claim.

## Reproducibility and evidence

`results/P00/run.json` contains one record per named case and every executed
subprocess with arguments, environment overrides, stdout, stderr and exit code.
Unexpectedly failing `run.json` records are archived under their content hash
before any subsequent overwrite. Build command logs and exact exit codes live
under `results/P00/build/`. `measure.py` implements fundamental/DC fitting,
explicit power units and a frozen window choice. Its P00 analysis-v1 result
says **unrun** until the separate coefficient-generation/certification work
exists. `--prepare-analysis-v1` writes the frozen generation request; it does
not install filter coefficients or claim qualification.

`bench.py` runs actual SoX processes, including I/O, on deterministic generated
inputs. The default 0.006-second development matrix is **not** a performance
qualification; it still covers DSD64/128/256, 1/2/6 channels, native repack
and 352.8/705.6 kHz direct ultra-quality decode. For longer controlled jobs,
select `--profile full --duration N --warmups 2 --repetitions 15`. Each
repetition is saved atomically, including failures. `--resume` refuses a
changed binary, build source, host fingerprint or benchmark configuration and
runs only missing repetitions. Host-specific speed claims require the longer
matrix, a controlled physical machine and bandwidth-matched comparisons.

All paths are local; no licensed recordings, external data downloads or network
access are required for ordinary P00 tests. A skipped/unrun qualification gate
is documented as such and never counted as a passing test.

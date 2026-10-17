# DSD and rational SRC evidence index

This directory stages the independent DSD audit, exact C regression results,
real-FIFO timing evidence and P15 source assessment for the production SRC change.

## Path mapping

Original workspace prefix: `/workspace/scratch/4dd8292178b8/agent_dsd`.

Each original `agent_dsd/<relative path>` is retained here as `<relative path>`.
Repository destination: `tests/dsd/results/SRC_RUNTIME_OPTIMIZATION_2026-10-17/agent_dsd`.
Original commands and hashes remain unchanged. Supporting source files referenced
by commands remain in the repository; rebuild with corresponding configured
include and archive paths when the original workspace prefix is unavailable.

The P15 assessment is also copied verbatim to
`docs/dsd/SRC_RUNTIME_OPTIMIZATION_P15_ASSESSMENT_2026-10-17.md`.

## Contents

- `correctness-final/`: final-header exact O2, O3 and x87-fallback results,
  commands, logs and all three executables.
- `real-fifo-final/`: complete primary final timing, 765 raw rows,
  source/executable/raw hashes, metadata and reproducible statistics.
- `analyze_real_fifo.py`: standard-library statistics summarizer for the final
  C benchmark rows, invoked with this directory's `real-fifo-final` path.
- `threshold/`: temporary threshold comparison, source/header snapshots,
  executable, raw output and explicit incomplete-result metadata.
- `correctness/`: preceding configuration results and logs, including the
  LeakSanitizer environment failure and successful address/UB follow-up.
- `profile-screens/`: fresh DSD64/128/256 profile measurements, commands,
  diagnostic/output hashes, raw gmon output and gprof text.
- `real_fifo_O2.jsonl` and its summary: pre-final dispatch comparison, preserved
  with its original identity instead of being presented as final-source evidence.

## Preserved limitations

The temporary threshold process reported success but retained 861 of 867 expected
rows. Its final case has thirteen measured rounds; the preceding sixteen cases
have fifteen. The original raw rows and explicit anomaly remain intact.
The final primary run has all 765 expected rows.

The final binary has a small latency increase on one- and two-input stage calls;
the assessment reports it alongside sustained gains. These are virtual-host,
stage-level timings and do not establish prepared physical host qualification.
The exporter describes initialized graphs; it does not execute the filters or
provide a new P15 certificate. Old source-bound receipts retain their old scope.

## Omitted deterministic audio and redundant executables

Generated `.dsf` fixtures and `.wav`/`.s32` outputs are omitted. They are
reproducible from the retained `profile_dsd_screens.py` procedure and the
repository's `tests/dsd/profile_decode.py` helpers. Fixture parameters, commands
and recorded fixture/output hashes remain in JSON and logs. The C benchmark
constructs its own deterministic fixtures in memory.

Older redundant correctness executables are omitted; their exact commands,
binary hashes, source identities and results are retained. Final O2/O3/x87
correctness binaries and the temporary threshold executable are included.

`EVIDENCE_INDEX.json` lists every copied and omitted source-relative filename,
its size, omission reason, provenance mapping and known anomalies. Payload before
this index and README: 147 files, 16,191,154 bytes.

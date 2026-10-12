# P12 restart checkpoint (2026-10-11)

Input: `sox_ng-P12-39998c36.tar.gz`; verified SHA-256
`58f3a6a9051b846a97bee770237cf1e41113c864caaa73fd2f8f9e6954b320ec`.
The input contained no `.git`. P11's final handoff authorizes P12.

Scope: independently compiled no-FMA AVX2 kernels (FIR full-width AVX2
permutations for 4 output times and streaming FIR; SDM coordinate-neighbor
permutations), feature-gated selection, executable regression, analysis-v1
cross-ISA and throughput evidence. No defaults or coefficients changed.

For a subsequent session, use this complete source tree. Read `P12.md` for
final verified gates and exact evidence paths. Never infer qualification from
the existence of an output directory. Existing P00-P11 evidence is inherited,
not regenerated. Original archive above is an immutable byte checkpoint.

Status: AVX2 code and public decoder streaming now pass forced CLI and channel wrappers. Full phase qualification is running; failures and reruns are retained separately; consult P12.md for final disposition.

## Verified intermediate state (2026-10-11, after qualification)

Actual `autoreconf -fi`, configured `-O2 -g` build, `make -j2`, and
`make check` have exited 0. An initial P12 `make check-dsd` exposed an
unbound AVX2 streaming decoder; the subsequent repair was independently
exercised. Its initial nonzero log is under
`tests/dsd/results/P12/build/check-dsd.log` and it is NOT counted as a
pass. A premature `measure.py` attempt lacked a not-yet-built P09 helper;
the original nonzero log is retained. Both gates were rerun on the repaired
source and exited 0, as do `run.py` and `bench.py` for P12.

Primary replays and raw receipts are in
`tests/dsd/results/P12/check-dsd-final/` and
`tests/dsd/results/P12/phase-{measure,run,bench}-final/`. The all-tier
15-repeat kernel and short end-to-end benchmark finished PASS at
`tests/dsd/results/P12/bench-reviewed/benchmark-matrix.json`.
A longer 15-repeat DSD64/128/256 stereo end-to-end matrix is currently
running at `tests/dsd/results/P12/bench-long/`; do not assume it passed
until its JSON `status` is PASS. No dispatch preferences have changed.

`tests/dsd/results/P12/build/commands.tsv` is the exit-code log. Compile
commands and all test logs are preserved in that directory. The P12
AVX2-on-host unit, 37 forced CLI conversions, 32 channel conversions,
full analysis-v1 cross-ISA, and static ISA-isolation tests pass. The
historical P11 QEMU execution receipt is inherited, not reexecuted; this
host has no qemu-x86_64. The inherited P00-P11 measurement corpus and
immutable historical evidence have not been altered.

## Final closure (2026-10-11)

All 15-repeat benchmark matrices completed with status PASS: short stereo,
mono and six-channel at `bench-reviewed/`, and longer DSD64/128/256 stereo
at `bench-long/`. Final `autoreconf`, `configure`, `make`, `make check` and
P12-enabled direct unit test exited zero. The final check-dsd replay of
the delivered source exited zero, in `check-dsd-delivered-final/` (the
previous synchronous replay was terminated by the invoking tool timeout;
its partial log is retained, not counted as a numerical failure).
Do not modify these source bytes or receipts after the P12 source manifest
and bundle are constructed. Review `P12.md` and the portable evidence audit.

## Corrective checkpoint (2026-10-11)

P12 benchmark external-results-root hotfix applied. Only two local expressions
were corrected in `tests/dsd/bench_p12_matrix.py`: the evidence path and
failed-child progress logging. Both full 15-repeat successful matrices and
one deliberate child failure have receipts in `tests/dsd/results/P12/bench-path-*`.
Consult the appended P12 handoff for statuses; no P13 work has started.

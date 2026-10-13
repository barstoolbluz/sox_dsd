# Resume checkpoint - COMPLETE investigation, 2026-10-12

Input: sox_ng-perf-question-d2bd98df-2026-10-12.tar.gz
SHA-256: 4d0bcd399914f2433563e9ab7a236f7916c42dd613a466d4c04a1ac91c168120
Authority: docs/dsd/DSD_DESIGN.md, unchanged.

The investigation, measurement tooling and validation are complete. Read
PERFORMANCE_HANDOFF.md and docs/dsd/PERFORMANCE_INVESTIGATION_2026-10-12.md.
Current source/result bytes are bound by PERFORMANCE_SHA256SUMS.txt. The review
patch applies cleanly to the input tree and reproduces the changed/new source
and document files. No production DSP code, coefficient, guard, default or
certificate changed; no next phase was implemented or authorized here.

The authoritative final measurement set is controlled/kernels,
controlled-final/decode-88200, controlled-final/decode-44100,
controlled-final/decode-with-report, and controlled/encode-e2e under
 tests/dsd/results/PERF_INVESTIGATION_2026-10-12/.
All final runs passed. Preliminary controlled/decode-* wall values are not the
basis of conclusions; see exploratory/README.md. Keep those histories intact.

Validation: clean configured build; 13 tooling tests; inherited kernel units;
make check exit 0 (recorded optional skips/VOID cases); make check-dsd with
DSD_PHASE=P14 exit 0. Production identity: all 258 original C/header files.
The raw logs, local audit binaries, gmon samples, source/executable/input hashes
and original session scripts/checkpoint are retained under the result directory.

Future work requires a separate authorization. Candidate directions are a
bounded exact-clock/control optimization, an actual half-band-path experiment,
and an execution-tier SDM certification delta. Do not make decode redesign a
prerequisite to SDM evaluation. Do not silently promote defaults or claim that
this VM closes physical hardware or P15 qualification.

To extend evidence, rebuild using the report commands and choose NEW result
directories. Do not rerun historical orchestration scripts blindly: they record
ephemeral session paths and may expect previous steps. The profiler deliberately
refuses existing evidence directories. Its partial atomic receipts survive an
interrupted run; preserve them and start a separately named continuation run.

# FINAL STATUS: COMPLETE - 2026-10-12

The investigation and delivery are complete. Build, 13 tooling tests, final
measurements, configured make check and explicit P14 DSD regression all passed.
All 258 original production C/header files remain byte-identical. The optional
measurement tools and report are the only implementation scope; no phase,
coefficient, guard, certificate, ABI or automatic default changed.

Final source/report artifacts are /mnt/data/sox_ng_performance_investigation.tar.gz,
/mnt/data/sox_ng_performance_investigation.zip, the matching report .md and review
.patch. Read the external *_delivery_verification.json and *_SHA256SUMS.txt
for the current archive identities. The package's RESUME_CHECKPOINT.md is the
consumer-facing completed-state record. The remaining text below is preserved
chronological session history, not an instruction to rerun completed jobs.

Final measurement basis: evidence/controlled/kernels,
evidence/controlled-final/decode-88200, decode-44100, decode-with-report, and
evidence/controlled/encode-e2e. Preliminary timeout-polled wall timings are
excluded from conclusions. Production/executable/gmon/fixture digests and
patch reproduction are checked during packaging. Full original-tree file
preservation and both archives' per-file hashes are also verified.

---

# Performance investigation checkpoint - 2026-10-12

## Scope
Investigate P14-perf-question.md; no phase work or default/certification changes.
Deliver full source bundle, minimal measurement fixes if supported, detailed findings,
reproduction instructions and honest test/host limitations.

## Inputs verified
Archive: /mnt/data/sox_ng-perf-question-d2bd98df-2026-10-12.tar.gz
SHA-256: 4d0bcd399914f2433563e9ab7a236f7916c42dd613a466d4c04a1ac91c168120
4766 archive members extracted with Python tarfile data filter.
Baseline: /mnt/data/perf_investigation/baseline/sox_ng
Working tree: /mnt/data/perf_investigation/work/sox_ng
Authority: docs/dsd/DSD_DESIGN.md; no AGENTS.md or CLAUDE.md found.

## Environment
GCC, clang, make, autoconf, automake, gprof, Python and git available.
perf and valgrind absent. Check libtoolize before bootstrap.
CPU: AMD EPYC 9V74 under KVM, 5 virtual CPUs, AVX512 exposed.
This is NOT the user's physical 7970X and cannot close physical dispatch gates.

## Work so far
Read brief and inspected source/layout/design. No source changes yet.
Investigating whether microbench kernel/stimulus matches actual decoder hot path.
Need build, verify reported arithmetic/raw evidence, inspect dispatch and certified
SDM route, gather attributable profile/control measurements, decide minimal scope.

## Resume next
Read src/dsd_kernels_{scalar,sse2,avx1,avx2,avx512}.c,
src/dsd_decode.c, tests/dsd/bench_p11.py and test_p11.c; physical evidence under
 tests/dsd/results/P13_amd_physical_avx512_2026-10-12/.
Read docs/dsd/sows/P15.md and design 8/10 before recommending any default decision.
Persist commands/results under /mnt/data/perf_investigation/evidence/.

## Confirmed findings (source and arithmetic)
All four vector *_direct FIR functions immediately call scalar for halfband=1.
Decoder feed_* calls only single-output direct kernels; block FIR is not wired
into production reconstruction. DSD64 mastering has four 57-tap halfbands and
one 117-tap final dense FIR: steady-state halfband/final call ratio 30:1.
Old benchmark uses synthetic dense 153-tap FIR, halfband=0, stride=1.
P12 and P13 kernel stimuli use the same code; different frame count is not
independent stimulus construction.
Brief pass-2 full tier span = 2.2613%, not 1.2%; 1.2% is max vs scalar.
Amdahl using 1.17 and 1.115 gives 70.984%, not roughly 80%; not an attribution.
Clean GCC build and baseline P11/P12 kernel units passed.
Link-only -pg profile copy built using unchanged optimized objects; no -pg
compile instrumentation. GNU gprof documents -Q flat samples for this case.
Initial profiles launched via checkpoint/profile-initial.sh; logs/results in
 evidence/profile-initial/, exit receipt pipeline.exit. Check before further timing.

## Measurement tooling implemented
Changed only test/benchmark/build-test infrastructure; no production C/header
has changed. Extended test_p11 --bench with exact production 57/117/153/257-tap
banks and stride-two single/block workloads. Existing modes remain default.
New profile_decode.py uses a normal timing binary and link-only -pg sampling
binary. Diagnostic --dsd-report is an untimed preflight by default; its output
must hash-identically to plain timing/profile outputs within each tier.
Optional report control is explicit. It retains each result atomically and
refuses to overwrite previous evidence. 12 new regression tests pass, covering
metadata, FIR checksums, fixture oracle, invalid parameters, host metadata,
profile denominator and no-overwrite behavior. Existing P11/P12/P13 C units pass.

## Additional source finding
src/dsd_public.c: sox_dsd_decoder_process feeds ONE native frame per call to
reconstruction and calls lsx_dsd_count_convert on EVERY native frame. The
latter performs checked integer divisions. Initial link-only profiles find
large scalar-FIR and bookkeeping costs (not a whole-FIR <1% result).
Reporting adds native stats overhead; do not use --dsd-report in timed baseline.

## Running pipeline
checkpoint/measure.sh (PID in measure.pid) executes sequentially, no concurrent
build: exact-bank microbenchmarks, plain 88200 5 tiers, 44100 SSE2 control,
report-enabled SSE2 control, existing encode/decode e2e 5 tiers.
Evidence: evidence/controlled/. Status: evidence/measure-pipeline.log and
measure.exit. Do not start a competing build while it runs.

## Historical physical evidence limitations
Physical benchmark-matrix.json refers to seven child JSON artifacts absent from
its delivered directory. The three recorded production source hashes match.
Five-tier medians exist as text, without delivered raw per-repeat values.
Do not claim independently verified physical confidence intervals.

## Profiler wall-timer correction (must rerun final profiles)
Initial controlled/decode-* profiles used Popen.wait(timeout) indirectly;
POSIX polling quantizes parent wall time. CPU and gprof samples unaffected.
Preserved old script in evidence/exploratory. New script uses a blocking wait
with sleeping timeout watchdog, disk-backed logs and explicit timeout receipt.
After measure.sh completes, run 13 tooling tests, then fresh three profile
runs into controlled-final/. Use final reruns in report. Kernel/e2e runners
are unaffected (kernel self CPU timer; e2e pipes/communicate).

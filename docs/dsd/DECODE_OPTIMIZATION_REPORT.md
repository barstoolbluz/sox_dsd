# Production DSD decoder optimization: engineering decision

October 12, 2026, America/New_York. Implementation and virtual-host validation
complete; physical-hardware performance qualification is not claimed.

## Decision

Retain two local changes: a fixed-order sparse specialization of the production
57-tap half-band FIR, and consolidation of native-frame reconstruction/counting
work up to the next existing intermediate-output boundary. No block queue,
lookahead, new dependency, mastering-policy change or SDM default change is added.
The four production files contain 55 added lines and 10 removed lines, including
comments. Tests and measurement tools are separate from this production delta.

The specialized scalar calculation won against the tested SIMD reduction and
bounded block alternatives in the actual decoder. SIMD is not intrinsically the
right optimization for this sparse single-output workload. The combined changes
save approximately 39-45% of paired median CPU time in the main single-thread
DSD64/128/256 cases on this KVM host. This is time saved, not a throughput-percent
claim, and not a physical CPU dispatch qualification.

Starting archive SHA-256:
`3f0704e1c38ae7bb0359c4a23d516558808dc746dcde61fd22baa548c91bf27f`.
The final eight-file implementation identity is the SHA-256 of
`IMPLEMENTATION_SHA256SUMS`:
`b5f2b990ab85b0baf9feaca6b9c5b8298224e9a25eb9cbe24adcd02290e02fc9`.
The archive's `SOURCE_SHA256SUMS` covers its complete delivered contents except
that manifest itself. The external manifest identifies the compressed archive
and review patch; historical investigation manifests retain their original scope.

## Independent experiments and rejected alternatives

Every production timing arm used the supplied measurement primitives, actual
CLI decoding, input/output I/O, two warmups and 15 randomized/interleaved timed
repetitions. CPU affinity was fixed. Raw commands, executable hashes, fixtures,
output hashes, wall/CPU times, RSS and empirical confidence intervals are retained
under `tests/dsd/results/DECODE_OPTIMIZATION_2026-10-12/` (called **evidence** below).
Inputs are valid seeded native-bit performance stimuli, not a new musical-quality
corpus. GCC 14.2.0 release builds use `-O2 -g`, without global native-ISA flags.

On the independent stereo DSD64-to-88.2-kHz screen, the ordered FIR saved 25.2%
paired median CPU time; the tested SSE2 tap-lane reduction saved 21.7%. The latter
reassociates arithmetic and was slower, so it was rejected. Count deferral alone
saved 3.1% in the first screen and 2.3% in the control screen. Bounded reconstruction
consumption alone saved 4.8%; reconstruction plus count consolidation saved 15.8%.
These are measured independent/combined arms, not additive predictions. See
`measurements/screen-independent/paired.json` and `screen-control/paired.json`.

The first block-repeat experiment wastefully used eight lanes even for SSE2.
It is preserved as exploratory evidence, not used as the fair comparison. The
corrected minimum-native-width repeated-output block arm, with no future input
or staging architecture, was still 16.5% slower in the real decoder. A separate
real stride-two stage test included input assembly, retained history and output
traversal. The ordered helper took about 8 ns/output; the fastest tested block
configuration was about 13.6 ns for SSE2, 10.4 ns for AVX1, 10.9 ns for AVX2 and
9.6 ns for AVX-512. All stage checksums matched. This does not measure a complete
batched decoder or prove that no future batching scheme could win. It provides
no justification for paying the integration and streaming cost now. Only the
small direct implementation is retained in production.

## End-to-end results

Representative SSE2 results below are process medians, including I/O. Paired CPU
ratios differ slightly from ratios of medians. All before/after PCM output bytes
matched within each forced tier, including real multithread execution.

**DSD64, stereo, 2 seconds to 88.2 kHz:** CPU 0.477396 to 0.278478 seconds; wall
0.477944 to 0.279019 seconds. Paired CPU ratio 0.5921, empirical 95% interval
0.5807-0.6003: 40.8% less CPU time.

**DSD128, stereo, 1 second to 176.4 kHz:** CPU 0.529532 to 0.311581 seconds; wall
0.530332 to 0.312284 seconds. Paired ratio 0.5790, interval 0.5642-0.5996:
42.1% less CPU time.

**DSD256, six channels, 0.5 seconds to 176.4 kHz:** CPU 1.400421 to 0.783753
seconds; wall 1.401018 to 0.784350 seconds. Paired ratio 0.5641, interval
0.5619-0.5665: 43.6% less CPU time. The new wall/audio ratio is still 1.57;
this VM does not decode that case in real time on one thread.

**The same DSD256 case with explicit two-thread execution:** CPU 1.536769 to
0.947074 seconds; wall 0.944412 to 0.623743 seconds. Paired CPU ratio 0.6144,
interval 0.5833-0.6376. Wall time falls 34.0%. The initially labeled two-thread
arm omitted `--multi-threaded`; setting `OMP_NUM_THREADS=2` was insufficient.
That original receipt is retained but superseded as thread evidence. The corrected
arm explicitly sets the option, and its aggregate CPU/wall ratio exceeds one.
See `validation/THREAD_MEASUREMENT_CORRECTION.md`.

The final matrix also improves 44.1/48-kHz final resampling, 705.6-kHz output,
wideband mono/six-channel cases, reporting enabled, and a 20-ms short file.
Short-file wall time falls from 4.219 to 3.434 ms. Scalar, SSE2, AVX1, AVX2 and
AVX-512 are all exercised in the principal stereo cases. `BENCHMARK_SUMMARY.json`
indexes every comparison and its raw receipt.

Legacy decoding, the public PCM rate effect, scalar/SSE2 SDM encoding and native
DFF read/repack controls retain byte identity. Their paired changes are small,
but dispersion exceeds the controlled gate's 2% threshold. No material
regression was observed; these controls remain **inconclusive for physical
performance acceptance**, rather than being converted to PASS. Prepared-host
repetition is still necessary. Sampled profiles corroborate the removed work,
but coarse histogram bins can misattribute neighboring symbols; neither their
percentages nor a missing sample establishes an exact call count.

## Correctness argument and scope

The graph's only half-band bank has 57 taps. The new helper keeps the scalar
reference's center-first, ascending odd symmetric-pair operations. It removes
zero-coefficient tests and loop bookkeeping, not terms or precision. The scalar
oracle remains intact, no FMA/reassociation is enabled, and dense FIR/SDM kernels
are unchanged. Existing forced-tier selection still governs the dense stages.

The public decoder previously called reconstruction and exact count conversion
for each native frame. With no held PCM, reconstruction can now consume input
only until it produces its next intermediate frame, using its existing
one-frame output capacity. No output can become releasable before that event.
A held PCM frame retains one-native-clock advancement. The original exact
integer count helper executes once per accepted span, before the next release
decision. It is not replaced by floating point, reciprocal arithmetic or a new
rounding rule. Finalization still computes the exact final count independently.

The offered span is capped by the reconstruction's existing finite-tail reserve,
so an overflow still accepts the same valid prefix before the same sticky error.
An invalid native value likewise preserves the consumed prefix in the internal
report, while public error returns retain zero consumed/produced counts. The
opaque context adds one `uint64_t`; audio buffers, latency and public interfaces
are unchanged. Coefficients, profiles, guards, reference-level behavior, dispatch
defaults and P10's scalar mastering recurrence are byte-unchanged.

## Validation and explicit limitations

Release `make check` passes on both source trees, with seven unavailable optional
format families and eight VOID regression cases. Full `make check-dsd
DSD_PHASE=P14` passes, including available numerical, streaming, error, count,
forced-ISA, channel, DoP, seek, reporting and ISA-isolation gates. The new unit
passes 113,573 assertions and 1,270 stream cases on each of five tiers. Independent
baseline/candidate public call, sample and error transcripts match byte for byte
on all five tiers. Tests cover irregular input, tiny output capacity, finite
EOF, all admitted rate/profile combinations, invalid prefixes, uint64 reserves,
half-up holdback, four rounding modes, subnormals and guard-page spans.

Clang ASan+UBSan passes changed-path/streaming/bounds tests on its four admitted
tiers. Its existing AVX-512 isolation-flag probe rejects that tier; its build also
lacks OpenMP. GCC ASan+UBSan passes the new unit on all five tiers and the P13
unit with `detect_stack_use_after_return=0`. Default fake-stack mode crashes
both original and optimized P13 binaries at the unchanged dense AVX-512 stack
store; disassembly and both reproductions are retained. Bounds/UB/leak checks
remain active in the passing run, but fake-stack/use-after-return coverage is
not claimed. GCC ASan-only real CLI forced-tier/buffer/thread tests, public-rate
numerical goldens and streaming pass as additional memory checks, not as a
replacement for full UBSan.

The complete generic sanitizer gates are **not green**. Original and optimized
Clang builds both reproduce an out-of-range float-to-uint64 conversion at
`formats.c:1398`, a negative left shift at `raw.c:89`, and the sample test's signed
shift. The ASan-only generic harness caps virtual address space at 1 GiB and
replaces `ASAN_OPTIONS`; ASan cannot reserve its shadow memory under that cap.
Baseline and candidate `--version` probes demonstrate the harness blocker before
any decoding. These unchanged issues were not repaired in an audio-performance
patch. Raw failures remain available beside the passing scoped runs.

The P10 certificate checker fails on both trees because four source bindings
predate later phase changes. All 35 certificate inputs are unchanged by this
optimization. No historical certificate was rewritten. P11's inherited replay
and 549-state integrity verification passes; this is receipt verification, not
a new hardware replay or long soak. Prepared physical Intel/AMD/older-AVX runs,
non-x86/32-bit execution, new QEMU runs and hardware-counter profiling were not
available. `VALIDATION_SUMMARY.json` is the gate ledger, including these limits.

## Delivery and continuation

The complete source archive includes original investigation material, current
source, tests, rejected experimental snapshots, matching measured executables
and libraries, raw observations, profiles, command logs and hashes. The minimal
review patch contains only the four production changes, two Makefiles, new unit
and paired benchmark. It intentionally excludes bulk evidence and narrative
files. Its application against the supplied archive is independently checked.

The current root `RESUME_CHECKPOINT.md` supersedes the inherited checkpoint,
which is preserved inside the new evidence directory. Build/reproduction
instructions are in `evidence/README.md`; `tools/reproduce_decode_optimization.py`
rebuilds independent variants from the hash-checked input and refuses an existing
work directory. P15 SSE2 mastering-default work is documented separately in
`docs/dsd/P15_SSE2_SDM_QUALIFICATION_DELTA.md`. No default is activated here.

The appropriate next step is prepared-host qualification of this small patch,
not a larger FIR or batching subsystem. Investigate only a reproduced regression
or an actual uncovered qualification requirement; do not discard accepted P10/P11
evidence or commission duplicate one-hour SSE2 runs merely because older summary
fields are stale.

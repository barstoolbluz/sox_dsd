# Decoder optimization checkpoint

Starting source: /mnt/data/sox_ng_performance_investigation.tar.gz
SHA-256: 3f0704e1c38ae7bb0359c4a23d516558808dc746dcde61fd22baa548c91bf27f
Unmodified extraction: /mnt/data/dsd-work/baseline/sox_ng
Working tree: /mnt/data/dsd-work/sox_ng
Receipts: /mnt/data/dsd-work/receipts

Completed: verified archive, extracted independent baseline, read inherited
checkpoint and investigation. Reading governing design and production hot paths.
No implementation or qualification claims yet. Host AMD EPYC 9V74 under KVM,
5 virtual CPUs, GCC/Clang/autotools available. Physical hardware unavailable.
No SDM default or P10 reference changes authorized.

Next: complete design/source review; build independent baseline; benchmark
specialized direct 57-tap half-band FIR and exact-count/control candidates
separately; retain only demonstrated production improvements; regression and
sanitizer validation; package source/patch/manifests/raw evidence/report/P15 delta.

## Candidate builds complete
Five independent executables built from the supplied source: baseline,
fir-ordered, fir-sse2-reduced, count-only, fir-block-repeat. Source snapshots
in experiments/<variant>/src; binaries/static libraries in variants/<variant>,
with build commands, logs and hashes. No retained decision yet. Working source
currently contains the last experimental block-repeat variant, NOT a final tree.
The single-change randomized 15-repeat production screen is running from
run-screen.sh; progress is atomically written to measurements/screen-independent/paired.json.
Do not concurrently build or stress CPU 1 during timings.

## Independent evidence and next combined candidate
Single-change screen complete (15 repeats, randomized, KVM CPU 1): ordered FIR
median paired CPU ratio .7482; SIMD tap-lane reduction .7830; count-only .9690.
Block-repeat experiment first used 8 lanes for every tier; that was wasteful
on SSE2. The corrected native-width repeat arm remains slower (.1.165 ratio)
and is rejected. True stride-two block costs are still to be measured at stage
level; no batched reconstruction architecture is proposed.
Control screen: reconstruction-only .9515, count-only .9770, count+reconstruction
.8419. Full 1,270-case scalar differential call/sample/error transcripts match
baseline for ordered FIR, count-only, reconstruction-only and control-combined;
73,563 assertions per run. No combined performance claim yet.
Working source is now the combined candidate: ordered FIR plus existing
reconstruction consumption up to one intermediate frame, preserving tail reserve
and accepted error prefix; public opaque context adds one uint64 limit, no queue.
New test and paired benchmark source added. build-final.sh is running; check
receipts/final-build.exit, then benchmark final all tiers and workload controls;
run make check and full check-dsd P14, sanitizers, ISA isolation and profiling;
write final decision and separate P15 SSE2 qualification delta; package/verify.

## Current authoritative state (supersedes earlier progress paragraphs)
Combined build passed and is saved as variants/combined/sox_ng. Working source
contains ordered scalar sparse halfband plus bounded existing-reconstruction
consumption and consolidated exact counts. P10 reference/SDM defaults unchanged.
First final production matrix cases passed all five tiers, PCM byte-identical:
DSD64 median paired CPU ratios .573-.609; DSD128 .564-.601 (15 repetitions).
run-final-matrix.py is executing remaining rate/channel/SRC/thread controls.
run-post.py waits for it, then runs unchanged-path controls, real stride-two
stage benchmark, before/after sampled profiles, generic/full P14 regressions,
certificate receipt checks, and all-tier exact public API differential replay.
run-sanitizers.py waits for post.exit, builds a separate Clang ASan+UBSan tree,
then runs changed-path, boundary, forced-ISA and generic checks. All three
scripts write commands/raw logs/exit receipts under receipts/ or validation/.
Do not start competing throughput workloads until performance-complete.exit.
No completed final validation or physical-hardware qualification claimed yet.
P15 evidence review: P10 latest adjudication CERTIFIED/CLOSED, P11 final replay
COMPLETE. Existing P11 nine one-hour rate/family groups include SSE2; 549 states
already supplied. Reuse valid accepted evidence, do not call these unrun gaps.
Next after runners: inspect every exit/log, fix concrete failures only; document
retained/rejected decisions, noise and physical qualification limits; refresh
checkpoint; construct clean authoritative tree from original archive + explicit
changes + evidence, generate review patch and SHA manifests, verify extraction
and patch application. Never promote SDM or mastering defaults in this work.

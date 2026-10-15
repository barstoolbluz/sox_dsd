# Reviewed P15 amendment: physical Intel AVX-512 performance evidence

**Decision (2026-10-14): APPROVED, FEATURE-SCOPED.** Normative operative
language is in `docs/dsd/DSD_DESIGN.md` section 10.7, immediately following
the previously mandatory physical-hardware requirement. This companion records
the decision and its limits, not a new DSP tolerance or an alternative test.

## Original rule and deviation

The original rule expressly required an Intel AVX-512 run and described a
skipped run as a gap. Section 13's existing optional hardware gaps did not
include this one. The original closeout correctly marked it **UNRUN**, and
it remains **UNRUN** after this amendment. Its absence was not, and is not,
reclassified as a test success.

Operator constraint: representative physical Intel AVX-512 hardware is not
available and is not expected to become available for this release. The
operator explicitly asks to proceed without an Intel-specific performance
claim, rather than pretend a benchmark was executed. The conservative
section 8.4 automatic policy remains SSE2 on unknown supported CPUs and
scalar otherwise, with higher tiers available only through validated force.
No Intel-specific preference is proposed; no observed-vendor equivalence or
Intel AVX-512 physical throughput assertion is supported. A hardware test that
cannot influence this retained dispatch policy should not block the limited
release *solely to measure that unsupported claim*.

## Binding scope

- **Permitted:** the already conservative first-release automatic dispatch
  policy, with no new Intel-specific kernel/workload preference and no
  Intel AVX-512 performance/physical-compatibility/vendor-parity claim.
  Preserve the ability to request supported higher ISA tiers explicitly,
  subject to unchanged functional and runtime feature checks.
- **Not waived:** ISA correct execution on supported configurations, CPUID and
  XGETBV capability checks, instruction isolation, numerical acceptance,
  all other actual hardware requirements, benchmark target/control validity,
  software-format and corpus gates, streaming/state correctness or general
  regression gates. Neither unknown-CPU preference nor production mastering
  is promoted by this decision.
- **Still UNRUN:** physical Intel AVX-512 performance. Do not write PASS,
  PASS-SCOPED, SKIP-PASS or an invented performance figure into a release
  manifest; retain a visibly scoped **UNRUN-SCOPE-EXEMPT** status.
- **Reactivated:** before any future Intel-specific automatic AVX-512
  preference, cross-vendor timing assertion, physical Intel-specific claim or
  compatibility claim that implies direct Intel silicon qualification.
  Obtain representative physical execution and workload/correctness evidence,
  then independently adjudicate it. This amendment is not an automatic
  waiver for a broader P16+ feature set.

## Adjudicated first-release status

The 2026-10-14 R2 receipt coverage still does not close the composite SRC
numerical gate. The revised DSD256 comparison has 15 timed runs per arm,
but its declared *bandwidth-matched* legacy control cuts off near 20 kHz
while the DSD256 mastering reconstruction guarantees a 40 kHz passband.
The Intel exception removes only the irrelevant performance-policy
prerequisite; it does **not** authorize first-release promotion or P16 while
those real quality/performance gates remain open.

Historical manifest and recorded measurements remain unchanged. The P15
readjudication creates a new ledger rather than rewriting old UNRUN labels.

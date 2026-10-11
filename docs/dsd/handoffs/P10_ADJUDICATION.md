# P10 adjudication and positive reviewer certification (2026-10-11)

**Decision: P10 CERTIFIED and CLOSED for the three current scalar composite
mastering profiles. P11 may begin. No automatic profile activation, default
migration or authorization of P11's prospective runtime-ISA kernels is implied.**

The authoritative machine-readable decision is
`tests/dsd/results/P10_certification_2026-10-11/certification.json`.
It explicitly reverses the *current disposition* of the earlier incomplete P10
reviews, without rewriting their original failure/UNRUN receipts or generated
negative-profile manifests. The built-in `qualified=0` flags, conservative
production CLI refusal and P15 activation policy remain unchanged. The phase's
measured acceptance status, ability to opt into a *production release*, and
future-kernel qualification are distinct questions.

## Basis for certification

The evidence in the supplied source snapshot was assessed under the reviewer's
**previously frozen**, versioned criterion at
`tests/dsd/reference/p10_ratification_criteria.json`, as constrained by
`docs/dsd/DSD_DESIGN.md` sections 7.2, 10.1, 10.2 and 10.5 and
`docs/dsd/sows/P10.md`. The unmodified ratification collector returns `PASS`
for all ten gates, including eight inherited gates and the independently
adjudicated one-hour and real-world-source criteria. It reports no remaining
release gate. Its `qualified=false` is deliberate: that collector is an
*evidence assessor*, and cannot issue an explicit positive certificate for
itself. This document and the separately pinned positive certificate make
that reviewer decision.

- **Scalar one-hour hardware gate: PASS.** Three 3,600-second single-state
  mixed-content runs cover DSD64, DSD128 and DSD256: 71,124,480,000 native
  frames, 71,124,479,919 complete 28-bit windows, 183 hashed continuation
  files, no recorded nonfinite states, no 0.5-envelope/guard breaches and no
  DSD64 population excursions. Frozen state limits and snapshot/frame/command
  identities are checked by `ratify_p10_gates.py`. Reported physical machine:
  Ryzen Threadripper 7970X. This is *operator-reported* provenance, not
  independently attested hardware execution.
- **DSD-origin corpus: PASS.** Eighteen independent external excerpts, six
  per native rate; 14 unity admissions and four correct explicit overload
  rejections recovered with declared 0.1–1.0 dB attenuation. Retained
  preserve-reference measurements meet the level, duration and bit-window
  rules. The reader/oracle self-check is recorded.
- **Ordinary-PCM corpus: PASS.** Seventeen distinct commercial-release excerpts
  at each native output rate, 51 complete admitted renders. Thirteen genres,
  both 44.1-kHz and 48-kHz source clock families, source-decoding checksum
  receipts and output DSF digests are retained. Levels are measured at the
  `sacd` reference, not the DSD-origin `preserve` reference. All frame counts,
  window counts, output digests and paired source/target records satisfy the
  criterion. Input audio remains externally held.
- **Frozen quality, counts, overload and regression gates: PASS.** Inherited
  analysis-v1, numerical identity, routing, deterministic 30-minute soaks,
  CLI and generic regressions remain assessed as PASS. No P10 spectral
  threshold, guard, profile coefficient or admission envelope was changed.
- **Prepared-host read/repack: PASS on newer evidence.** The previous collector
  cites its older accepted 2026-10-09 P09/P10 comparison. The separate
  2026-10-11 prepared-host hotfix record is the more appropriate *current*
  throughput receipt, since its candidate binary SHA-256 matches the PCM
  corpus's recorded SoX identity. All 16 workloads pass at 40 AB/BA pairs;
  worst noise is 0.91%. The `dff-6ch-repack-small` regression is -4.4294%
  relative to the tested pre-hotfix comparison binary. Original collector
  output is retained, not retroactively rewritten. Its different historical
  benchmark remains valid for its historical scope.

The new certificate binds 35 code/criteria/evidence paths to SHA-256 values.
`python3 tests/dsd/check_p10_certification.py` re-runs the criterion collector,
compares the frozen gate assessment, cross-checks PCM target records, source
integrity flags, reconstruction reference and benchmark executable identity,
and rejects mutated receipts. It does not *create* certificates, run external
media without the files, or switch any profile on.

## Resolved uncertainties and explicit limits

1. The proposed SSE2 kernel objection does not apply to this composite.
   `src/pcmdsd.c` enters `sdm_normal_step_guarded`, which calls the explicitly
   scalar `sdm_normal_step_impl`. `sdm_filter_calc_sse2` in `src/sdm_x86.h`
   belongs to the separate legacy filter path. An SSE2-capable baseline
   compiler/CPU does not change which recurrence qualified. The one-hour
   criterion's `current_mastering_kernel_family=scalar` is correct.
2. Neither independently sourced corpus measures internal integrator extrema
   or a whole-file post-interpolation overshoot maximum. The published
   criterion explicitly does not mandate new external audio state/spectral
   instrumentation; the independent frozen synthetic soaks cover that
   separate obligation. No independent *real-world* state or spectral claim
   is certified, and no universal-stability conclusion follows.
3. The zero PCM unity rejections do not demonstrate under-testing against
   the agreed criterion. Ordinary PCM scales by 0.5 while DSD-origin
   remodulation preserves the DSD reference. This expected difference in
   available headroom is not evidence of an extra 6.0206 dB loss. The frozen
   overload fixtures, explicit DSD rejection/retry records and two-source-
   domain checks remain necessary.
4. Seventeen PCM albums suffice, despite excluding two unverified FLAC
   candidates. A missing FLAC STREAMINFO MD5 is a limitation of this
   runner's preferred bit-integrity proof, not proof that the audio is
   unusable by *every possible* authenticated decode process. The five
   176.4-kHz releases share an artist/catalogue lineage but represent
   different recordings and meet the reviewer's **minimum two distinct
   external recordings per native rate**. No claim of comprehensive
   catalogue/artist diversity is made.
5. The 4096-byte-alignment hotfix has measured residual layout sensitivity:
   a separate perturbation improved the DFF canary by another 2.70% despite
   preserving alignment. The fix empirically passes the prepared-host
   acceptance gate; it does not prove performance independent of future
   linker layouts. This is a profiling/backlog issue, not a new P10 release
   threshold, and no speculative rewrite is requested.
6. Commercial-source provenance, file digests, FLAC STREAMINFO checks and
   the one-hour host identity were supplied by the operator. They were
   independently **cross-checked as receipts**, not verified by possession of
   the original recordings, rebuilding the exact historical hardware binary
   or rerendering 19 private releases. The criterion explicitly permits this
   distinction. The certificate does not claim cryptographic proof of the
   operator's machine or sourcing and is scoped to those receipts.

## Limits of authorization

- **P10**: accepted/closed for `encode.mastering.v1.dsd64`,
  `encode.mastering.v1.dsd128` and `encode.mastering.v1.dsd256` using the
  current guarded scalar recurrence and unchanged source/coefficients.
- **P11**: permitted to begin. Every newly introduced runtime kernel/ISA family
  requires fresh one-hour representative-hardware qualification and the
  applicable cross-ISA/numerical gates before its own release claim.
- **P15/defaults**: **not authorized**. Existing `src/pcmdsd.c` qualified flags,
  reference negative certificates, old reports and production CLI defaults
  remain as delivered. Promotion/activation is a later explicit change.
- This certificate does not approve trellis defaulting, new coefficients,
  automatic gain reduction or resets, wideband/higher rates, or arbitrary PCM
  files above the nominal encoder envelope.

## Engineering corrections and preservation

The default evidence made `tests/dsd/test_p10_ratification.py` stale: it
expected the *earlier* `INCOMPLETE`/`PARTIAL` corpus receipt. The test now
asserts the newly passing evidence status while continuing to demand
`qualified=false` from the **precertification collector**; it adds negative
cases for absent PCM evidence and the wrong PCM gain reference. No production
DSP or timing-sensitive code was touched. New files: this adjudication,
`P10_ADJUDICATION_WORKLOG.md`, `tests/dsd/check_p10_certification.py`, and
`tests/dsd/results/P10_certification_2026-10-11/`.

Older results are byte-for-byte preserved. Do not overwrite
`P10_ratification_2026-10-10/qualification.json`: it is a historical partial
receipt. Do not overwrite the operator's `P10_gate_assessment_2026-10-11`.
Original benchmark JSON may include historical absolute paths; this closeout
makes no new such records and cannot rewrite those bytes under the stated
preservation rule. New records only name paths relative to this continuation
source tree. No private commercial source audio or copy of the attached brief
is packaged.

## Validation

See `P10_ADJUDICATION_WORKLOG.md` for the exact commands, observed exit codes,
unrun external tests and packaging checks from this closeout. The 2026-10-11
hardware/audio measurements are accepted as retained evidence, **not claimed
as work executed in this reviewer environment**.

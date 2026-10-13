# Independent audit of the decode optimization on the prepared host

Audited the delivery `sox_ng_decode_optimized.tar.gz`, SHA-256
`905e55736f29a432c912f1e27fec7c549d1d8aead69a019d7e390da757aaeb19`, against
baseline `d2bd98df`. Our checks, which have been wrong before.

## Verified

- **Production delta is exactly as described**: four source files, +55 -10
  lines. `src/dsd_decode.c`, `src/dsd_kernels.h`, `src/dsd_kernels_scalar.c`,
  `src/dsd_public.c`.
- **Invariants intact**: `dsd_coeffs.h`, `pcmdsd.c` (admission envelope),
  `sox_dsd.h` (public ABI), `dsd_dispatch.c`, `sdm.c` and all of
  `dsd_kernels_{sse2,avx1,avx2,avx512}.c` are byte-identical to baseline.
- **Bit-exactness**: 30 of 30 combinations byte-identical to baseline across
  two sources (DSD64, DSD128), three output rates (88200, 44100, 176400) and
  five forced FIR tiers. The optimized tree still yields one hash across tiers.
- **Error paths**: identical exit status, output hash and stderr across
  corrupted payloads at four offsets and three truncation lengths.
- **New regression** `dsd_test_decode_optimization` passes on all five tiers,
  113573 assertions and 1270 stream cases each. It takes the tier as argv[1];
  `SOX_DSD_KERNEL_FIR` does not steer it because the test sets `kernel_fir`
  through the P11 options struct.
- **Gates**: `make check` 0, `make check-dsd` 0 at 36 pass / 0 fail,
  `test_p14` and `test_p14_numeric` 0, all on the integrated tree.

## Measured speedup, physical prepared host

AMD Ryzen Threadripper 7970X, CPU 8, performance governor, boost off, 9
repetitions, median wall seconds. The delivery's own figures are from a KVM
guest; these are not.

| case | baseline | optimized | speedup |
|---|---|---|---|
| DSD64 to 88200, scalar | 0.5299 | 0.2969 | 1.78x |
| DSD64 to 88200, sse2 | 0.5272 | 0.2978 | 1.77x |
| DSD64 to 88200, avx2 | 0.5273 | 0.2974 | 1.77x |
| DSD64 to 88200, avx512 | 0.5267 | 0.2968 | 1.77x |
| DSD64 to 44100, sse2 | 0.5371 | 0.3080 | 1.74x |
| DSD128 to 176400, sse2 | 1.0581 | 0.6039 | 1.75x |

1.72x to 1.78x, a 42% to 44% reduction, consistent with the delivery's claimed
40.8% to 43.6%. The gain is the same on every tier, including the shipping
SSE2 default.

## Why our earlier measurements missed this

We reported that decode moves under 1% across the whole FIR tier matrix and
could not say where decode time went. This change explains it. Every tier's
`accept_frame` routed half-band stages through that tier's generic FIR with
per-tap zero handling, so all five tiers performed the same dominant wasteful
work and switching tiers could not help. The optimization routes half-band
stages in all five tiers to one fixed-order 57-tap specialization, 15
multiply-adds instead of 57 taps, preserving the reference's center-first
ascending-pair order so no output bit changes.

So decode was FIR-dominated after all, and our tier-sensitivity measurement was
measuring the wrong thing, not reporting an absence. We had explicitly declined
to offer a mechanism; the mechanism was this.

## The sanitizer disclosure is accurate, and the defect is in our baseline

The delivery states that default ASan fake-stack mode crashes the baseline's
unchanged AVX-512 kernel. We reproduced that on baseline `d2bd98df`, which
contains none of this optimization:

```
ERROR: AddressSanitizer: SEGV on unknown address
  #0 _mm512_storeu_pd  avx512fintrin.h:9361
  #1 lsx_dsd_fir_avx512_direct  src/dsd_kernels_avx512.c:72
  #2 fir  tests/dsd/test_p13.c:168
```

With `detect_stack_use_after_return=0` all four P13 groups pass. So the crash
is pre-existing, is not introduced here, and the disclosure is honest.

We are not diagnosing it. Note only that the P13 FIR test is deliberately
page-bounded to catch overruns and passes without ASan, so a plain fixed
overrun would already have been caught; the interaction may be with fake-stack
placement rather than a kernel defect. That is a question, not a finding. It is
in code never selected by default, AVX-512 FIR being opt-in only.

## What we did not integrate

The delivery is 523 MB and 9427 files. Excluded from the repository:

- 192 MB of built artifacts: `binaries/`, `variants/*/libsox_ng.a` and
  compiled test executables, 68 files.
- 3540 raw `.txt` timing dumps and 18 `.dsf` / 2 `.wav` fixtures under
  `measurements/`, and the bulk `validation/` transcripts, about 90 MB.

Retained: every `.json`, `.md` and `.exit` receipt, 400 files and 13.8 MB,
plus the production source, the new regression test and the three new tools.
The complete delivery remains in the tarball named above if raw dumps are ever
needed. Nothing excluded was evidence we relied on for the claims here.

## Still open

- Physical hardware performance qualification of the ISA tiers remains open and
  is not addressed by this change.
- The delivery's unchanged-path controls exceeded the controlled noise
  threshold on its own host. Our 16-workload read/repack gate has not been
  re-run against this change.
- The P10 certificate's historical source-binding mismatch reproduces on the
  supplied baseline, as the delivery states.
- No default changed, no profile promoted, SDM remains scalar. P15 governs
  activation.

# Independent audit of the P15 qualification continuation

Audited `sox_ng-P15-qualification-continuation-2026-10-12.tar.gz`, SHA-256
`224ee8f5eb326cdd183bf975de59490c700df84636849a1f46f3922387fc5d8f`, against
baseline `f13dda14`. Our checks, which have been wrong before.

## The reviewer's stated limit, closed

The continuation's reviewer recorded one limit: the original `f13dda14` archive
was not attached to them, so they could not compare every inherited file
against it. We have that commit and did the comparison.

- 4547 files in the `f13dda14` tree.
- 9 modified by P15: `Makefile.am`, `sox_ng.1`, `src/dsd.c`, `src/dsd.h`,
  `src/dsd_plan.c`, `src/sox_ng.c`, `tests/dsd/bench.py`,
  `tests/dsd/measure.py`, `tests/dsd/results/P00/P00_SHA256SUMS.txt`.
- 8 files added.
- **0 removed**, and the remaining **4538 are byte-identical**.

No inherited evidence was altered or dropped.

## Verified

- **Invariants**: `dsd_coeffs.h`, `pcmdsd.c` (admission envelope), `pcmdsd.h`,
  `sdm.c`, `sox_dsd.h`, `dsd_dispatch.c`, all five kernel files, `dsd_decode.c`
  and `dsd_public.c` byte-identical to baseline. The automatic default
  resolution block in `dsd_dispatch.c` is byte-identical: SSE2 FIR where
  available, scalar mastering SDM.
- **Manifest**: 4730 entries, every one verifying; tree holds 4731 files and the
  manifest excludes itself. Exactly as the delivery claims.
- **Build and gates**: build clean, `make check` 0, `make check-dsd` 0 at 36
  pass / 0 fail, `test_p15.py` 0 with **134 passed / 0 failed**.
- **Compiler warnings unchanged**: 22 in both trees. The
  `dsd_unavailable defined but not used` warning is present in the baseline
  too, so it is pre-existing dead code from P05 rather than introduced here.
- **Release manifest**: `status BLOCKED`, `default_promotion_authorized false`,
  and `--require-qualified` exits 2. Against the delivered evidence it reports
  exactly the **six** unclosed mandatory gates the reviewer named.
- **Behaviour**: both release profiles work (`-p mastering`, `-p wideband`
  exit 0); conflicting `-l` flags are refused with a diagnostic and exit 1; all
  nine documented PCM output rates including 48000 are accepted, which is
  correct and not a clock defect.

## Corrections to our own first pass

- We initially reported **eight** unclosed gates against the reviewer's six.
  That was our error: we ran `p15_release_manifest.py` against a fresh empty
  `--results` directory, so it found no evidence and marked the two
  available-host gates UNRUN. Pointed at the delivered evidence it reports six.
  The reviewer's count was right.
- We initially read `48000` output as an incorrect-clock case. It is a
  documented supported rate; all nine appear in `test_p15.py`. Not a defect.

## One finding the reviewer did not report

`dsdpcm -p legacy` and `--dsd-decode legacy` fail at every rate with a stale
P05-era message, while being advertised in the effect help, the manpage and the
new P15 migration guide, and while no P15 test exercises them. Detail and the
reasons we do not read this as contradicting the reviewer are in
`legacy-decode-profile.md` beside this file.

## Our own defects, repaired here

Two evidence files we committed earlier carried session scratch paths:
`tests/dsd/results/P13_amd_physical_avx512_2026-10-12/benchmark-matrix.json`
(7 occurrences) and
`tests/dsd/results/DECODE_OPTIMIZATION_2026-10-12/read-repack-gate-prepared-host.json`
(689). Both are sanitised to a `<session-scratch>` placeholder with the JSON
still valid and the measured values untouched. The repository now contains no
scratch paths. P15's own redaction pass covered 28 files of 175 scanned and did
not reach these two, which is consistent with them being ours rather than its.

## Still open

The six mandatory gates stand: independent spectral release matrix, physical
Intel AVX-512 performance, physical older-AVX performance, the six-channel
DSD256 reference target, current-revision full release soaks per profile and
ISA, and the independent codec and hardware corpus.

Of those, physical Intel AVX-512 is unobtainable to this project, and physical
older-AVX is not obtainable on this host either, which carries AVX2. The
remaining four are reachable here given time.

No default changed, no profile promoted. P15's own handoff states the
qualification is incomplete and that P16 must not be entered on an assertion
that P15 closed. We agree with that disposition.

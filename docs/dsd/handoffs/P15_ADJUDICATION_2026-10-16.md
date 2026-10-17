# P15 independent adjudication, 2026-10-16

## Revision, custody, and scope

Input: `sox_ng-P15-adj-ab7f0f56.tar.gz`, SHA-256
`e119c315d192cb44f8abb1bf3ae61f4e30a4cef9394e5a7f089ebdecd24b5cde`.
Operator-reported tip: `ab7f0f56`; this archive does not contain `.git`.
The input's historical measurement receipts, DSD_DESIGN.md, and production
DSP C sources are not modified. The P00 transport inventory is versioned to
cover the new scripts, tests, documentation and one observation, while
retaining indexed digests of the 946 intentionally omitted `.npz` files.
**No historical P10 or P15 release record is edited.**

## Gate decision (do not collapse conjunctions)

| Gate | Decision | Basis and unfulfilled requirement |
| --- | --- | --- |
| DSD256 direct 2x | MEASURED-SCOPED | 8/8 bootstrap lower CI comparisons clear 2x. |
| DSD256 matched comparator | OPEN | 2026-10-15 control spectral receipt measures approximately 6.014/6.017 dB decoder/control difference at 65,999 Hz, **inside** the published v2 DSD256 66,000-Hz passband. The historical verifier excluded the last 5% post hoc. A fresh verifier now checks the **entire passband** (`TRANSITION_EXCLUSION=0`) and is regression-tested against this failure. This mismatch does not itself prove that either absolute transfer violates its individual specification; it disproves the presented matched-control claim. No passband change or retrospectively altered receipt. |
| Intel AVX-512 physical | MEASURED-SCOPED | Raw samples, median/MAD, source hashes, repeated/cross-tier output digests and four-tier frequency records independently cross-checked. i9-11900H **operator-attested** physical host, not externally attested. Block-FIR 1.9149×; FIR single 1.2056×; SDM 0.9895×; twelve conversions 0.9870–1.0099×. No evidence for an end-to-end AVX-512 preference. Historical `UNRUN-SCOPE-EXEMPT` is not rewritten. |
| 72 SRC-active cells / 24 SRC clock pairs | OPEN | Earlier 38 sampled-tone tests, native FIR and the different-transfer comparison cannot prove the required source-bound same-transfer arithmetic or continuum composite extrema/coherent aliases. Reported R5 arithmetic PASS is not reproducible from this snapshot: checker and four support modules are not present. Source binding, exact SRC operator, finite-support proof, FFT4G arithmetic, all alias families, and 72-cell coverage remain. |

**Overall: BLOCKED. P16 not authorized; v2 default unchanged/off.**

The original R2 DSD256 timing/control receipt remains open. Its narrow 20-kHz
control is not quietly reclassified. There is no new Intel dispatch preference.

## Executable work supplied

- `p15_intel_receipt_review.py` independently reconstructs the Intel
  comparisons from the provided raw timing observations. Receipt identity
  is not an independent physical-host attestation.
- `p15_readjudication.py` separately reports direct timing and **full**
  effective-passband control agreement. The historical cropped result remains
  evidence but cannot supply the match decision.
- `verify_dsd256_control_match.py` no longer excludes the passband edge.
- `p15_src_continuum_bounds.py` performs arbitrary-precision interval/Taylor
  enclosure of a *provided* finite trigonometric coefficient witness. It
  conservatively adds coherent alias-family magnitudes and can detect
  violations between sample points. The routine has no production binding;
  even a witness-only mathematical `PASS` is **not a P15 SRC PASS**.
- `p15_src_operator_observations.py` invokes the actual private SRC probe,
  capturing every input phase class for a reduced rational ratio and a
  periodic-shift control. No coefficient truncation is invented. The 88.2
  → 48 kHz smoke acquisition captured all 147 input phases and 80 output
  shifts, max absolute residual `1.676737633286851e-13` in binary64.
  Its `phase-f64.npy` and JSON are SHA-coupled, atomic/no-overwrite and
  resumable after SHA/source validation. Its status remains
  `OBSERVED_UNCERTIFIED`; the probe cannot prove a source-independent
  transfer identity, exact infinite precision or spectral bound.
- New regression tests exercise the error boundaries and refusal paths.

## Precise SRC closure obligations

1. Supply `p15_src_same_transfer_checker.py` with the missing
   `p15_src_alias_coverage.py`, `p15_src_transfer_graph.py`,
   `p15_src_extrema_bounds.py`, and `p15_src_symmetric_interval.py`
   from the arithmetic R5 workstream **or** audit and implement replacements
   tied to the exact tree. Verify hashes before integration. A 57-character
   prerequisite digest in an earlier checkpoint is unusable as a SHA-256 pin.
2. Independently derive and bind every stage of private SoX SRC from
   `src/rate.c` and the selected runtime coefficients: ratio reduction,
   polyphase schedule, interpolation, halfband/FFT4G convolution, binary64
   coefficient realization, delay, zero-extension and output counts. A
   measured finite impulse is useful for cross-checking but **not** that
   derivation. Certify the 24 distinct operators or any distinct realization
   that changes a previously shared clock pair.
3. Replay §8.6.1's **input-dependent** error inequality for each of 72
   SRC-active cells, from independently reconstructed `W`, verified FIR
   inputs, audited operation count and coefficient/primitive error terms.
   Include first/last output, phase extremes and finite boundaries; do not
   compare unlike resampler designs to a made-up global tolerance.
4. Combine each independently bounded SRC polyphase transfer with the
   appropriate native-FIR filter. Enumerate **all** coherent alias families,
   both decimation/interpolation, continuous passband/stopband extrema and
   the complete-chain prescribed limits. The included interval routines
   are reusable mathematical primitives, not a substitute for composition
   or source identity. Do not omit bins or frequencies from guaranteed
   bands to achieve PASS.
5. Request/retrieve the SHA-matching 946 omitted `.npz` originals (including
   270 R3 matrix arrays reportedly not yet transferred) before attempting
   complete numeric replay. Do not replace omitted originals with new runs
   under the old receipt names.
6. Independently review the full results; create a **new** dated ledger, and
   only then consider defaults, release or P16. No new full hardware/soak
   matrix is required absent a genuinely changed production implementation.

## Known inherited defect

`test_p15_closeout_review.py` already reports `measured session source differs:
src/dsd_decode.c` (two failures, one error in the incoming snapshot).
It is preserved. No source-lock exception is added merely to turn the test
green. Current-source review and this legacy reviewer have different pin
assumptions and must not be conflated.

## Operator commands

At repository root, with Python 3, NumPy, SciPy and mpmath installed:

```sh
PYTHONPATH=tests/dsd python3 -m unittest -q \
  test_p15_adjudication_corrective test_p15_src_continuum_bounds \
  test_p15_src_operator_observations test_p15_current_closeout \
  test_p15_src_envelope_review

PYTHONPATH=tests/dsd python3 tests/dsd/p15_current_closeout.py \
  --output /tmp/P15-closeout-2026-10-16.json --require-release
# Exit 2 = correctly BLOCKED. Existing date-scoped output is checked before reuse.

# Build SoX and the P07 test probe in a separate build directory/checkout.
# This command intentionally exits 2: the operator has been OBSERVED, not certified.
python3 tests/dsd/p15_src_operator_observations.py \
  --probe /path/to/test/dsd_test_p07_reference \
  --input-hz 88200 --output-hz 48000 --frames 8192 \
  --output /tmp/P15-src-operator-88200-48000
```

## Integrity and interruption

The repository contains a `tests/dsd/results/P00/P00_SHA256SUMS.txt` transport
manifest for all indexed files other than itself; its omitted entries remain
hash-pinned. Raw historical evidence files and normative design sources were
not changed. The distributable tarball has a separate SHA-256 checksum.

On interruption, start with
`docs/dsd/handoffs/P15_RESUME_CHECKPOINT_2026-10-16.md` and rerun the above
checks. No user or agent should infer release acceptance from green
unit tests or from a mathematical witness test without operator binding.

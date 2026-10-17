# P15 remaining numerical/spectral certificates: corrective checkpoint R1

**Date:** 2026-10-16 America/New_York (source-audited work, no release signature)  
**Base archive:** `P15_COMPLETE_SOURCE_OPERATOR_2026-10-16_FULL_REPO.tar.gz`  
**Base SHA-256:** `168b29ed5b0af6577894b903094b1f09d4630b89de3a5776762fc23d1e9a6e30`  
**Binding authority:** `docs/dsd/DSD_DESIGN.md` §§6.1, 8.6.1, 10.4.  
**Final disposition:** `PARTIAL-MATHEMATICAL-CERTIFICATES`; release remains **BLOCKED**, mastering v2 stays **OFF** by default.

## Executive decision

The native FIR generator has now been independently bounded against its ideal *exact-rational* Kaiser/sinc definition. All 24 source-captured SoX SRC FFT coefficient-bin arrays have been independently bounded relative to the exact DFT of their source-captured binary64 design taps. A conservative, stagewise, signed-alias, directed-interval spectral verifier establishes *specific closed continuous-frequency intervals* across the full native FIR + private SRC cascade; it is deliberately not described as a complete continuum certificate for 72 matrix cells. Finally, a new DSD256 legacy control with the *correct transition width and center* has been verified on a full-passband test fixture, including a wrong-cutoff negative control.

**These changes do not prove arbitrary-input FFT4G transform execution or full-band global extrema.** They cannot close either substantive release gate. Historical matrix measurements, P10 certificate, source code, generated v2 FIR coefficients, ISA/dispatch decisions, and the old post-hoc-cropped comparator evidence are unchanged.

## Independently proven / observed, separated by type

### 1. Native FIR coefficient bank ideal-to-binary64 directed interval

`tests/dsd/p15_native_coefficient_interval.py` uses exact-rational frequency specifications, 112-decimal-digit outward interval arithmetic, and a positive-series definition of modified Bessel `I0` with an explicit geometric remainder bound. IEEE754 nearest-even rounding is proved by placing an exact interval strictly between the *exact rational* binary64 midpoint neighbors. It independently checks 1,439 native bank entries in **seven** banks: **1,421** strictly correctly rounded to the ideal definition; **18** not incorrectly rounded-to-zero by the historical finite-precision generator. Those 18 have an independent strict **2^-280 absolute deviation upper** from the ideal sinc-zero coefficient and remain classified `TINY_GENERATOR_ARTIFACT`. Failing either proof is an error, not a silently tolerated larger threshold. All bank/header identities are hash-bound.

Receipt: `tests/dsd/results/P15_REMAINING_PROOF_2026-10-16/native-interval-certificate.json`.

**Scope:** native FIR *source bank* quantization relative to the mathematical design. It is not the private SoX SRC Kaiser generator. It neither proves FFT4G execution error nor changes previously frozen P06 native-bank certificates.

### 2. Complete 24-rate-pair realized FFT coefficient-bin interval bound

`tests/dsd/p15_fft_coefficient_interval.py` and `p15_fft_bin_matrix_interval.py` work from the source-bound operator snapshots and `operator-binding.json`. Each verifies the *actual source-captured binary64 FIR design taps* are scaled exactly by the power-of-two `L/N` in `src/rate.c`; it then independently evaluates a radix-2, outward-rounded, 80-decimal-digit DFT of that exact real vector. The code bounds the deviation of **every** packed FFT4G real and imaginary coefficient bin from the mathematically exact DFT, including DC/Nyquist. It gives conservative bin-deviation totals and overlap-save single-impulse coefficient contributions without discarding small bins.

All **24 distinct SRC rate pairs** have individual immutable receipts and a digest-bound summary: `tests/dsd/results/P15_REMAINING_PROOF_2026-10-16/fft-bins/`.

**Scope:** this is *precomputed FFT coefficient realization*, not the forward/inverse FFT execution on arbitrary streams. It does not reproduce source C `lsx_design_lpf`'s theoretical Kaiser output. The separate full-chain ideal operator already represents the **realized binary64 design taps**, so the nominal filter-design discrepancy must not also be counted as an arithmetic discrepancy against the *same* operator. The FFT coefficient-bin difference, by contrast, must be included in the appropriate execution coefficient/other term in the final arithmetic bound.

### 3. Directed-interval stagewise global-alias method, locally applied

`p15_src_stagewise_alias_proof.py` reconstructs every realized FIR stage as a rational upsample/filter/downsample element with exact clock `L/M` and exact source-verified binary64 taps, using the existing source-inlined stage exporter. Native reconstruction banks are inserted at the beginning. `p15_src_stagewise_continuum.py` expands *all* reverse stage harmonic paths (never a thresholded subset), checks that the source family population and identities match the full stage-specific period, and bounds each stage factor with the 75-digit directed Taylor/complex-trigonometric checker. The coherent unwanted bound is a linear sum of **absolute path amplitudes**, not an RMS average or a bin/grid sample. A band crossing a branch/wrapping boundary must be partitioned; source family relabelings at an exact endpoint use the analytically continuous one-sided interior limit.

The passband mode requires the interval to lie inside the governing profile's P; it certifies `10^(-0.0001/20) < total amplitude < 10^(0.0001/20)` and coherent aliases `< 1e-8`. The stop-source mode bounds **all source harmonics with absolute native frequency >= S** that fold to every output frequency in the stated interval, not merely output frequencies themselves above S. A source harmonic reaching the stopband anywhere within the interval is conservatively included throughout the interval. Failure to close within an explicit node/path budget is `OPEN`.

Persisted local witnesses under `tests/dsd/results/P15_REMAINING_PROOF_2026-10-16/local-continuum/`:

- Mastering DSD64, 88.2 -> 44.1 kHz, continuous output 1000–2000 Hz: **PASS-LOCAL-BAND** with 8 directed subintervals; this is a meaningful 1 kHz *continuum*, not a sampled tone.
- Mastering DSD64, 88.2 -> 44.1 kHz, 1000–1000.001 Hz: PASS-LOCAL-BAND.
- Mastering DSD64, 88.2 -> 176.4 kHz, output 70000–71000 Hz: **PASS-LOCAL-STOP-SOURCE**, native source frequencies >=40 kHz only; a nested 1-mHz interval is retained separately.
- Candidate mastering-v2 DSD256, 176.4 -> 705.6 kHz, output 1000–1000.001 Hz: **PASS-LOCAL-BAND**.
- Candidate mastering-v2 DSD256, 176.4 -> 705.6 kHz, output 100000–101000 Hz: **PASS-LOCAL-STOP-SOURCE**, native source frequencies >=80 kHz only; a nested 1-mHz interval is retained separately.

**Crucial limit:** proving a named short band is not proof of every point in P, every stop-source contribution on the entire output interval, or all 72 profile/rate combinations. A future driver may cover the rest with resource-bounded exact interval partitioning; no full-band/current gate status is upgraded without checking the union covers every required closed interval. Source and design hashes appear in every local receipt, including the validated operator-binding file and stage snapshot. Their SHA manifest and test implementation must also be preserved for reproducibility.

### 4. DSD256 v1/v2 bandwidth-matched comparator

`p15_dsd256_comparator_2026.py` constructs a **new** staged control `rate -v 352800; sinc -a 180 -t (S-P) -((P+S)/2); rate -v` for both decoder profiles, with P/S taken from the frozen design: v1 **40/80 kHz**, v2 **66/80 kHz**. In contrast, historical `sinc -66000` put the 6 dB point at v2's nominal end-of-passband; excluding the upper 5% after measuring its 6 dB disagreement was invalid. On a common six-second native DSD256 broadband fixture, all four positive comparisons to the decoded v1/v2 outputs at 176.4/352.8 kHz meet the existing independent 1-dB agreement limit across **100%** of the guaranteed passband. The observed worst among them is **0.0065710 dB**. A two-second *wrong 20-kHz* control produces `CONTROL_MISMATCH`, worst full-passband discrepancy >77 dB, confirming the check rejects the known failure mode.

The positive and negative source/binary/audio SHA-bound receipts are under `ps-matched-comparator/` and `ps-matched-comparator-negative-selftest/` respectively. Their audio fixtures are retained for independent replay; verify with `--verify-only` on the same binary identities.

**Important:** these are spectral *comparability* diagnostics, not 0.0001 dB / -160 dB absolute composite transfer proofs, and **not** a new physical 2x benchmark. No historical timing of a different/narrower staged control transfers to this newly matched arm. The DSD256 direct-2x-and-matched-control performance gate remains **OPEN** until the properly matched control is timed in a separately audited, physical six-channel benchmark with the specified repetitions/confidence intervals. Historical OPEN labels are retained.

## Still open: exact deliverables for a future continuation

1. **FFT4G execution arithmetic.** Audit `src/fft4g.c`'s actual `rdft` forward and inverse call tree, trigonometric table-realization error, butterfly/intermediate scaling, packed frequency multiplication, overlap-save and output quantization. Independently justify a finite input-dependent forward-error envelope and `N_ops[n]`/`B_coeff[n]`/`B_other[n]` satisfying normative §8.6.1, including subnormal handling, first/last stream sample, and phase shifts. The precomputed-bin interval proof **cannot** be substituted for this.
2. **Private SRC generator, if claiming analytic-spec equality.** Independently reproduce `lsx_design_lpf` including `lsx_kaiser_beta`, `lsx_make_lpf`, `lsx_fir_to_phase` (if active), and C `libm` error/rounding. This is separate from the source-pinned *realized binary64 tap* operator. The same-operator arithmetic test must count only errors not already represented in `W`, rather than demand exact equality to a different Kaiser design.
3. **72-cell full spectral continuum.** Cover entire effective passband of each cell (with §6.5 `adapt/strict` policy respected), **all** folded high-native-frequency stop-source contributions over the entire supported output Nyquist, and every coherent alias path; also prove endpoints. Retain strict P/S and -160 dB/0.0001 dB limits. OPEN intervals and resource limits are not a pass.
4. **Arithmetic raw input and 2x physical bench prerequisites.** The original R5 same-transfer checker (`p15_src_same_transfer_checker.py` and four source imports) and **946 omitted historical `.npz`** payloads are not in the supplied repository. Use a separately provided, source-verified prerequisite or implement/verify an equivalent; never fabricate or reclassify historical receipts. Benchmark the newly P/S-matched staged control on the proper physical six-channel host. Do not infer performance from this container.
5. **Independent adjudication.** The resulting data require independent math/source review. Do not mutate P10 historic certificate, old Intel `UNRUN` label, acceptance thresholds, or production DSP to turn an OPEN gate green.

## Execution/replay

Run from the top of an extracted `sox_ng` working tree, with Python 3, `mpmath` (interval arithmetic), NumPy and SciPy installed. The snapshot includes *source* and evidence, not compiled executable targets.

```sh
PYTHONPATH=tests/dsd python tests/dsd/p15_native_coefficient_interval.py --output tests/dsd/results/P15_REMAINING_PROOF_2026-10-16/native-interval-certificate.json
PYTHONPATH=tests/dsd python tests/dsd/p15_fft_bin_matrix_interval.py
PYTHONPATH=tests/dsd python -m unittest discover -s tests/dsd -p test_p15_remaining_math.py -v
PYTHONPATH=tests/dsd python -m unittest discover -s tests/dsd -p 'test_p15_src_*py' -v
PYTHONPATH=tests/dsd python tests/dsd/p15_src_stagewise_continuum.py \
  --profile master64 --snapshot tests/dsd/results/P15_SRC_STAGE_BOUND_2026-10-16/88200-44100/stage-snapshot.json \
  --lo 1000 --hi 2000 --max-nodes 128 --mode pass \
  --output tests/dsd/results/P15_REMAINING_PROOF_2026-10-16/local-continuum/master64-88200-44100-pass-1000-2000hz.json
PYTHONPATH=tests/dsd python tests/dsd/p15_current_closeout.py --help
```

The DSD256 verification test skips only if locally built executables are unavailable; it never fabricates a positive replay in that case. Build commands and source-bound stage-export targets are in the previous `P15_COMPLETE_SOURCE_OPERATOR_CHECKPOINT_2026-10-16.md`. The comparator script accepts `--verify-only --sox src/sox_ng --candidate test/sox_p10_candidate --output tests/dsd/results/P15_REMAINING_PROOF_2026-10-16/ps-matched-comparator` and the matching `--selftest-wrong-cutoff` variant for the negative receipt. A different binary hash is a replay precondition failure, not a test success.

**No incomplete run should be described as asynchronously ongoing.** This checkpoint and source/receipt manifest are sufficient for a subsequent, source-audited continuation.

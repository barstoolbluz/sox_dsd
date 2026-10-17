# P15 R2 continuation: exact remaining acceptance obligations

Date: 2026-10-16 America/New_York. Source authority: `docs/dsd/DSD_DESIGN.md` §§6.1, 6.5, 8.6.1, 10.7. Base: `P15_REMAINING_PROOFS_R1_2026-10-16_FULL_REPO.tar.gz`, SHA-256 `34aaabec972d7b11e05d931e88abd4cc3ed55d7ad64bde96ff32374ce1`.

**Disposition: PARTIAL IMPLEMENTATION; RELEASE BLOCKED.** Mastering v2 remains off by default. None of the additional programs in R2 is an FFT4G arbitrary-input execution certificate, a full 72-cell continuum certificate, or a physical-host 2x measurement. Production DSP C code and normative acceptance thresholds are unchanged.

## Work completed in this continuation

1. `tests/dsd/bench_p15_dsd256_ps_matched.py` is a prospective **physical six-channel** benchmark and independently recomputable receipt verifier. It imports the *same* command definition as the full-bandwidth P/S-matched comparator in `p15_dsd256_comparator_2026.py`. It rejects VM execution as eligible physical evidence, checks CPU pinning, uses 15 timed repetitions per arm/cell, randomized arm interleaving, 10,000 reproducible bootstrap iterations, immutable input-fixture hashes and a separate source-/binary-bound FULL-passband spectral-comparator receipt. It preserves a six-channel DSF input and corresponding PCM generator file alongside the JSON receipt. No physical timings are claimed in this development environment. `--dry-run` checks the shape of all 12 commands without accepting a measurement.
2. `tests/dsd/p15_full_band_campaign.py` creates a closed, exactly rational coverage partition for the **72 SRC-active cells** (nine profiles × eight SRC-active output rates each, as actually present in the worklist). For every cell it covers §6.5 `P_effective = min(P_profile,0.475 min(R,F))` and, separately, every output frequency from zero through final Nyquist for all native-source stop-region contributions. At a 1 kHz scheduling partition it builds **11,516 closed, adjoining frequency intervals**. Missing results and resource-bounded OPEN results remain explicitly OPEN, never PASS. Completeness is *mathematical coverage candidate for independent replay*, not a release decision. Intervals are source-/design-/snapshot-bound; each receipt is immutable and atomically published. Existing P15 R1 certificates are imported only if their exact interval, profile, mode, source fingerprint, governing-design digest, stage snapshot and operator-binding digest match. 3 prior 1-kHz witnesses were imported, without recomputation or status upgrade.
3. The new directed-interval `master64` / 88.2 -> 44.1 kHz **0–1,000 Hz** passband proof is `tests/dsd/results/P15_FINAL_OBLIGATIONS_2026-10-16/full-spectrum/` (file content carries the exact interval). Its result was `PASS-LOCAL-BAND`, eight internally verified subintervals, with coherent alias upper `3.422466132795756e-11`. Joined with the independently recorded `1,000–2,000 Hz` interval from R1 (8 subintervals, alias upper `5.2415983989005044e-11`), these are a contiguous, continuous **0–2,000 Hz** LOCAL proof for that one route, not the full effective P=20,000 Hz or any stop-region proof for that route. The upper total gain bound over the two is max(`1.0000001570987038`, `1.0000001570215582`) and lower main gain bound min(`0.9999998427722394`, `0.9999998426621165`); those are diagnostic outward decimal formatting of the individual directed certificates, not an independently re-rounded global metric.
4. Adversarial tests verify exact end-to-end coverage windows and `adapt`, four full-band matched control command shapes, VM rejection, raw-bootstrap recomputation, fixture-integrity refusal, and timeout/open behavior. The six-channel test-fixture generation and all three arm command lines (one v2/176.4 kHz pilot) ran successfully on the development VM, **diagnostic only**, with no eligible timings.

## Why the other obligations remain legitimately OPEN

### Actual FFT4G transform execution

The existing R1 `p15_fft_coefficient_interval.py` bounds precomputed FFT coefficient bins. It does **not** bound `src/fft4g.c`'s runtime `rdft` forward and inverse transforms, the generated twiddle tables (`makewt`, `makect`, `atan/cos/sin` and downstream C libm), real/imag packed multiplications, `rate.c` overlap-save output selection, or bounded tails and subnormal arithmetic. The source contains 4096- and 8192-point FFT-stage realizations, with multiple branches (power-of-two interpolation or F-domain decimation), which require independent butterfly arithmetic propagation, coefficient errors relative to the exact captured transfer W, and the per-output `N_ops`, `B_coeff`, and `B_other` required by §8.6.1. Merely counting executed operations or applying `gamma(N)` to a potentially *cancellation-conditioned* final W is not a proof of bounded execution error. A theorem must use input-dependent absolute error propagation with an explicit admissible input envelope, including head/tail zero padding and gradual-underflow/FTZ/FMA/libm assumptions. The source-file/phase bindings and local agreement tests are groundwork, not such a theorem.

### Full spectral continuum

The only certified intervals are the previously captured seven R1 local witnesses plus the new 0–1000 Hz witness; four currently exactly match the default campaign partition and all other **11,512 worklist intervals remain without campaign receipts**. Absence is not a pass or a failure. The `p15_full_band_campaign.py` driver is structured for bounded repeated runs on a dedicated machine, and exposes limits explicitly. Its worklist completeness does not certify any absent interval. A verified full mathematically sound pass must additionally independently replay the proof checker and evaluate any OPEN cases without weakening the P/S, 0.0001-dB or -160-dB envelope. Resource budgets of existing interval Taylor bounds could require a more efficient *equivalent* analytic method, not a post-hoc bandwidth exclusion.

### SoX analytic Kaiser filter generation

No additional ideal-design proof is required to compare against §8.6.1's **source-captured realized binary64 operator W**. If a release instead claims equivalence to a different theoretical ideal Kaiser design, the `lsx_design_lpf`/`lsx_fir_to_phase`/libm proof is separately obligatory. Do not count the difference from an ideal design as numerical error against *the same captured W*, or assert that equality without proof.

### DSD256 physical matched-control 2x

The available development host is a **KVM guest, AMD EPYC 9V74, 5 logical CPUs**, so it cannot establish a prepared physical-host qualification; `/proc/cpuinfo` explicitly reports `hypervisor`. The new benchmark **has not been run in eligible physical mode**. On the actual physical host, build the pinned SoX_ng binaries, first reproduce a full-passband `p15_dsd256_comparator_2026.py` spectral receipt for those exact binaries, then use `bench_p15_dsd256_ps_matched.py` with `--sox`, `--candidate`, `--spectral-receipt`, `--cpu`, `--output` (a *new directory*, not a JSON file), `--seconds 2`, `--warmups 2`. The instrument will create four cells with 15 repeats for each of three arms. Recompute the four times two ratios from the saved arrays, check both lower 95% confidence endpoints >2, review host CPU/governor/frequency/thermal conditions, and sign off source/build/provenance. Spectral fixture comparability is not itself a performance measurement. No automatic promotion occurs even if all ratios satisfy 2x.

## Replay instructions

From the extracted repository root (Python 3 + NumPy + mpmath):

```sh
PYTHONPATH=tests/dsd python -m unittest discover -s tests/dsd -p test_p15_final_obligations.py -v
PYTHONPATH=tests/dsd python tests/dsd/p15_full_band_campaign.py --output tests/dsd/results/P15_FINAL_OBLIGATIONS_2026-10-16/full-spectrum --summary-only
PYTHONPATH=tests/dsd python tests/dsd/p15_full_band_campaign.py --output tests/dsd/results/P15_FINAL_OBLIGATIONS_2026-10-16/full-spectrum --import-existing --summary-only
PYTHONPATH=tests/dsd python tests/dsd/bench_p15_dsd256_ps_matched.py --sox src/sox_ng --candidate test/sox_p10_candidate --spectral-receipt tests/dsd/results/P15_REMAINING_PROOF_2026-10-16/ps-matched-comparator --output tests/dsd/results/P15_FINAL_OBLIGATIONS_2026-10-16/PHYSICAL_BENCH_DO_NOT_CREATE --cpu 0 --dry-run
```

The full-band campaign deliberately returns code **2** when OPEN, including during successful *partial* proof acquisition. Its receipt files survive a driver interruption. The bench `--dry-run` returns 0 if command construction and spectral receipt verify, even on a VM, but explicitly says `NO_TIMING_PERFORMED` and `physical_host_admissible=false`. The benchmark's real mode refuses VM hosts.

No results in this R2 should be described as a complete release qualification or as a pending asynchronous job. This checkpoint is sufficient to resume a later separate workstream, provided exact source and binary digests still match.

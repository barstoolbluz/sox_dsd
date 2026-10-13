# P15 numerical-matrix and scalar-cross-host decisions

**2026-10-13. Decision for the supplied `1a2d9992` snapshot.** Governing authority: `DSD_DESIGN.md` §§6.1–6.4, 8.6, 10.2, 10.4–10.6 and `sows/P15.md`. This note answers the two questions in `P15-questions.md`; it is **not** a certificate of P15 completion, a new DSP profile, or authorization to change defaults. Historical results remain untouched.

## A. The 3 × 9 × 2 independent spectral qualification

1. **Every scalar cell is mandatory** (three native DSD clocks, both decoder profiles, all nine PCM destinations = 54). The 54 already executed P15 alias-identity conversions and P07 count/routing tests do not pass this gate. For all 54 cells, separately assert count, finite end behavior, latency/phase, effective bandwidth, filter response, coherent summed aliases, numeric reference discrepancy, finite input boundaries, supported channel/buffer/thread invariance, and the applicable clipping/level policy. Use *internal linear* stimuli to characterize FIR transfer functions and *genuine one-bit* material to characterize end-to-end program/noise behavior; do not conflate the two.

2. **Reference mapping is arithmetic, not a judgment by profile:** 44.1, 88.2, 176.4, 352.8 and 705.6 kHz destinations are integer ratios from every DSD64/128/256 native clock: **30 scalar cells**. Compare against direct high-precision, delay- and endpoint-correct *combined* decimated-convolution mathematics, including any final upsampling/interpolation stage (do not omit the SRC merely because the net ratio is integer). The 48, 96, 192 and 384 kHz destinations are rational ratios: **24 scalar cells**. For those, require an independent high-precision fractional SRC reconstruction of the *complete* FIR-plus-SRC chain; a successful invocation of the same private SoX backend is not independent.

   The repository already has P06 high-precision finite-convolution/cascade groundwork and `tests/dsd/test_p07_reference.py` / `test_p07_impulse.py` **selected** independent SciPy rational/polyphase SRC tests. Those are useful starting points, **not** an existing 54-cell end-to-end oracle. Extending and certifying the independent complete-chain oracle is remaining engineering work, not a new performance requirement or new audio filter policy. Record the reference algorithm and hashes separately from the production implementation, with measured numerical error, count and alignment. For extreme endpoints the finite signal and phase/endpoint convention matter as much as steady-state ripple.

3. **ISA release execution vs selected ISA metrology are different obligations.** §10.4 expects the complete representative 54-cell routing/count/phase grid under every *actually supported* scalar/SSE2/AVX1/AVX2/AVX-512 tier during qualification; unsupported hardware is not a pass. Separately run detailed scalar-relative metrology for every native-rate/profile pair on a predeclared, nonadaptive subset of PCM outputs. The worklist chooses **44.1, 48, 384 and 705.6 kHz**, covering low integer, low rational, high rational and maximum integer endpoints for each of the six native/profile pairs. On a host supporting four additional tiers, that is 24 selected cells × 4 comparisons = **96** detailed cross-ISA comparisons, on top of the full functional grid. This selected subset is an engineering implementation of the specification's otherwise-unspecified word *selected*; it is not a waiver of any remaining explicit §10.4 tests or an excuse to avoid extra cells when a defect is discovered. The gate remains open until the actual results are executed and reviewed.

4. **Do not use `analysis-v1` as the 54-cell decoder oracle.** The frozen P09 analysis FIR low-passes to 20 kHz and decimates to 88.2 kHz. It intentionally cannot establish, for example, wideband DSD256 response at 705.6 kHz. Use that *unchanged* and hashed for the PCM-to-DSD modulator quality/stability comparisons under §§10.2, 10.5 and 10.6, including optional second-filter corroboration; build the DSD-to-PCM combined-stage independent reference alongside it. `measure.py --prepare-analysis-v1` only emits a design request; P09 already froze the actual coefficient bytes under `tests/dsd/reference/analysis-v1/`.

5. **Acceptance values are not interchangeable.** For each decoder scalar cell, retain §6.1's profile-dependent effective P/S envelope (maximum **0.0001 dB** passband error, no undesired coherent alias/stopband transfer above **-160 dB**, with the output Nyquist and actual adaptive bandwidth accounted for), §6.4's defined linear-phase/zero-extension/count semantics, and §8.6's FIR accumulated-roundoff bound and at-most-one-int32-LSB graph allowance. The §8.6 FIR-only bound must **not** be borrowed as a fractional SRC tolerance: §10.4 calls for an independently measured *combined-stage* tolerance and its justification. Per-input-program THD+N is not constrained to -160 dB just because the reconstruction filter rejects aliases there. For the **encoder SDM** cross-ISA reference, §10.6's **0.001 dB** gain, phase, **1 dB** residual/THD+N and ultrasonic-noise limits with floor-aware exceptions apply after latency alignment, together with spur/run-length/state controls and the defined pairwise residual criterion. Those figures do **not** define a new blanket decoder FIR tolerance or a universal floor for every cell. No thresholds, profile P/S values or analysis-v1 coefficients are changed here.

**Executable planning artifact:** `python3 tests/dsd/p15_matrix_contract.py --output /path/to/matrix-worklist.json`. The planned rows all report `UNRUN`. Its successful exit means a deterministic worklist was written, never that any metrology passed. The delivered snapshot includes this plan at `tests/dsd/results/P15_questions_2026-10-13/matrix-worklist.json`.

## B. Scalar SDM output differs between machines: decision

**Not automatically a defect or P15 blocker in itself.** §8.6 explicitly states that forcing scalar assists reproducibility **under a pinned build** and is not advertised as universal cross-compiler determinism. The specification does not guarantee cross-host scalar-encoded byte identity. §10.6 uses bit hashes for *within-kernel/build* buffer/thread invariance and native repacking, while cross-ISA SDM equivalence uses frozen reconstructed measurements, spurs, state stability and reference level. A different trajectory from a different host can therefore be acceptable **provided it satisfies the same numerical and stability gates**. Do not weaken those gates or assume either host's bytes are intrinsically correct.

The supplied report establishes **matching WAV file SHA-256** and differing **DSF file SHA-256**, with matching named compiler/libc versions and no linked FFTW. It does *not* establish a byte-for-byte identity of executable binaries, other linked math/dependency paths, floating-point environment, CPU microarchitecture, or whether the changed bytes are DSF audio chronology rather than merely container fields. Those are plausible remaining differences, **not proven root causes**. The resulting FIR *file* hash divergence from a different SDM source is not evidence of a bad FIR implementation; compare the **same native bit chronology** across FIR tiers to measure FIR differences.

The limited P10 positive certificate remains valid **within the revision, input corpus, kernel/profile and measurement scope that it actually states**. Source SHA-256 binding was never a proof of cross-machine byte reproduction. If a future claim needs exact rebuild/audio-byte identity, record complete build/dependency configuration, binary identities, runtime CPU/FP environment and bit-payload chronology rather than treating four source hashes as a hermetic build. Do not retroactively invalidate or rewrite the P10 certificate solely because the design did not promise the stronger property.

If the original WAV/DSF pairs from both machines become available, run:

```sh
python3 tests/dsd/p15_compare_cross_host.py \
  --first-wav hostA/in.wav --second-wav hostB/in.wav \
  --first-dsf hostA/sdm_scalar.dsf --second-dsf hostB/sdm_scalar.dsf \
  --output cross-host-audio-review.json
```

This invokes the existing independent strict DSF reader to compare *logical chronological bits*, count, channels and sample rate. A different bit chronology is recorded as `AUDIO_DIFFERS_NEEDS_METROLOGY`, **not an automatic failure**. Subsequent independent `analysis-v1`/state measurement is the correct quality test. Preserve build/source/environment provenance when presenting that result.

## C. Evidence problem in the attached physical AVX1 record

`tests/dsd/results/P15_avx1_physical_2026-10-13/README.md` describes a prepared *physical AVX1-without-AVX2* machine and quotes timing results. Its shipped `host.txt` instead identifies **AMD Ryzen Threadripper 7970X**, `avx / avx2 yes / yes`, and contains a truncated/malformed virtualization description. The folder contains **only those two files**, with no `kernel/kernel-timing.json`, clock sample log, `gate-eligibility.txt` or per-run output hashes. Therefore this snapshot cannot validate the reported older-AVX host identity or reproduce/adjudicate the performance numbers. This does **not** prove the measurements never happened or that the quoted ratios are false: it identifies insufficient and contradictory *delivered evidence*. The older-AVX gate remains UNRUN/UNVERIFIED in this continuation.

`tests/dsd/check_avx1_physical.sh` previously accepted `AVX1_SMOKE=1` on an AVX2 host without automatically removing gate eligibility. The supplied code now explicitly forces such smoke runs into **DIAGNOSTIC ONLY**, even if clock/governor are controlled. `tests/dsd/check_p15_avx1_receipt.py` enforces independent raw-provenance review and names the current failures. Its `ADMISSIBLE_FOR_INDEPENDENT_REVIEW` status is only eligibility to *review* raw physical-kernel evidence, not a P15 release certificate or full end-to-end hardware benchmark.

```sh
python3 tests/dsd/check_p15_avx1_receipt.py \
  --results tests/dsd/results/P15_avx1_physical_2026-10-13 \
  --output /tmp/older-avx-review.json
# Expected for supplied snapshot: exit 2, status BLOCKED, explicit reasons.
```

## Resulting release disposition

The **full independent scalar matrix is unrun**, cross-host bit mismatch is **not itself a defect**, and the supplied purported physical older-AVX receipt is **not admissible as proof of its claimed machine**. Physical Intel, controlled 2× DSD256, present-version soaks, and corpus rerenders remain governed by the existing six unclosed gates. Automatic mode remains legacy, production mastering `qualified` bits remain false, and no CPU selection policy is promoted. Continue P15, not P16.

This change set is deliberately limited to planning/diagnostic tools, self-tests, documentation, a physical-smoke gate safeguard and a new result folder. No DSP algorithm, ABI, frozen coefficient, legacy PCM or release-default source was modified.

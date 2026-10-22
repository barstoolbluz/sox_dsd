# P20 DSD512 / P19 DSD1024 residual asymmetry — adjudication

**2026-10-22. Finding: EXPLAINED for this diagnostic. No encoder defect established. No production qualification or authorization implied.**

## Direct answers

**Why 37.10 dB at DSD512 but only 3.67 dB at DSD1024?** The P19/P20 synthetic stimulus is rounded to 32-bit signed PCM before encoding. Its quantization noise is already near -200 dBFS after the signal's approximately 0.5 reconstruction scaling. This masks nearly all of the eighth-order residual at both native clocks, and much of the seventh-order residual at DSD1024. A control that removes *only* this quantization (reconstructing the frozen corpus waveform before rounding) reveals a comparable order-reduction penalty at each clock: **40.99 dB at DSD512; 37.47 dB at DSD1024**. The 3.67 dB DSD1024 result cannot be interpreted as the intrinsic cost of reducing SDM order.

**Is 37 dB expected at 22,579,200 Hz?** It is **a reproducible consequence of these specific frozen eighth-order and CLANS-7 candidate definitions, this native clock, this input, and this 128:1 reconstruction**. It is not a universal seventh-order or sample-clock prediction. Neither order nor clock alone determines a noise residual: coefficients, quantizer behavior, passband, reconstruction filters, and stimulus all enter. No evidence here establishes a coding error or a misselected coefficient bank. For this candidate, the corrected seventh-order signal genuinely carries more reconstructed noise than the eighth-order signal. Source quantization masks the full contrast in the historical reports.

**Was -163.04 dBFS deliberately selected as a target?** **No.** The P20 correction selected an existing CLANS-7 binary64 coefficient set for better numerical and bitstream behavior and froze clock-specific guards. It did not design or tune coefficients to an -163 dBFS reconstruction target. **-163.04 dBFS is an observed value**, not an optimization objective, target, threshold, or newly approved audio-quality requirement. Record it as the measured characteristic of the unqualified P20 candidate under the stated diagnostic. Do not reinterpret it as a general noise floor, listening-test result, or quality certification.

## Reproduction and controls

1. SHA-256 validation passed for the delivered working-set archive and its companion input manifests. All **2,370 entries** in the original P20 source/evidence SHA-256 manifest passed. Both frozen P19/P20 candidate `--check` operations passed. All **66** retained operator nominal/stress `.state` files matched their assessment SHA-256 records. The nominal sustained assessment remains `PASS_SOAK_INPUT_GATE`: 81,285,120,000 native frames, min/max28 7/21, longest run 5, zero nonfinite states. It is **not** a production authorization.
2. A fresh native build, `make check`, 105,489 P10 unit checks, 32,859 P17 unit checks and 398 P18 native checks passed. P18's high-rate transport and format capabilities remain unavailable. No historic P15 validators were repaired or claimed to pass: the supplied working set intentionally omits 49,964 historic files and 1,351 `.npz` datasets.
3. The **unmodified** `p19_audio_compare.py` and `p20_audio_compare.py` reproduced the published residuals. All **four** emitted packed bitstreams exactly matched the archived v1/v2 SHA-256 digests, even though the newly compiled qualification executable's file digest differs from the historic executable. That distinguishes bitstream identity from executable-byte identity.
**The P19 v1 nonfinite incident is not a truncated version of this test.** The original P19/P20 audio reports, and the byte-identical fresh replays, each process the entire 1.6-second 997-Hz stimulus without a nonfinite state: 72,253,440 native frames per P19 variant and 36,126,720 per P20 variant. The roughly 33.1-million-frame P19 failure concerns a different stimulus. Both comparisons use the same fitted source interval (0.4–1.2 s); differing clock-appropriate decimation ratios are intentional. Neither figure is an opportunistically truncated pre-failure interval.

4. `tests/dsd/diagnose_residual_asymmetry.py` runs the same scalar qualification renderer and frozen FIRs. It accepts the archived int32-equivalent stimulus and a separate binary64 control, rebuilt using the *exact operation order* of `p10_corpus.stimulus()` before its int32 rounding. Rounding the control back to int32 reconstructs the original `source_i32le_sha256` exactly. Source taper, amplitude, phase, fit interval (0.4–1.2 s), decimator taps, and sample clocks are otherwise unchanged.
5. Both rates reconstruct to 176,400 PCM samples/s. DSD512 uses six halfband stages plus the mastering stage (128:1); DSD1024 uses seven halfband stages plus mastering (256:1). All cases fit out 997 Hz and DC and report sine-equivalent RMS dBFS (`20 log10(sqrt(2) * RMS)`). The spectral decomposition is a Parseval-checked rFFT of the fitted residual. No archival receipt is overwritten.

### Original, signed-32-bit-equivalent source

| Rate | v1 / eighth-order | v2 / seventh-order | v2 minus v1 |
|---|---:|---:|---:|
| DSD512 | -200.1374 dBFS | -163.0366 dBFS | +37.1008 dB |
| DSD1024 | -202.4472 dBFS | -198.7747 dBFS | +3.6725 dB |

The independently calculated *unfiltered source-rounding residual*, scaled by 0.5, is **-200.4291 dBFS sine-equivalent** over the same window. This is a diagnostic noise scale, not a mathematically absolute floor: subsequent filtering and correlations can move the measured value up or down.

### Exact prequantization binary64 control

| Rate | v1 / eighth-order | v2 / seventh-order | v2 minus v1 |
|---|---:|---:|---:|
| DSD512 | -204.0454 dBFS | -163.0581 dBFS | **+40.9873 dB** |
| DSD1024 | -238.7241 dBFS | -201.2566 dBFS | **+37.4675 dB** |

For DSD1024, treating the quantized v1 result (-202.4472 dBFS) as the source-limited contribution and the unquantized v2 result (-201.2566 dBFS) as the additional seventh-order contribution predicts **-198.8009 dBFS** by summing powers, within **0.0263 dB** of the actually observed quantized v2 (-198.7747 dBFS). This is a corroborating *approximation*; it does not presume statistically independent sources or prove the NTF analytically.

The deep -238.7 dBFS binary64 eighth-order measurement should not be used as a certified noise specification. It is also subject to finite-precision stimulus generation, fitting, and reconstruction. Its purpose is to show that the eighth-order candidate lies far below the original 32-bit source's diagnostic floor.

### Where the DSD512 v2 difference lies

With the **original int32-equivalent source**, DSD512 v2 residual energy partitions as follows:

| Reconstructed band | Residual, sine-equivalent RMS |
|---|---:|
| 0–20 kHz | -201.849 dBFS |
| 20–40 kHz | -200.411 dBFS |
| 40–60 kHz | -165.261 dBFS |
| 60–88.2 kHz | -167.011 dBFS |

The two bands from 40 kHz to the 88.2-kHz output Nyquist limit contain **99.9686% of the total residual power** in this particular reconstruction. Thus the large wideband number is primarily upper-ultrasonic content, not a 37 dB increase in 0–20 kHz residual. The corresponding original-source 0–20-kHz v1 result is -206.809 dBFS, versus -201.849 for v2 (a 4.96-dB *measured* increase there). The unquantized control also finds the ultrasonic concentration; it is not created by source quantization. This reconstruction does not measure noise above 88.2 kHz or analog-device behavior.

## Adjudication, limits, and disposition

- **Explanation accepted:** the original 37.10-vs-3.67 dB contrast is a source-precision/measurement-floor comparison artifact. A genuine and significant seventh-order residual penalty exists at both clocks under a higher-precision control. There is no evidence of an implementation defect demanding encoder surgery.
- **Design intent:** the numerical correction was selected for sustained modulator and bitstream behavior, not for a predetermined -163 dBFS figure. The value is a repeatable measurement of the current *experimental* P20 candidate. No claim that the residual is optimal or that all mastering applications should accept it is made.
- **Scope discipline:** do not tune the coefficients, widen guards, revise the one-hour soak result, alter the continuum-extrema waiver, enable DSD512/1024 writer or transport capabilities, or change the P00/P15/P17/P18 records in response to this explanation. A future independent audio/quality decision remains separate from this diagnostic question.
- **Limitations:** one shaped-noise measurement on a frozen 997-Hz synthetic tone, common in-tree reconstruction FIRs, finite-precision arithmetic and 176.4-kHz PCM output. Not an independent reconstruction oracle, native SACD playback test, spectral certification, listening evaluation, or general noise specification. No upstream Git history was supplied, so `75f8e8c3` is an input label, not an independently verified Git commit.

## Repeat without touching the frozen evidence

From the `sox_dsd` directory after the usual project build prerequisites:

```sh
autoreconf -fi && ./configure --disable-shared && make -j4
make -C test dsd_test_p10
python3 -m unittest discover -s tests/dsd -p test_residual_asymmetry.py -v
python3 tests/dsd/p19_audio_compare.py --results /tmp/p19-residual-replay.json
python3 tests/dsd/p20_audio_compare.py --results /tmp/p20-residual-replay.json
python3 tests/dsd/diagnose_residual_asymmetry.py --results /tmp/p20-residual-bands.json
python3 tests/dsd/generate_p19_candidate_certificate.py --check
python3 tests/dsd/generate_p20_candidate_certificate.py --check
```

Pass *fresh results paths* for materially different runs; the diagnostic publishes immutable JSON atomically and refuses to replace a different record. The included frozen diagnostic is `tests/dsd/results/P20_RESIDUAL_ASYMMETRY_2026-10-22/analysis.json`. The executable, NumPy/SciPy and machine math can affect extreme sub-noise-floor digits; the control's relevant ~37–41 dB pattern is the principal evidence, not byte identity of JSON floats across machines.

See the machine-readable checkpoint at `P20_RESIDUAL_ASYMMETRY_CHECKPOINT_2026-10-22.json` before continuing in another session.

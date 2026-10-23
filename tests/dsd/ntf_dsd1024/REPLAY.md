# DSD1024 NTF research — deterministic replay and resume

**R2 corrective precedence (October 23, 2026):** Read `R2_REPORT_2026-10-23.md`
and `R2_CHECKPOINT.json` first. The four R1 short screens, and historical
23-design arithmetic shortlist, are INSUFFICIENT nonlinear stability gates.
For candidate evidence use `r2_screen.py`, `verify_r2.py`, `r2_numeric.py`
and `r2_welch.py`. R1 archived receipts are preserved as historical
measurements, not candidate-advancement authority.

Read `README.md`, `R2_REPORT_2026-10-23.md`, and `R2_CHECKPOINT.json` first; R1 files are historical.
This is an independent **experimental** campaign. Replaying it does not
promote any candidate or authorize new production coefficients.

## Verify without reproducing giant packed streams

Within `sox_dsd/tests/dsd/ntf_dsd1024`:

```sh
sha256sum -c STUDY_SHA256SUMS.txt
python3 -B -m unittest -v test_study.py
python3 -B verify_evidence.py
```

Expected: checksum verification PASS, historical 12 tests PASS, and
`verify_evidence.py` certifies ONLY archival R1 integrity and fixed analysis
parameters. **Also run** `python3 -B -m unittest -v test_r2.py` and
`python3 -B verify_r2.py` to adjudicate the corrected research decision.
Neither result authorizes production promotion. A failure must not be ignored by
substituting altered receipts or adjusting test expectations.

## Replay experimental native work from the supplied source

The source archive provided by the user must unpack as `sox_dsd/` at
the original `a5e77be5d` working state. `model.py` verifies the original
source/hash identities when creating 55 designs.

```sh
cd sox_dsd/tests/dsd/ntf_dsd1024
python3 -B study.py prepare --checkout /tmp/ntf1024-only-source
python3 -B study.py instrument --checkout /tmp/ntf1024-only-source \
  --registry /tmp/ntf1024-only-registry.json
(
  cd /tmp/ntf1024-only-source
  autoreconf -fi
  ./configure --disable-shared
  make -j4
  make -C test dsd_test_p10
  ./test/dsd_test_p10 --unit
)
python3 -B study.py stimuli --directory /tmp/ntf1024-only-stimuli --stress32
```

Expected design catalogue SHA-256:
`f6ef9af08482ed3bbd7f5e88297e95ce419252dfbd56e87fdfe686f2e9400d12`.
Expected primary binary64 stimulus SHA-256:
`ca844611f9ba9f7f95428f69927e62c03806ddde21d3e43e8d5b3ab46a95701a`.
Both are checked in the executable verification code.

Generate every native screen in sequence. In a POSIX shell, within the
new study directory, the following commands produce complete independent
run/output directories (where `case_name` is not user-supplied untrusted text):

```sh
for case_name in hot-997 noise-safe dc-step silence primary; do
  python3 -B study.py render \
    --checkout /tmp/ntf1024-only-source \
    --registry /tmp/ntf1024-only-registry.json \
    --binary /tmp/ntf1024-only-source/test/dsd_test_p10 \
    --input "/tmp/ntf1024-only-stimuli/$case_name.f64le" \
    --receipts "/tmp/ntf1024-outputs/$case_name/receipts" \
    --packed "/tmp/ntf1024-outputs/$case_name/packed" \
    --jobs 4 --timeout 900
done
```

For the 55 primary spectra after all screens pass:

```sh
for packed in /tmp/ntf1024-outputs/primary/packed/*.packed; do
  key=$(basename "$packed" .packed)
  python3 -B study.py spectrum \
    --packed "$packed" \
    --receipt "/tmp/ntf1024-outputs/primary/receipts/$key.json" \
    --output "/tmp/ntf1024-outputs/spectra/$key.json"
done
```

For every finalist, render independently on `quiet-997`, `tone-20k`,
`tone-40k`, and `stress32`, with `--only clans-7 clans-8 sdm-8
sdm-8-g2p0 d512-sdm7-g3`. Run `study.py spectrum` separately for the
two tonal inputs using `--tone-hz 20000` or `--tone-hz 40000`,
`--window-start .25 --window-stop .95`. These 1.2-second tonal sources
have a 25-ms EOF taper; analyzing through 1.2 seconds causes a spurious
~189-dB fitted residual increase. The script now infers and enforces
(.25, .95) from the source SHA-256 and refuses an invalid plateau.
For `primary` the distinct correct source plateau remains (.4, 1.2).
For the four FIR sensitivity
candidates `clans-7 clans-8 sdm-8 sdm-8-g2p0`, rerun `spectrum`
with `--alternative`. The raw candidate-specific 32-second bitstreams
have 1,445,068,800 bits each; retain sufficient scratch disk space.

**Crash/re-run contract:** `study.py render` writes packed output and a
hash-bound native receipt atomically and will not silently overwrite
existing records; if a prior packed file is removed, replay is checked
against the saved bitstream SHA-256 and immutable native status (excluding
wall-clock CPU seconds). If a crash leaves a packed file without its
receipt, the tool will fail closed. Investigate before replacing anything.
Do not assume a source or binary change can reuse earlier receipts.

This helper intentionally does **not** package private builds, giant
intermediate `.packed` streams, temporary binary64 samples, or fake
holdout receipts. The evidence retains hashes, exact input frames,
native result summaries, experiment binary SHA-256, and experimental
source/header SHA-256. The bitstreams can be recreated independently.

## Recreate incumbent P19 guard with original bounds

This is a **separate** disposable checkout; never point at the ordinary
source checkout or an existing scratch path.

```sh
python3 -B requalify.py prepare --scratch /tmp/ntf1024-p19-only
python3 -B requalify.py run --scratch /tmp/ntf1024-p19-only \
  --evidence-dir /tmp/ntf1024-p19-evidence --jobs 3
```

The scratch pre-freeze sentinel is `0x1p100` per each of eight bounds.
After training and freeze, the runner explicitly recompiles and relinks
the native P10 binary before checking `verify` and the full 36 holdouts.
Rerunning a partially completed qualification first verifies the marker,
checks for a valid frozen header/proof combination, and refuses unexpected
changes. A completed validation may be replayed without deleting the
historical authority; no receipts in the packaged original are removed.

Authoritative results already included in `evidence/requalification/`:
- 17 training JSON receipts and their source-bound recreated frozen proof;
- 36 guarded holdout JSON receipts, summary and adjudication logs;
- `result.json`, with exact eight-maxima equality and original bounds match.

## Replay R2 full-scale screens, native ultrasonic power, and numeric holdouts

R2 source generation, isolated binary build and experimental registry are
the same as above. All R2 stimuli are deterministic and bound to hashes.

```sh
python3 -B r2_screen.py generate --directory /tmp/ntf1024-r2-inputs
python3 -B r2_screen.py screen --checkout /tmp/ntf1024-only-source \
  --registry /tmp/ntf1024-only-registry.json \
  --binary /tmp/ntf1024-only-source/test/dsd_test_p10 \
  --stimuli /tmp/ntf1024-r2-inputs \
  --outputs /tmp/ntf1024-r2-output --jobs 4 --timeout 900
python3 -B r2_screen.py assess \
  --manifest /tmp/ntf1024-r2-inputs/manifest.json \
  --results /tmp/ntf1024-r2-output \
  --output /tmp/ntf1024-r2-output/assessment.json
```

A failed native render is a **failing design** if its monitor identifies a
nonfinite/28-bit failure. A missing monitor or infrastructure timeout is
**not** interchangeable with a measured candidate failure. The two exact
0-dBFS P10 tones may trigger 11 native `monitor_overloads_nominal_half`
counts from source/interpolator double-roundoff (peak 0.500000000023 at
encoder scale 0.5); these are retained, and admitted only when peak is at
most 0.500000001, all other native stability conditions pass, and the
source digest matches one of the two explicit full-scale tones. No such
exception applies to near-full-scale DC, the -0.1-dBFS tone, or programme.

Do NOT run a clipped full-scale noise/programme generator as an unconditional
filter test: interpolation overshoot can produce a failure even for
CLANS-7, unrelated to the candidate. The final R2 programme source uses
a smooth, bounded, unclipped .90-peak multitone/noise stress. R2's
versioned stimulus manifest and original failed calibration trials are
retained as evidence, never substituted into original receipts.

For spectral checks, `r2_numeric.py` takes a SHA-matched replayed packed
stream and its **new** native render receipt and recomputes all reconstructed
FFT bands against the original retained R1 spectra (0.05-dB hard tolerance).
For native ultrasonic tradeoffs, `r2_welch.py` processes packed bits with
Hann 65,536-point, nonoverlapping Welch PSD over 0.4-0.8 seconds. For example:

```sh
python3 -B r2_welch.py \
  --packed /tmp/ntf1024-outputs/primary/packed/clans-7.packed \
  --receipt /tmp/ntf1024-outputs/primary/receipts/clans-7.json \
  --output /tmp/ntf1024-r2-clans7-psd.json
python3 -B r2_numeric.py --case primary --key clans-7 \
  --packed /tmp/ntf1024-outputs/primary/packed/clans-7.packed \
  --native-receipt /tmp/ntf1024-outputs/primary/receipts/clans-7.json \
  --output /tmp/ntf1024-r2-clans7-reconstruction.json
```

Do not compare the **absolute** raw native PSD dB against the distinct
sine-equivalent reconstructed residual dBFS. Compare only candidate-minus-
control differences within each method. A digital Butterworth scenario is
illustrative; it is NOT a characterized DAC, analog filter, load or
intermodulation acceptance oracle. Offline verification of receipts cannot
magically reproduce omitted raw bitstreams; regenerate and recompute them.

## Outstanding work before production selection

1. **For each new finalist**, construct an independent candidate-specific
   qualification authority and immutable training/holdout identities;
   re-use P19's process, not its CLANS-7 frozen guard.
2. Run 3,600-second uninterrupted candidate nominal training/soak at
   45,158,400 Hz and adversarial stress, record state vector maxima,
   low/high run distribution and nominal guard utilisation.
3. Candidate-specific 36/36 guarded holdouts, verify, five-tier ISA
   bit identity, provenance manifests, complete native boundary errors,
   throughput/latency/CPU resource benchmarks on supported hosts.
4. Independent real-program objective and subjective measurements, with
   fitting/removal checks at 176.4-kHz input and explicit passband goals;
   investigate any limit-cycle/idle-tone issues at sustained silence/quiet.
5. Separate independent DSD1024 read media/qualification; internally
   encoded bitstreams are never their own independent media oracle.
6. The 49,964 intentionally omitted files and 1,351 `.npz` are outside
   this source bundle. Rehydrate the complete repository before full
   P15 provenance/math campaign; do not adjust tests to hide omissions.
7. Resolve the *pre-existing*, single P20 README checksum mismatch with
   the original evidence owner. Do not alter the historical manifest
   and do not conflate this archival issue with the new NTF study.

Until these gates are satisfied, `encode.mastering.v2.dsd1024` stays
untouched and remains the incumbent/control. The existing
`CONTINUUM_EXTREMA_WAIVER_2026-10-21.md` is unchanged.

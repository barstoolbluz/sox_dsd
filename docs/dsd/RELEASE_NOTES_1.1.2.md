# SoX DSD 1.1.2 release notes

## Wider mastering passbands at DSD256, DSD512 and DSD1024

The default mastering encoder and mastering decoder use replacement FIRs and
higher intermediate PCM rates at these three DSD clocks. This **changes the
output** of ordinary PCM-to-DSD encodes and DSD-to-PCM decodes relative to
1.1.1. In particular, an ordinary DSD decode without `-r` now uses the PCM
rate in the table. An explicit `-r` still routes through the existing PCM
resampler, subject to its established `adapt` or `strict` bandwidth policy.

| DSD clock | Mastering pass | Mastering stop | Internal/default decoded PCM | Encoder FIR taps | Final decoder FIR taps | Earlier decoder halfband stages |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DSD256 | 60 kHz | 100 kHz | 352.8 kHz | 117 | 229 | 4 × 57 |
| DSD512 | 88.2 kHz | 148.2 kHz | 352.8 kHz | 81 | 153 | 5 × 57 |
| DSD1024 | 120 kHz | 200 kHz | 705.6 kHz | 117 | 229 | 5 × 57 |

The corresponding 1.1.1 profiles had a 40 kHz passband, 80 kHz stopband,
176.4 kHz internal rate and 61-tap encoder/117-tap last decoder FIRs at
all three clocks. DSD256 and DSD1024 now reuse normalized coefficients at
different working rates; there are four new binary64 coefficient banks.

The DSD64/128 mastering profiles, all five wideband decoder profiles, and the
explicit legacy encoder remain unchanged. The eighth-order SDM-8 coefficients,
rate-specific high-rate tables, runtime guards, default 0.9 encoder gain,
warn-mode 0.45 ceiling and strict-mode 0.5 envelope remain unchanged. The
canonical `encode.mastering.dsd*` and `decode.mastering.dsd*` IDs retain
those same names. No old 40/80 kHz mastering profile is selectable at the
three changed rates.

## Numerical filter verification

The coefficient generator lives at
`tests/dsd/generators/generate_112_passbands.py`. The audit reads the
**production C99 binary64 words** from the new headers, verifies their
manifest fingerprints, and evaluates the filters independently in
`tests/dsd/qualification/certify_112_passbands.py`.

The analysis checks the passband's maximum absolute error, the response at
the specified stop edge and the **worst response anywhere from that edge to
native Nyquist**. It includes the entire factor-two decoder cascade and a
coherent sum of every alias image that can fold into the promised passband.
The previous 57-tap halfband remains part of the calculation. All new banks
met the existing 0.0001 dB passband and -185 dB individual-FIR stopband
requirements. The three mastering decoder cascades met the existing -160 dB
stopband and folded-alias transfer requirements. The worst decoder-cascade
stopbands were approximately -188.66 dB (DSD256/1024) and -189.16 dB
(DSD512). The worst coherent alias sums were approximately -191.93 dB,
-186.81 dB and -191.77 dB respectively. Separate incoherent flat-power
and synthetic fourth-power-weighted alias diagnostics are also recorded;
the latter is not a measured SDM-8 noise transfer function.

See `tests/dsd/results/P112/filter-response.json` for the edge and worst-case
measurements, search intervals, and fingerprints. This is an adaptive
high-precision **numerical measurement**, not a formal interval proof. The
nonlinear modulator's shaped quantization noise is excluded from these FIR
transfer-function claims.

Actual PCM/DSF/PCM signal-path tests, including input tones above 40 kHz,
seeded broadband noise and silence spectral measurements, explicit PCM
resampling, unchanged low-rate master output and unchanged wideband decode, are recorded in `tests/dsd/results/P112/integration.json`.
Those end-to-end tests corroborate that the new paths run as intended; they
do not replace the frequency-domain FIR and SRC contracts.

## Compatibility, old certificates and historical evidence

The P10 coefficient certificate covers the **unchanged DSD64/DSD128**
mastering encoder profiles only. Encoder reports and plans deliberately do
not attach that old certificate to the changed DSD256, DSD512 or DSD1024
profiles. Decoder receipts identify the actual new final FIR bank using its
new SHA-256; a bank digest proves identity, not an audio-quality claim.
Historical qualification records and dated reports are left intact and may
refer to the earlier transfer functions.

The existing private SRC continues to use its 180 dB-rejection, 95% 0-dB
bandwidth configuration. An explicit low PCM rate cannot reproduce ultrasonic
content above its own Nyquist frequency. The planner's existing `adapt` and
`strict` semantics apply; no new interpolation or resampling policy is
introduced.

## Reproduce and review

```sh
make check
make check-dsd-cli
make check-dsd-release-112
make check-dsd-qualification-112
make check-dsd DSD_PHASE=P10
make check-dsd DSD_PHASE=P15
make check-dsd DSD_PHASE=P18
```

`make check-dsd-qualification-112` needs Python 3 with numpy, scipy and
mpmath. CPU costs relative to an unmodified 1.1.1 build are recorded in
`tests/dsd/results/P112/performance.json` with every repetition, host and
compiler configuration. Its five-repeat 0.5-second single-channel synthetic
measurement found about +8.4% median CPU for DSD1024 encoding and +10.2%
for DSD1024 decoding to a common explicit 176.4 kHz output. At DSD256/512,
encoding was essentially unchanged; some decoder paths cost 6–9% more CPU.
Default-rate decoder measurements are recorded separately because they
produce more PCM samples than 1.1.1.

The music-library corpus, extended SOAK tests, hardware playback and native
qualification on other platforms require the owner's facilities. This
release note does not treat synthetic signals as a substitute for that work.

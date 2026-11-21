# Phase 08 source-operator arithmetic proposal and independent witnesses

**2026-11-21 corrective status: PROPOSED; NOT OWNER-ADOPTED.** Signed owner
[decisions D1-D16](amendments/PHASE08_OWNER_DECISIONS_2026-11-20.md)
control acceptance. R08-D01 has additional independent *finite* tests of the
actual DSD64/128 encoder front end and decoder final SRC. The universal
same-operator P2/P3 bounds and D6's platform `pow` premise **remain OPEN**.
No implementation arithmetic, certified resonator, or frozen reference was
changed for this corrective. A finite screen is not a theorem about all
accepted streams.

## Domain and source-to-binary premises

The proposed numerical model is IEEE-754 binary64, round-to-nearest even,
gradual underflow, no FTZ/DAZ or reassociation across the examined operator,
finite intermediates, and **the exact binary64 coefficients checked in**.
Coefficient construction and FFT preparation are separately rounded, not
ideal real-number coefficient design. Accepted inputs include all stream
lengths, partial blocks, channels, lawful gain settings, output rates and
encodings that the actual route admits. A proof must identify the specific
compiler/linker/CPU/ISA, runtime libm, and the allowed arithmetic flags,
then reconcile the generated binary with the source model. The current
finite receipts do not establish those premises for every supported host.
Do not introduce a new domain restriction just to simplify proof.

## P3: unified decoder, DSD64/128, five source-pinned FIR stages

Each native bit is exactly +1 or -1. Causal zero extension outside its
finite chronological extent and source-derived group-delay removal are
part of the transfer operator. The five stages are four symmetric 57-tap
half-bands followed by the profile/rate-selected terminal bank:

| Bank | Taps L | sum(abs(exact binary64 taps)) | k=2L+4 |
| --- | ---: | ---: | ---: |
| Half-band (four stages) | 57 | 1.5062117154055743 | 118 |
| DSD64 mastering | 117 | 1.7715389138731121 | 238 |
| DSD128 mastering | 153 | 1.781758140151541 | 310 |
| DSD64/128 wideband | 257 | 2.24446877803686 | 518 |

Those values are computed from `src/dsd_coeffs.h` and the immutable
manifest checked by `unified_reference.py`, not from coefficients fitted to
output samples. In `src/dsd_kernels_scalar.c`, a generic symmetric pair is
formed from two input words, multiplied by one coefficient, then accumulated;
the central coefficient is multiplied once. For odd L this is at most
`3*(L-1)/2 + 1` scalar floating-point operations per output, aside from
indexing and any explicitly identified specialized half-band case. Scalar
and enabled SIMD accumulation orders differ, with conditional FMA and
short-tail cleanup. Taking `k=2L+4` offers more operations than that generic
pair organization, **but is still a proposal**, not proof for every enabled
kernel and denormal/intermediate path.

For `u=2^-53`, `eta=2^-1074`, `A_j=sum_i |h_j[i]|`,
`U_0=1`, `E_0=0`, and `gamma(k)=k*u/(1-k*u)`, a *candidate*,
conditional stagewise forward-error recurrence is:

```text
k_j      = 2*L_j + 4                       (requires k_j*u < 1)
U_j      = A_j * U_(j-1)
E_j      = A_j*E_(j-1) + gamma(k_j)*A_j*U_(j-1) + k_j*eta
```

It is a per-stage absolute error proposal for the FIR reconstruction versus
a real-arithmetic convolution **of the stored binary64 coefficients**. The
`k_j*eta` term is a cautious subnormal-operation allowance, but is not a
license to ignore FTZ, overflow, coefficient conversion or a different
SIMD schedule. `unified_reference.py` implements this independent causal
full convolution with extended-precision intermediates; **64 native-rate
comparisons pass** across DSD64/128, mastering/wideband, short/long lengths,
channels and scalar/auto kernels. The finite screen includes reference
rounding headroom, not an adopted universal P3 bound.

### Actual final SRC (96 kHz acceptance witness)

`src/dsd_decode.c` supplies reconstructed intermediate samples to
`src/rate.c`. It offers **ceil(N_DSD/32)** FIR output samples to the private
SRC before trimming the publicly emitted count to the nearest native PCM
frame. For a partial frame these can differ by one word. Neglecting this
word produced a detectable false mismatch in the independent reference,
now explicitly covered by two negative controls.

The unmodified source-bound P15 exporter and index oracle capture each
actual SRC stage's exact binary64 taps, phase and output length. The
independent operator is

```text
y_ideal[n] = sum_j W_src[n,j] * x_5[j]
E_output[n] <= sum_j |W_src[n,j]|*E_5[j] + B_SRC[n]
```

where the first term transports the P3 FIR error and `B_SRC[n]` must cover
actual FFT4G preparation, butterflies, multiply/accumulate rounding, phase
and end effects. The measured source-selected stage families are:

| Route | Source SRC stage families | Checked output |
| --- | --- | --- |
| DSD64, 88.2 -> 96 kHz | FFT4G interpolation (L=2; 1005 original taps; N=4096); rational polyphase (L=80, M=147) | Float64 WAV |
| DSD128, 176.4 -> 96 kHz | rational polyphase (L=160, M=147); FFT4G (L=1; 1005 original taps; N=4096) | Float64 WAV |

`final_src_reference.py` independently composes the captured source
operator at 192/256/384-bit precision and compares sampled output words
against the **real SoX final 96 kHz result**, including both profiles,
DSD64/128, scalar/auto FIRs, short streams and boundary/long partial blocks.
The **32 finite cases PASS**; two missing-tail mutants are rejected. The
record's `512*sum(log2(N))*u*product(L1)*peak` FFT4G multiplier (plus
polyphase allowance) is deliberately an **engineering screen for these
fixtures**, not a source-proved maximum. There is not yet a universal bound
for each rounded FFT butterfly or all accepted resampling ratios, output
precision conversions, channels, permitted gains and architectures. Full
same-operator P3 sign-off **remains OPEN**.

## P2: certified v3 DSD64/128 encoder input, before the resonator

The existing v1 front-end source, scalar kernels and coefficient files
(`src/pcmdsd.c`, `pcmdsd_coeffs.h`, `pcmdsd_guards.h`, `src/rate.c` and
related headers) are pinned against the **unaltered predecessor source
manifest**. It is intentionally **not** correct to require the predecessor's
all-file hash after Phase 08 changes decoder files; the focused encoder
files and historical reference hashes must remain byte-identical.

For the measured 44.1 kHz input source, the actual composition is:

```text
PCM source -> working-rate SRC -> frozen symmetric prefilter
           -> 32x working-to-native SRC -> 0.5 * headroom_gain
           -> unchanged certified v3 resonator contract -> one-bit DSD
```

The stage exporter observes the **original stored binary64 source taps**
used to prepare FFT4G bins. The source-derived stage-index oracle evaluates
those exact taps as rational coefficients at each output phase, including
causal zeros and partial tails. The working-rate SRC selects FFT4G
interpolation L=2 (DSD64) or L=4 (DSD128). The frozen centered prefilter
uses 61 or 77 original taps respectively; its scalar pair organization
requires at most `3*(L-1)/2+1` arithmetic operations per output before
rounding/extra stage bookkeeping. The 32x SRC selects two real FFT4G
stages: first L=4, 2009 original taps, N=8192; then L=8, 273 original
taps, N=1024. The actual resonator input is a **single** rounded
multiplication of the native SRC word by `0.5 * headroom_gain`, and no
post-hoc bitstream correction is an independent P2 witness.

For exact stored-coefficient operator W and incoming bounded x, a
candidate error propagation expression is:

```text
B_out[n] <= sum_i |W[n,i]|*B_in[i]
          + gamma(N_ops[n])*sum_i |W[n,i]|*(|x[i]|+B_in[i])
          + B_coeff[n] + B_phase[n] + B_other[n]
```

Here `N_ops[n]` is the *actual* source-dependent FFT4G/polyphase and FIR
operation count; `B_coeff`, `B_phase`, and `B_other` cannot be assumed zero
without proof. The 192/256/384-bit independent `reference_cascade.py` and
existing P15 test-only exporter compare eight finite working-SRC/FIR cases,
eight additional **32x native SRC** cases, and two nonzero-headroom
resonator-input scaling cases, including centered phases and edges. Four
phase/coefficient mutants are rejected. These are valid finite witnesses,
**not** a universal `N_ops`, FFT roundoff, or coefficient-construction
certificate. They neither certify the nonlinear resonator nor replace its
already adopted input envelope and bitstream certificate. Remaining work
includes WAV/FLAC decode rounding, the full stream/block/ISA domain, and
composing an accepted frontend bound with that certified input contract.
**Universal P2 remains OPEN.**

## D6: dB argument, headroom `pow`, and ordinary gain `exp`

The headroom route actually calls `pow(10., -d/20.)` (`src/pcmdsd.c` and
`src/sox_ng.c`). The ordinary `gain` effect uses
`dB_to_linear(d) = exp((d*M_LN10)*0.05)` (`src/gain.c`, `src/util.h`),
so a `pow`-only argument does **not** cover every admitted gain route.
For each operator the proposed propagation is

```text
|delta(y)| <= |g|*B_input + |x|*B_libm + u*|x*g| + B_subnormal
```

conditional on no nonfinite intermediate and on independently bounded
argument parsing, exponent arithmetic and multiplication. At 0 dB the
existing identity choices must be preserved, with an exactly representable
factor 1; `--dsd-level sacd` multiplies by 2 exactly until overflow.
`gain_libm_reference.py` calls this runtime's actual `libm pow/exp`, uses
120-decimal-digit references of the **exact binary64 argument**, and
reports 41 finite tests with observed error measured in ulps. All pass
an explicitly **sample-only 2-ulp screen**. This is not a documented bound
on `strtod`, every permitted argument, libc's `pow`/`exp` implementations,
compiler contraction or rounding-mode variants. The D6 numerical premise
**remains OPEN** pending a supported target-specific maximum and owner
adoption. It is not valid to assume correct libm rounding from finite data.

## Qualification gates and stopping rule

| Obligation | Current evidence | Disposition |
| --- | --- | --- |
| D11 P3 native FIR | 64 independent full-convolution cases | FINITE PASS; universal OPEN |
| D11 P3 96 kHz final SRC | 32 source-bound, high-precision cases; 2 tail mutants | FINITE PASS; universal OPEN |
| D11 P2 encoder front end | 8 SRC/FIR + 8 native-SRC + 2 gain cases; source pins; 4 mutants | FINITE PASS; universal OPEN |
| D6 libm | 41 runtime `pow` and `exp` sample cases | FINITE PASS; supported worst-case bound OPEN |
| D9/D10 adapters | Exact +/-1, neighbors, NaN/Inf, parity/gain/level/output checks | PASS for supported Linux test target |
| D13 predecessor | Immutable source/fixture digests and mutation rejection | PASS, do not regenerate |
| D16 unified accepted words | 19 historical **v2-only** receipts preserved | OPEN, owner selection/approval |
| D4 cross-ISA/spectral | First physical v3 measurements are report-only | OPEN |

The signed owner record is the arbiter. Do not close universal gates from
finite receipts; do not modify the certified encoder, historical fixtures,
or production DSP to paper over a qualification deficiency. Release 2.0.0
and automatic native routing remain unauthorized.

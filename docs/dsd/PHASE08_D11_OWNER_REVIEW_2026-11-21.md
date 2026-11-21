# Phase 08 D11: computed arithmetic accounting and owner decision

**Date:** 2026-11-21
**Authority:** Signed owner decisions D6, D11, D13, D15 and D16 (unaltered)
**State:** **Not accepted; D11/D6 universal proofs OPEN.** No release authorization.

## What this corrective delivers

`tests/pcm64/qualification/d11_bound_accounting.py` is a small offline
consumer of the existing Phase 08 independent qualification receipts. It
reuses P15's test-only `rate.c` snapshot exporter rather than creating
another SRC implementation. It rejects changed source hashes, changes to
captured operator snapshots, missing tests and measured errors above the
model's conditional envelope. Three independent negative controls mutate an
error, an operator digest and a runtime-libm output, and verify rejection.

It derives **exact rational** phase-wise absolute coefficient sums from
actual stored binary64 taps for 44.1 kHz to 88.2/176.4 kHz, the 61/77-tap
prefilters, the two FFT4G stages comprising 32x native interpolation, and
the final 88.2/176.4 to 96 kHz SRC. This is an upper bound on the *ideal,
real-arithmetic* FIR operator's infinity norm for all input lengths and
phases of these captured fixed-rate operators. For the five DSD64/128
reconstruction stages it computes `A_j = sum(abs(h_j))` directly from the
pinned decoder manifest. It composes stage bounds using exact rational
arithmetic until receipt display conversion.

The stages use the recurrence, for `M` the upstream ideal peak bound and `E`
its absolute error bound:

```text
A = maximum over all output phases of sum(abs(stored real FIR tap))
gamma(k) = (k * 2^-53) / (1 - k * 2^-53)
M_next = A * M
E_next = A * E + gamma(k) * A * (M + E) + k * 2^-1074
```

The IEEE-754 round-to-nearest, gradual-underflow, finite-intermediate and
source-to-binary premises are explicit. For the scalar/symmetric decoder
FIR the proposed source count is `k = 2*L+4`; for `rate_poly_fir0.h`
`k = 2*n+2`. The independent native DSD reference and stage tests already
exercise different kernels; a compiler/ISA proof must still establish the
operation-count premise for *each* named binary.

**Crucial limitation:** For FFT4G stages the receipt uses the already
published `k = 512*log2(N)` as an **engineering screen only**. Neither this
number nor a uniform bound on FFT4G trigonometric table construction,
coefficient preparation and butterfly rounding has been proven for the
source and compiled binary. The computed complete-path numbers below are
therefore **conditional estimates**, not all-input error certificates.

## Numerical result for the tested operator families

For normalized PCM source magnitude at most 1, or unit DSD input bits, the
model computes the following conservative envelope. These values are from
one named Linux/x86-64 qualification run and must be regenerated elsewhere:

| Route | Profile | Candidate absolute error upper (conditional) |
| --- | --- | ---: |
| DSD64 to 96 kHz PCM | mastering | 4.42e-11 |
| DSD64 to 96 kHz PCM | wideband | 5.83e-11 |
| DSD128 to 96 kHz PCM | mastering | 3.52e-11 |
| DSD128 to 96 kHz PCM | wideband | 4.56e-11 |
| 44.1 kHz PCM to v3 DSD64 resonator input | default 0 dB | 3.10e-11 |
| 44.1 kHz PCM to v3 DSD128 resonator input | default 0 dB | 2.92e-11 |

The reported values **do not authorize the claimed bounds**: a small sampled
error or a small screening envelope does not justify the FFT multiplier.
They also do not cover the general D11 admitted source-rate, output-format,
gain, compiler/ISA and stream-domain matrix. The actual resonator's frozen
binary64 admission check still limits the values that reach its certified
recurrence; this proof exercise does not relax that check. At 0 dB the
existing 0.5 factor is exactly representable. For nonzero headroom or ordinary
`gain`, an additional term for the `pow` or `exp` computation and exponent
formation must be composed with the pre-resonator error bound.

The harness rechecks all 41 original libm samples through **C `strtod` and
the currently loaded `libm`**, not Python parsing alone. It reports the
actual glibc, compiler, architecture, shared-library name and witness-process
rounding mode. A matching 41-case result establishes runtime continuity,
**not a maximum libm error over all admitted dB arguments**. The glibc
manual explicitly describes `pow`/`exp` accuracy as goals, not guaranteed
correct rounding; its test-suite error cutoff is not a mathematical
maximum. See [glibc, Errors in Math Functions](https://sourceware.org/glibc/manual/latest/html_node/Errors-in-Math-Functions.html).

## Verification and interpretation

After the ordinary `make check-phase08` run:

```sh
python3 tests/pcm64/qualification/d11_bound_accounting.py \
  --self-test --results /tmp/phase08-evidence
python3 tests/pcm64/qualification/d11_bound_accounting.py \
  --sox src/sox --results /tmp/phase08-evidence
```

The target now calls both commands and binds the new receipt into
`phase08-gates.json`. The first command rejects three deliberate evidence
mutations; the second recomputes coefficient/operator envelopes and checks
the independent witnesses. It cannot say `PASS_UNIVERSAL`. It returns
`PASS_CONDITIONAL_ACCOUNTING_OWNER_OPEN` or `FAIL`.

The named build's launcher, compiled executable and linked SoX core SHA-256s, source hashes, operator snapshot
hashes and runtime identity are recorded. The tool does not establish
compiler-codegen equivalence or all-input floating-point flags. A different
architecture, reordered binary or unsupported new SRC stage requires a
new qualification record, not silent reuse of this receipt.

## Owner decision requested

**D11(a) is still the governing requirement.** This implementation cannot
prove universal FFT4G and libm bounds merely by adding more test inputs.
Completing source-to-binary FFT4G/`pow`/`exp` proofs would require a separate,
substantial numerical-analysis or vendor-guarantee effort, and could still
leave architecture-specific exceptions. No algorithm change is warranted
without a demonstrated numerical defect.

Choose one explicit disposition, in a separately signed owner record:

1. **Defer** the universal FFT4G and D6 libm guarantee while keeping finite
   gates active and D11/D6 **OPEN**. The delivered computations remain
   engineering evidence only. This is the least disruptive choice.
2. **Amend D11** to name a narrower set of build targets, input classes,
   outputs and accepted conditional error assumptions. This changes the
   signed D11(a) requirement; the qualification tool must be updated to
   enforce the amended domain before claiming a bound.
3. **Commission the missing proof** with independently reviewed FFT4G,
   platform-libm and compiler/ISA guarantees, plus new cross-target
   qualification. This is separate scope and is not implied by the finite
   pass results.

**No choice has been made on the owner's behalf.** D16 reference adoption,
D4 cross-ISA qualification and release authorization are independent open
gates and are unchanged.

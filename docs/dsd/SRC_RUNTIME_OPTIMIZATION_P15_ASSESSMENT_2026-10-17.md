# P15 interaction of the production rational SRC optimization

Editorial note: The final integrated report,
`SRC_RUNTIME_OPTIMIZATION_2026-10-17.md`, includes the completed CLI corpus and
subsequent diagnostic repeats and buffer findings. Prospective testing language
in this assessment records the independent review checkpoint. The original
independent snapshot is retained with the evidence; the mathematical and P15
source-binding analysis below remains applicable.

Date: 2026-10-17. This is an independent source assessment for the current
optimization session. It describes the integer rational scheduler and paired
independent polyphase outputs now implemented in `src/rate_poly_fir0.h`. An
interleaved halfband candidate was investigated but is not retained; the
production halfband header remains unchanged. This is not a release certificate.

## Decision and scope

Both retained transformations preserve the per-output floating-point evaluation graph.
The rational scheduler can have a stronger, entirely integer equivalence proof.
The polyphase implementation evaluates independent outputs together without
changing any output's additions, multiplications, coefficients or sample
selection. Neither requires new filters, FFT algorithms, FMA, optional CPU
instructions, additional buffering, or altered decimation policy.

The intended classification is **bit-exact under the recorded strict binary64
build/execution conditions**. This is conditional on the final C code preserving
the operations described below and the compiler honoring the recorded floating
point contract. Source reasoning plus differential machine tests do not amount
to a formal proof of an arbitrary optimizing compiler.

The default preprocessor path remains the inherited implementation. The
candidate is explicit opt-in with `LSX_RATE_ORDERED_OPT=1`; the optimized branch
also requires no `__FAST_MATH__` and `FLT_EVAL_METHOD == 0`. A default-off macro preserves default execution;
it does not make a modified source file retain its old SHA-256 identity.

## 1. Exact rational scheduler

The inherited noninterpolated polyphase code in `src/rate_poly_fir0.h` calculates
`div(a, L)` once for every output, then increments integer clock `a` by `M`.
The quotient selects the first input sample and the remainder selects the phase
coefficient bank. The convolution starts at positive zero and accumulates taps
in ascending `j` order.

For admitted rational-stage states, `L > 0`, `M > 0`, and `a >= 0`. Define

    a = q L + r,       0 <= r < L
    M = s L + t,       0 <= t < L.

The next state is exactly

    c = 1 if r >= L - t, otherwise 0
    q_next = q + s + c
    r_next = r - (L - t) if c, otherwise r + t.

This is Euclidean division of `a + M`. The carry condition uses `L-t` rather than first
forming `r+t`, so the remainder update need not overflow even for a large
positive `L`. When `t=0`, the carry condition is false because `r<L` and the
remainder remains unchanged. No reciprocal approximation, floating point
phase calculation, or division-rounding change is involved.

Induction from the initial `div(a,L)` proves that each output uses the same
quotient and remainder as the inherited code. For `0 <= r < L`, the old loop
condition `a < num_in * L` is equivalent to `q < num_in`; use the latter only
if the new implementation intentionally carries the divided representation.
At loop end, consume the same `q` input frames and preserve the same `r` in the
stored clock. Therefore the subsequent call begins from an equivalent state.
There is no growing phase error: this is an identity over integers, independent
of stream duration, chunk boundaries, and cancellation in the audio signal.

The C proof also requires representable clock/quotient updates and valid FIFO
sizes. Compare only states for which the inherited C execution is defined;
do not treat signed overflow in the inherited `num_in*L` or `a+=M` as a numeric
oracle. Use wider arithmetic in the test oracle when exercising those limits.
Do not infer that `L` is globally bounded by 2048: the implementation can double
the rational phase count, and some public quality configurations use a
coefficient-memory-dependent search bound. The recurrence does not need that
bound.

If convolution text, coefficient selection, starting accumulator, and tap order
are unchanged, the audio operations are identical. The error **introduced by the
scheduler transformation** is exactly zero; that statement does not certify the
preexisting SRC's error relative to its ideal real-arithmetic transfer.

## 2. Paired independent polyphase outputs

For each rational output, the selected input index `q` and coefficient phase `r`
determine the inherited dot product:

    S[n,0] = +0.0
    T[n,j] = round(h[r,j] * x[q+j])
    S[n,j+1] = round(S[n,j] + T[n,j]).

The candidate advances the exact rational clock twice and evaluates these two
independent recurrences together. Both sums still start at positive zero, visit
ascending `j`, and use the original coefficient-first multiplication order.
It does not horizontally reduce partial sums belonging to one output. The
second output is computed only when its own quotient is inside the admitted
input span; a scalar tail handles the last unpaired output. The same induction
over `j` establishes exact output identity under strict binary64 semantics.
The final dispatch uses the original body whenever the reserved upper bound
`max_num_out` is at most two. This avoids pairing setup on tiny calls without
changing the output contract. The upper bound is not the exact output count:
the current phase may produce fewer outputs. Both dispatch branches are covered
by the exact differential tests.

The test-only recurrence comparator in `test_src_optimization.c` keeps one dot
product at a time and uses the same exact rational update. Comparison with the
paired implementation helps assess the combination, while function layout,
setup and register allocation still differ.

### Halfband investigation, not retained in production

For each output index `n`, the inherited `src/rate_half_fir.h` computes

    S[n,0] = round(x[2*n] * 0.5)
    P[n,j] = round(x[2*n-(2*j+1)] + x[2*n+(2*j+1)])
    T[n,j] = round(P[n,j] * h[j])
    S[n,j+1] = round(S[n,j] + T[n,j]).

`j` increases from zero to the last pair. Batching two or four different `n`
values may interleave these independent recurrences. It must not split one
output across accumulators and horizontally reduce them, reorder the `j`
sequence, contract a multiply/add pair, replace multiplication by another
operation without checking the rounding contract, or reverse asymmetric input
selection. A compiler can vectorize across outputs because each lane still
executes that output's original recurrence.

Induction over `j` proves bit identity when each primitive operation has the same
binary64 rounding semantics as in the reference. This is stronger than an
empirical small residual. In particular, cancellation, subnormal results and
signed zero do not invalidate the induction when both implementations execute
the same primitives in the same rounding environment. The claimed domain is
the supported audio processing domain and finite, nonoverflowing floating
point operations; no promise about NaN payload propagation or floating point
trap delivery order is needed to qualify ordinary audio processing.

An interleaved vector loop must process only complete output groups. For a width `W` group
beginning at output `n`, its greatest needed positive input offset is
`2*(n+W-1)+(2*j_max+1)`. That is exactly the last scalar output's required
window, not an extra SIMD padding entitlement. Scalar tails handle every
remaining output. Input FIFO consumption remains `2*num_out`, including odd
available-input cases inherited from the current halo contract.

### Floating point portability boundary

Record no fast math/reassociation and `-ffp-contract=off` for the compared C
translation units. Verify actual generated instructions for the measured
targets. Compiler auto-vectorization across outputs is acceptable; changing the
reduction tree within an output is not.

`FLT_EVAL_METHOD != 0`, particularly x87 excess precision, needs a conservative
fallback. More live scalar accumulators can change which values spill to
binary64 memory, and vector arithmetic can evaluate binary64 where inherited
scalar operations use extended precision. The same source expression sequence
alone cannot establish bit identity in that environment. Retain the original
loop when the strict evaluation condition is absent instead of adding an
extended-precision compatibility framework. The rational integer recurrence
alone does not share this issue if its convolution stays untouched, but the
retained paired-output candidate does. Its complete optimized branch therefore
uses the strict evaluation guard and retains the original body as fallback.

The retained candidate needs no new capability detection: portable C can run without
vectorization, and a baseline-target compiler emits only ISA permitted by its
build flags. An opt-in native-target build is a distinct measured configuration;
it must not silently broaden the deployment instruction-set requirement.

## 3. Actual P15 stage coverage

I inspected all archived stage snapshots in
`tests/dsd/results/P15_SRC_STAGE_BOUND_2026-10-16/`. The exact extracted mapping
is in `agent_dsd/affected_p15_snapshots.json`.

The modified rational family is present in the initialized stage graphs of
twelve captured nonidentity SRC pairs: each of
88.2, 176.4 and 352.8 kHz to each of 48, 96, 192 and 384 kHz. The captured
order-zero stages use `L` in {40, 80, 160}, `M=147`, and FIR lengths in
{18, 24, 26}. These are actual captured stages, not the overall SRC ratios.

The rejected halfband candidate would have affected four captured pairs: 176.4 to 44.1 kHz, and 352.8
to 44.1, 48 and 88.2 kHz. The 352.8-to-48 pair also has a rational stage.
The retained production change is therefore represented in twelve of the 24
archived nonidentity SRC stage graphs. The mapping file records only the retained rational
change; halfband rows are unchanged-path controls in the final implementation.
Halfband stages captured for P15 use 12 coefficient pairs.
The public `rate` effect also instantiates 8, 9, 10, 11 and 13 pairs; the delivered
kernel test covers all six existing instances even though P15 uses one.

DSD256 mastering v1 and v2 reconstruct to 176.4 kHz. Final output at 176.4 kHz
uses identity SRC; 352.8 kHz uses a DFT stage. These are the output rates in the
archived physical P/S-matched DSD256 comparison, and neither executes the changed
header in its native-decoder path. The DSD reconstruction code and its
previous optimizations remain untouched.

The legacy comparator's larger-ratio public SRC may execute the new optimized
code if rebuilt with the candidate option. Therefore a current comparator may
be faster even though the DSD reconstruction numerator is unchanged. Preserve
the eight archived speedups and their `PASS-SCOPED` status as historical
evidence; do not transfer the numerical speedup ratios to a changed comparator
without measuring it. A comparison to the frozen comparator remains a useful
performance continuity check when identified as such.

## 4. P15 evidence preservation and binding

| Obligation or evidence | Effect of these changes |
| --- | --- |
| Native DSD coefficients, banks, delay, stage phases, dense FIR kernels and dispatch | Unchanged. The sole production delta is in `rate_poly_fir0.h`. Existing native-filter mathematics and records retain their original scope. |
| SRC coefficient generator and exact binary64 coefficient words | Source unchanged. The completed exporter comparison found exact agreement for all 24 pairs, 43 stages, 59,854 coefficient words and 123,904 FFT-bin words, including scheduling metadata. The reviewed final-header comparison is recorded in `work-evidence/operator-identity-final-reviewed` and describes initialized graphs, not filter execution; source unchanged alone is not a substitute for recording the compared build flags. |
| Ideal multirate operator and coherent-alias route indexing | Unchanged if the scheduler induction and paired-output indexing checks hold. Existing pure mathematical inequalities are not made false by the optimization. |
| Per-output rational convolution arithmetic | Unchanged under the stated strict conditions. No additional arithmetic error term is needed for these transformations. Halfband production code is unchanged. |
| FFT4G factorization, butterflies, coefficients, DFT stage layout, overlap/save | No source change. Existing FFT arithmetic assumptions apply with the same scope; their outstanding arbitrary-input proof is still outstanding. |
| Raw source-bound captures, operator bindings and campaign receipts | New header hashes differ. Existing receipts remain valid archival evidence for their original source identity. They do not automatically become candidate receipts. |
| P15 full composite spectral coverage and release/default promotion | Still blocked by the existing independent acceptance conditions. Neither the optimization proof nor zero observed error closes those gates. |

`tests/dsd/p15_src_bound_operator.py:SOURCES` pins the changed rational header and many
other files. It also pins `test/Makefile.am`: adding a test target there changes
the source identity even when every DSP operation remains identical. The
downstream `p15_src_capture_matrix.py`, `p15_fft_coefficient_interval.py`,
`p15_full_band_campaign.py` and continuum receipt path bind the whole identity
and/or the stage snapshot/operator-binding SHA-256 values. Those checks should
continue to reject unnoticed source drift. Twelve captured stage graphs
contain the modified rational FIR function, but the shared source manifest binds
the header for every pair. The exporter initializes and describes stages; it
does not execute the FIR functions. Actual kernel and full-adapter execution are
covered by the separate differential tests and timings. Thus all captures carrying that original whole-source
identity need an explicit new binding if presented as evidence for a rebuilt
candidate; the other twelve are unchanged-path controls, not an exception to
the identity check.

The proper optimization deliverable is a new, explicit equivalence/binding
assessment with frozen baseline bytes recoverable from the source patch or a
small hashed baseline snapshot. Do not rewrite the old JSON receipts, source
pins, operator snapshots, campaign outcomes or thresholds to make a current
checkout pass their old identity check. Run archival adjudication against the
recovered frozen tree when that is the intended question.

A future reviewed source-equivalence bridge may reuse the old pure mathematical
inequalities for exactly the same coefficient words and operator. It need not
redo expensive frequency intervals solely because an equivalent integer clock
loop became faster. That is distinct from declaring the current unmodified
prover able to accept such a bridge: it currently checks raw source identity.
No certificate-tool redesign is necessary for this production optimization.
New candidate captures and differential results plus the explicit proof and
recorded limitation are sufficient to make the improvement reviewable.

## 5. Delivered test and measured evidence

`tests/dsd/test_src_optimization.c` includes the real production `rate.c` and
instantiates exact archived original headers as independent reference functions.
The references retain the original license text and source SHA-256 values in
`tests/dsd/reference/src_optimization/ORIGIN.json`. No epsilon comparison is used.
The added test is not a replacement rate implementation or a benchmark of a
separately reconstructed floating point kernel.

The direct matrix covers every existing `h8` through `h13` halfband as an
unchanged-path control, variable polyphase lengths 1, 2, 3, 11, 18, 24, 26, 42,
63 and 88, and fixed `u100_0`/`U100_0` instantiations. It covers rational phases
through 4096, the actual P15 stage ratios, initial phases zero/mid/last, no-output
and odd tails, offset and exact-span FIFOs, signed zeros, near-full-scale and
cancellation values, small normals/subnormals and deterministic signed finite
values. Four rounding modes are exercised. A closed-form wide-integer clock
oracle independently verifies output counts, consumption and stored phase.

There are also 288 streamed kernel cases comparing whole and irregular chunks,
and 50 complete private binary64-adapter cases over ten rate pairs and lengths
zero through 4099. The latter compare statuses, input/output counts, binary64
sample words, finite EOF behavior and retained processing state between actual
initialized production stages and identical stages using the archived kernels.
They run with nearest rounding; the isolated kernel tests cover all four modes.
The direct, streaming and API suites perform 768,060 checks and compare 5,409,850
binary64 sample words in each successful configuration.

Final-header runs passed at GCC O2 and O3 with the option enabled, and at O2
with x87 excess precision where the guard correctly selected the original
fallback. `agent_dsd/correctness-final/results.json` binds those results to final
header SHA-256
`c1626c26f7ba8d64f2b69752906948b527923745313d13c41f78c47046552591`.
The original default-path configuration passed separately. The pre-final `>1`
version also passed address/undefined-behavior sanitizers on the test translation
unit and included `rate.c`; its separate linked archive was not instrumented.
LeakSanitizer alone could not inspect `/proc` in this environment, so that
failure and the successful `detect_leaks=0` follow-up are both retained in
`agent_dsd/correctness/`. The parent task additionally completed a fully
instrumented sanitizer build and carries its independent evidence. The final
threshold changes only which already-compared body executes for tiny calls.

The test compiles against a configured static build with, for example:

```sh
cc -O2 -g -ffp-contract=off -DLSX_RATE_ORDERED_OPT=1 \
  -I "$SOX_BUILD_ROOT/src" -I "$SOX_SOURCE_ROOT/src" \
  "$SOX_SOURCE_ROOT/tests/dsd/test_src_optimization.c" \
  "$SOX_BUILD_ROOT/libsox_ng.a" -lm -o test_src_optimization
./test_src_optimization
./test_src_optimization --benchmark
```

The library pathname above is the standalone-build layout used in this session;
an Autotools build may place the archive under its `src/.libs` directory. Use
the actual configured archive and include directory, and retain its build flags.
`-O3` is an independently tested variant, not an instruction to enable fast math.
The x87 check uses `-mfpmath=387 -fexcess-precision=standard`, verifies
`FLT_EVAL_METHOD == 2` and confirms that the guarded fallback is selected.

The benchmark mode has original, recurrence-only and paired production functions
inside the same executable, with actual production FIFO structures. It allocates
and warms the buffers outside the timed stage loop; preserves exact clock state
between calls; checks equal output counts, checksums and final phases; randomizes
three-arm order; and records two warmups plus fifteen measurements. It reports
process CPU and monotonic wall time. Its setup fields cover the test's fixture
and FIFO setup, not filter coefficient design or application startup. This
measurement reduces unrelated whole-executable layout confounds. Function
layout and setup still differ, and it does not measure complete audio-decoder
throughput.

The primary final-source result is
`agent_dsd/real-fifo-final/summary.json`, with raw rows and metadata beside it.
The executable includes final header SHA-256 `c1626c26...52591`; its own SHA-256
is `fd1095d818517b00c4ad1eadb61a56005cbab2bb683623bb5869bbb411f2debe`.
The run completed all 765 expected rows (15 cases, 17 rounds, three arms) in
22.28 seconds. Every measured round retained equal output count, checksum and
final phase between variants. The correctness suite separately compares every
sample word, rather than relying on the timing checksum.

For sustained 4096-input blocks, paired median CPU ratios of original time to
ordered time range from 1.42 to 1.92. Pairing also improves on the recurrence-only
arm by 1.30 to 1.79 across those cases. Representative results are:

| FIR taps | L/M | Original / ordered CPU time | Descriptive paired bootstrap interval | Recurrence-only / ordered |
| --- | --- | ---: | --- | ---: |
| 11 | 80/147 | 1.922 | 1.791–2.047 | 1.519 |
| 18 | 40/147 | 1.472 | 1.282–1.702 | 1.303 |
| 24 | 160/147 | 1.787 | 1.686–1.872 | 1.562 |
| 26 | 80/147 | 1.635 | 1.492–1.703 | 1.562 |
| 26 | 160/147 | 1.672 | 1.594–1.711 | 1.533 |
| 88 | 80/147 | 1.822 | 1.722–2.032 | 1.652 |

The final binary still has a small-call cost. With 26 taps and L/M=80/147,
one-input calls take median 33.49 ns versus 29.04 ns original; two-input calls
take 36.42 ns versus 31.51 ns original. These are increases of roughly 4.4–4.9 ns
or 15–16 percent of the original tiny-stage time. Empty calls are neutral, and
8/32/128-input calls show paired speedup medians 1.47/1.52/1.50. The optimization
therefore does not improve every block size. Full-CLI small-buffer evidence is
needed to assess the practical impact after adapter and application overhead;
the standalone nanosecond cost must not be hidden by a sustained-throughput claim.

The preceding `>1` three-arm run is retained in
`agent_dsd/real_fifo_O2_summary.json`. A temporary same-executable `>1` versus
`>2` comparison is in `agent_dsd/threshold/summary.json`. In that comparison,
`>2` avoided setup overhead for the problematic two-input 26-tap case and
retained sustained gains; it also forfeited useful 88-tap pairing on tiny
blocks. The conservative policy was chosen explicitly. Its temporary `>2`
instantiation measured nearer original cost than the final production function,
which reinforces that dispatch and function layout affect very short calls.
The temporary file retains 861 of 867 expected rows despite a reported zero
exit: its final seventeenth case has thirteen measured rounds; the first sixteen
have fifteen. Metadata explicitly preserves this anomaly, and that incomplete
case was not used for the threshold decision. The final primary run is complete.
Use the final binary's measured costs above for current behavior, not the
more favorable temporary result. No further source threshold was selected from
those fluctuations.

These measurements were taken with GCC 13.3, `-O2 -g -ffp-contract=off`, CPU3
affinity, on the session's virtual AMD EPYC host. Their bootstrap intervals
summarize repeat variation on that run. They do not make the host a prepared
physical qualification system. Actual full-CLI timing and RSS evidence are kept
separately by the parent task. Old physical P15 speedup receipts remain archived.

## Frozen implementation identities inspected here

| File | SHA-256 |
| --- | --- |
| `src/dsd_decode.c` | `7194387ab5906a1f8cfcaef98a46922a12dd680d2420febc5dd7e993f70bfad7` |
| `src/dsd_public.c` | `26b22da56992da1c3cf6151e309dac759235199449b1c2336476766600d8c8be` |
| `src/dsd_kernels_scalar.c` | `9661303075f0965c0e319ed94c5037da72963aebf4499ba3206b3e8dd3344c26` |
| `src/dsd.c` | `376427406ba7f1e96463b82d308651d548ba4121bf4ad6a04148a415980aff5c` |
| `src/dsd_dispatch.c` | `f4fb56e640171600458dfff8b344b17b7cb254455db01fe78a6678cad7409d81` |
| `src/dsd_coeffs.h` | `853c3e4c1902124513d99706a40a08c9b33363f7e18810ec41a955ab0b598d17` |
| `src/dsd_coeffs_v2.h` | `a356b080cf7d90403bbcc684c4df047c1f190212f7156d0a6fcfed6fcbf9884c` |
| `src/rate.c` | `aefcbff631e391531e00dabcdf7a1d328fa110baa7379a33dc6cb2465eeaafa6` |
| `src/fft4g.c` | `fc547db7fc3d0938c53357f98c16ec8a1b999c8d94352faa6ea1547df084e39b` |

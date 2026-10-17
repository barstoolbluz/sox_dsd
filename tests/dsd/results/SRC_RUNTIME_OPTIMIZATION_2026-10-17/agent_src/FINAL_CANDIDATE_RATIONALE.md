# Final production SRC candidate — rationale and independent review

Date: 2026-10-17. This is an implementation/review checkpoint, not a P15 release certificate.

## Exact change and activation

Only `src/rate_poly_fir0.h` changes production code. Final SHA-256:

`c1626c26f7ba8d64f2b69752906948b527923745313d13c41f78c47046552591`

The header instantiates the existing `vpoly0`, `U100_0`, and `u100_0` rational, non-interpolated FIR functions. The candidate combines exact integer phase recurrence with two independent output accumulators. It adds no persistent state, allocation, dependency, coefficient preparation, phase table, FFT change, ISA dispatch, or CLI option.

The ordinary build keeps the original implementation. The candidate requires `LSX_RATE_ORDERED_OPT=1`, absence of `__FAST_MATH__`, and a defined `FLT_EVAL_METHOD` equal to zero. Unknown/excess intermediate precision falls back to the original. Qualification builds must also use `-ffp-contract=off`; the preprocessor cannot portably identify the compiler's contraction setting. A once-per-call `max_num_out > 2` condition leaves calls whose output capacity bound is at most two on the original implementation. There is no dispatch inside a dot product.

I independently removed the candidate preprocessor block and the new standard-header include from the final text, normalized the resulting blank line, and obtained the frozen original header byte-for-byte. The preserved reference is `tests/dsd/reference/src_optimization/rate_poly_fir0.h`.

## Integer scheduling proof

For a production rational stage, let the original nonnegative integer clock be A, positive phase count L, and positive clock increment M. Write A=qL+r and M=uL+v, where 0≤r,v<L. Initially these are precisely the quotient/remainder returned by C `div`, because its numerator is nonnegative.

Define carry c=(r≥L−v), then update:

- q′=q+u+c
- r′=r+v−cL

If r<L−v, c=0 and 0≤r′<L. Otherwise c=1 and 0≤r′<L. In either case q′L+r′=A+M. Induction therefore gives exactly the original input index q and coefficient phase r for every output.

The actual C expression uses `r += v - c*L`, not an intermediate `r += v`. For every positive representable int L: L−v is in [1,L]; cL fits int; v−cL is in [−L,L−1]; the final remainder is in [0,L−1]. Thus no overflowing r+v intermediate is required, even when L is large. Also u+c≤ceil(M/L)≤M, so that increment fits int. The accumulated quotient is bounded when the corresponding original A+M has defined representable-int behavior. This is an equivalence claim over the original implementation's defined domain, not a claim that its pre-existing clock/length overflow cases were certified.

The loop test q<num_in is equivalent to A<num_in*L for positive L and nonnegative A where the original multiplication is defined. The candidate avoids that multiplication. Before forming the second output's pointers it advances a copy of the state and tests its quotient. Therefore it never reads a second convolution beyond the original admissible input window. When that check fails, exactly one output remains; the scalar tail advances to the same final quotient/remainder. Both paths consume that quotient from the input FIFO and retain the same remainder for the next call. The unused fraction field is untouched as in the original.

## Floating-point operation graph

For each output k, the original evaluates a left-to-right dot product beginning at +0. The candidate assigns that complete dot product to one accumulator and visits j in the same increasing order. Each coefficient address is algebraically identical to the original `coef(...,0,...,phase,0,j)` address. Products and additions retain their original grouping; no partial sums, horizontal reduction reassociation, interpolation, or coefficient change is introduced.

Under the stated build conditions and the same ordinary floating-point environment, each corresponding rounded operation has identical operands. Induction over j gives the identical accumulator bit pattern, including cancellation and signed-zero behavior for finite legal audio inputs. The order of independent outputs changes, which is safe because `rate_process` supplies distinct adjacent-stage FIFO objects and their storage does not overlap. The inspected GCC output maps packed-add lanes to separate output samples; each lane retains the original serial accumulation. This establishes category 1 relative to the frozen implementation under those conditions. It does not establish the frozen implementation's absolute arithmetic error against an ideal filter, nor close P15's outstanding FFT/composite spectral obligations.

## Measurements and selection

### Exploratory screens

These are preliminary source-header, same-executable kernel screens using synthetic double coefficient/sample banks, pinned to CPU 2, with alternating baseline/candidate order. The container reports an AMD EPYC 9V74 and a hypervisor flag; these are not qualified physical-host measurements. They are not substitutes for final source-bound production CLI/FIFO receipts. Raw files are in `agent_src`.

| Rational FIR length, L=80/M=147 | -O2 median speedup | -O3 median speedup |
|---|---:|---:|
| 11 taps | 1.829× | 1.362× |
| 22 taps | 1.608× | 1.521× |
| 44 taps | 1.721× | 1.672× |
| 88 taps | 1.765× | 1.804× |

Each column used five pairs with `-ffp-contract=off`. The smallest observed ratios were approximately 1.47× with -O2 and 1.22× with -O3. These measurements concern the paired prototype before the final tiny-call guard and lexical cleanup; final evidence must identify the final source hash separately. Initial and polished exact-output/count/phase screens each passed 36,652 cases, comparing binary64 samples before quantization. The test inventory included FIR length, phase, input length, and rational-ratio variation. Full production-structure/FIFO, compiler, adversarial, and streaming validation is the independent test agent's responsibility.

The short-call screen found the extra setup matters in nanosecond-sized calls. Before the threshold, an empty call cost about 8.3 ns versus 5.8 ns and an 11-tap single-output call about 17.1 ns versus 14.8 ns. The initial `> 1` threshold removed the second division in empty/strict single-output-bound calls. A retest still observed roughly 1–3 ns of extra function/setup overhead on empty or one-output calls. Under that initial threshold, two-output calls were approximately neutral at 11 taps and 1.28–1.54× faster at 44/88 taps in the guarded screen. An independent actual-FIFO screen subsequently measured a 26-tap L=80/M=147 two-input case at about 0.948× speedup (roughly 1–2 ns extra per call), while sustained cases improved 1.33–1.77×.

A temporary same-executable comparison in `agent_dsd/threshold` showed approximately neutral small-call performance with `> 2` and motivated the conservative final capacity-bound threshold. It deliberately forgoes some large-FIR gains in tiny calls. That temporary result does not establish the latency of the final compiled function: returning to the original sample loop does not restore the original function layout or setup. The dispatch remains one call-level comparison, with no additional runtime state or machinery. The final source-bound measurements below supersede the temporary threshold experiment and all earlier stub-FIFO screens.

### Final source-bound real-FIFO measurements

`agent_dsd/real-fifo-final/summary.json` and its `metadata.json` bind the real production `rate.c`/FIFO stage benchmark to the final header hash shown above and executable SHA-256 `fd1095d818517b00c4ad1eadb61a56005cbab2bb683623bb5869bbb411f2debe`. This is an `-O2` same-executable comparison of the original, recurrence-only, and final guarded paired implementations, pinned to CPU 3. There are 17 repeated rounds per case. The benchmark uses fixed input windows in the production stage and FIFO structures; it does not measure complete CLI conversions or establish a prepared-physical-host performance result.

For sustained 4,096-input windows, the paired median speedups range from **1.42× to 1.92×** over the tested 11–88-tap cases. The P15-relevant 18-, 24-, and 26-tap cells are:

| FIR length | L / M | Paired median speedup | Bootstrap 95% interval |
|---|---|---:|---:|
| 18 taps | 40 / 147 | 1.472× | 1.282–1.702× |
| 24 taps | 160 / 147 | 1.787× | 1.686–1.872× |
| 26 taps | 80 / 147 | 1.635× | 1.492–1.703× |
| 26 taps | 160 / 147 | 1.672× | 1.594–1.711× |

The final executable retains a measurable tiny-call regression despite the `> 2` guard. For 26 taps and L=80/M=147:

| Input window | Original median time per call | Final median time per call | Change in median time |
|---|---:|---:|---:|
| 0 inputs | 13.702 ns | 13.730 ns | +0.2% |
| 1 input | 29.044 ns | 33.491 ns | **+15.3%** |
| 2 inputs | 31.510 ns | 36.416 ns | **+15.6%** |

The paired median speedups for one and two inputs are 0.861× and 0.861×, with bootstrap intervals 0.841–0.884× and 0.842–0.889×. These paired statistics differ slightly from reciprocals of the independently computed median times. The empty-call interval includes parity. The extra one/two-input latency is about 4.45/4.91 ns per stage call, rather than the 1–2 ns or roughly 2–3% residual in earlier experimental layouts. The final function's setup/layout overhead remains even when the unchanged scalar sample loop is selected; the threshold must not be described as eliminating the final binary's tiny-call regression. The complete CLI small-buffer corpus must determine whether these stage-level costs materially affect production conversions. No further source change is proposed on the strength of this result alone.

### Rejected alternatives

- Integer recurrence alone preserves the arithmetic but showed smaller, less consistent isolated benefits. It remains a component of pairing, avoiding an external `div` call and associated register spills per output.
- Half-band batching had mixed compiler/tap results. More importantly, `work-evidence/screen-independent/measurements.json` records about 1.167× speedup for the half4 binary on 44.1→48 kHz very-high quality, a route whose stage topology has no half-band stage. This is a negative control against attributing whole-binary gains to the new half-band arithmetic. Together with mixed isolated gains it argues for excluding that additional production delta.
- Retaining drained FIFO allocation is logically defensible if explicit clear/delete semantics remain unchanged, but changes all FIFO-using effects and retains historical capacities. Its CLI confidence intervals overlap 1.0 and show no meaningful consistent benefit; it is excluded.
- FFT4G or changed FIR reductions would create materially greater numerical/source-binding obligations. The paired rational path already realizes a strong measured kernel improvement while preserving operation order.

## Final patch review

No demonstrated implementation defect or excessive scope was found. I checked macro cleanup across repeated header instantiation, untouched scalar fallback, zero/odd-output behavior, coefficient/input bounds before the second output, FIFO phase/consumption state, recurrence intermediate ranges, and the strict floating-point assumptions. No existing coefficient, half-band header, interpolated polyphase header, FFT source, FIFO source, or P15 Python prover is changed by this candidate.

The source hash changes even though the default executes the original code. Existing source-bound receipts must not be relabeled as evidence for the opt-in build. The reverse patch/reference header preserve the baseline. P15 remains blocked independently; adoption requires the documented source/build rebinding and acceptance evidence, with final full-CLI and actual-FIFO measurements taking precedence over exploratory screens.

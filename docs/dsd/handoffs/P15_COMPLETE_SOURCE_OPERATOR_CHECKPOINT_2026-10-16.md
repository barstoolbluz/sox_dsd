# P15 source-bound native-FIR + private-SRC operator — checkpoint

**Date:** 2026-10-16 (America/New_York)  
**Input:** `sox_ng-P15-adjudicated-2026-10-16-FULL_REPO.tar.gz`  
**Authority:** `docs/dsd/DSD_DESIGN.md` §8.6.1 and the original P15 acceptance amendment.  
**Disposition:** `SOURCE_BOUND_UNCERTIFIED`; P15 release **BLOCKED**; mastering-v2 **OFF by default**.

## Implemented, with reviewed scope

1. Test-only `test_p15_src_stage_export.c` includes the actual unmodified `src/rate.c` in a separate translation unit, using the same `rate_init` settings as `lsx_rate_f64_create` (`-180 dB`, 95%-0dB, 50% linear phase). It records all active stage kinds, realized binary64 coefficient words and phase/clock state. Its single interposition on `lsx_design_lpf` preserves *pre-FFT4G* LPF taps before `rate.c` destroys them, **without changing production DSP**. It records the actual packed FFT4G words too. The independent Python reconstruction cross-checks FFT packing via NumPy; this is *not* a source-independent design proof of the Kaiser LPF or an FFT4G forward-error bound.
2. `p15_src_bound_operator.py` independently reindexes DFT/overlap, halfband and rational zero-interpolation-order polyphase stages, without magnitude-based truncation. Every currently active P15 rational stage is order 0. It represents the source-captured **ideal convolution cascade of binary64 design taps**. The execution-stage packed FFT4G coefficient multiplication and rounding are a separate, still-open arithmetic obligation.
3. The **stage-true phase period** is the reduced U/V period multiplied by the least integer needed for every intermediate stage's clock translation to become integral. The 352800→48000 route needs 40/294 rather than 20/147 because of its initial halfband stage. The infinite-periodic operator is used for spectral transfer. For finite streams, each separate stage is primed by numeric zero, not by hypothetical negative-time anticausal outputs from upstream. This distinction was initially missed, and was corrected after first-frame production residuals exposed it.
4. `p15_src_full_chain.py` composes source-verified native FIR banks, using the established 75-digit P06/R3 exact binary64 reference, with the captured SRC coefficient/phase operator and the real finite native bitstream. The native phase is `h[delay + m*D - native_index]` and full native/input to PCM/output translation is `(D*V, U)`. No fake PCM input is passed as one-bit audio.
5. `p15_src_complete_aliases.py` enumerates **every** signed original/native input harmonic in `[-Fn/2,Fn/2)` for an output frequency `f`, with spacing `Fout/U` and one representative per family, retaining the SRC phase residue `s mod V`. It derives the complete ideal SRC's `V` phase-modulated Fourier coefficients from the source-derived rows, multiplies each by the independently pinned native bank response, and sums the *absolute values* of unwanted contributors coherently. Sampled evaluations are diagnostic and cannot imply a continuum certificate.
6. `p15_src_capture_matrix.py` binds both frozen worklists, validates **72 SRC-active cells and 24 rate-pair realizations**, checks all individual phase identities, and fully enumerates 214,432 native alias family instances at the 1-kHz diagnostic frequency (no pruning). Per-pair atomically published, source/binary/hash-bound snapshots can be reapplied idempotently but cannot be replaced under conflicting source identities.

## Measurements and gates run

- **13 new focused tests: PASS**, including malformed fixed-point clocks, changed FFT coefficient, changed coefficient words, wrong rational schedule, source-hash replay refusal, phase parity, 75-digit finite full-chain composition, actual endpoint and midstream one-bit native input production export (master64→48 kHz, wide256→48 kHz, mastering-v2-256→48 kHz), and coherent alias population. These are engineering conformance checks, **not** official P15 arithmetic/spectral pass thresholds.
- Independently acquired **72 production private-SRC impulse probes**: first, interior and final source impulses for **all 24 pairs**. A separate SHA-bound `PRODUCTION_CROSSCHECK.json` preserves every production output digest and selected independent sample-index comparisons. Maximum observed absolute disagreement: **1.2731e-13**. This tiny measured value is not a proven FFT4G bound.
- Three real native DSD→PCM decoder exports, including first/middle/last output frames. Max observed absolute differences from the independent native reference followed by the independently indexed ideal private SRC were approximately `1.54e-11`, `5.6e-16`, `6.7e-16`; compare by profile in the tests. This is evidence of correct finite-stage indexing, not acceptance under §8.6.1.
- Matrix `SUMMARY.json`: `status=SOURCE_BOUND_UNCERTIFIED`, `release=BLOCKED`, `qualified=false`. Full current-tree P00 SHA inventory updated only for changed test build manifest and newly appended source/receipt/document files; historical frozen entries and **946 intentionally omitted NPZ hashes** retained byte-for-byte. 
- No production C DSP sources, normative envelope, source-locked historical measurement results, archived Intel scope label or dispatch defaults were changed.

## Mathematical definitions (two different operators)

`r_i` denotes input-to-output rate ratio of stage i. Reduced overall period is U0/V0. Define `d_i = V0 * product_(k<=i) r_k`, as an exact rational. Then `m = lcm_i denominator(d_i)`, `U = m*U0`, `V = m*V0`. A valid phase shift satisfies `W[n+U,j+V] = W[n,j]` *for the infinite stationary operator*. For the finite operator, every negative intermediate stage index is zero, and finite input indices are zero outside `0..N-1`.

At an output frequency `f`, enumerate every integer `s` satisfying `-Fn/2 <= f + s*Fout/U < Fn/2`. Its SRC residue is `s mod V`. For each residue, derive the *stationary* harmonic coefficient

```
C_s(f) = (1/U) sum(n=0..U-1) sum(j in source-bound W[n,*])
             W[n,j] exp(2 pi i (f+s*Fout/U) j / R)
                    exp(-2 pi i f n / Fout)
```

The native FIR product at `f_s = f+s*Fout/U` is `H_native(f_s)` from the manifest-pinned centered native bank cascade. The sampled, maximally coherent *unwanted amplitude* diagnostic is `sum_{s != 0} |H_native(f_s) * C_(s mod V)(f)|`. This is not power/RMS summation and does not drop low-level aliases. The sum's ordinary binary64 calculation is **not** an outward-rounded continuum bound.

## Commands on a clean unpacked tree

```
autoreconf -fi
./configure --disable-shared --without-magic --without-alsa --without-oss \
  --without-pulseaudio --without-ladspa --without-id3tag --without-mad \
  --without-lame --without-vorbis --without-flac
make -j6
make -C test dsd_test_p15_src_stage_export dsd_test_p07_reference
python tests/dsd/p15_src_capture_matrix.py      # only verification; no binary needed
PYTHONPATH=tests/dsd python -m unittest -v \
  tests/dsd/test_p15_src_bound_operator.py \
  tests/dsd/test_p15_src_complete_aliases.py
```

To acquire receipts from source for the **first** time in a different destination, pass `--exporter test/dsd_test_p15_src_stage_export --output <fresh_directory>`; the existing source-bound captures refuse rewrites. The test-only build target uses the existing compiled SoX library, not a new production symbol.

## Explicitly NOT complete (do not falsely label PASS)

1. **FFT4G and stage arithmetic:** no independently proven `N_ops`, `B_coeff`, `B_other`, butterfly-roundoff, interpolation or stage overlap numerical envelope. The 75-digit coefficient model is the ideal stage graph from captured binary64 taps, not a mathematical certificate of rounded binary64 FFT execution.
2. **Generation provenance:** C LPF design output is source-inlined *observed realization* verified against the packed FFT; a separately proven independent reproduction of the source's Kaiser coefficient generator is not supplied. This is correctly recorded as source-bound rather than source-independent design proof.
3. **Full continuous-frequency extrema:** the existing interval checker can bound a supplied finite trig polynomial. A full instrument to reduce this source-derived multirate/native frequency product to directed-rounded continuous pass, stop and all coherently folded alias extrema—within reasonable resource budgets—is still needed. The 214,432 enumerated *instances at one frequency* do not prove any continuum envelope.
4. **R5 prerequisite and raw evidence:** the original R5 arithmetic-checker sources (`p15_src_same_transfer_checker.py` and four imports) were absent from the supplied snapshot. The 946 omitted `.npz` payloads remain absent; no missing data were fabricated. The historical closeout-review test has two failures and one error from a previously stale source hash.
5. The DSD256 66-kHz bandwidth-match comparator remains OPEN independently; AVX-512 evidence remains measured/scoped. Both P15 substantive release gates are OPEN. No defaults or production code modifications are authorized here.

## Continuation / reproducibility

Start from this source archive, verify the P00 inventory and SHA256SUMS, run the 13 focused tests, verify `SUMMARY.json` against its receipts with `p15_src_capture_matrix.py`, then implement coefficient-accurate FFT4G forward-error bounds and directed-rounded source-bound continuous extrema using the full alias lattice. Do **not** substitute the matching-but-uncertified small observed residuals for §8.6.1's arithmetic bound. Once the missing R5 source and raw arrays are obtained and verified, replay the complete 72-cell raw acceptance instrument. Preserve the present findings and original historical results.

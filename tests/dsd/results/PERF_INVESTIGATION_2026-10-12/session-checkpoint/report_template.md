# Decode performance and SDM default: investigation and decision record

Date: 2026-10-12. Input tree: `d2bd98df`, supplied as a git archive without `.git`.
Input archive SHA-256: `4d0bcd399914f2433563e9ab7a236f7916c42dd613a466d4c04a1ac91c168120`.
Authority: `docs/dsd/DSD_DESIGN.md`. This is an investigation, not P15 or another implementation phase.

## 1. Decision

**Further decode optimization is worth a bounded attempt, but additional dense-FIR ISA widening is the wrong first target.** The actual reconstruction path performs many scalar half-band FIR calls and substantial per-native-frame control work. The supplied dense microbenchmark is not the workload that dominates that path. The flat forced-tier decode timings cannot establish that FIR work is insignificant, complete, or incapable of yielding a useful end-to-end improvement.

**The reported encode benefit justifies evaluating a qualified SIMD SDM default. It does not authorize changing that default today.** Treat this as an execution-tier certification delta against the retained scalar P10 reference, not a new coefficient design or a wholesale repetition of accepted work. SSE2 is the first conservative candidate: it supplies essentially all of the reported physical-host benefit. AVX2 is a possible measured host-specific preference, not a universal preference inferred from register width. P15 remains responsible for activation under the existing authority.

**No production source, coefficient, guard, public ABI, dispatch default, certificate or governing design was changed.** The delivery adds measurement capabilities, tests and this evidence-backed decision record. Historical receipts and reports remain unedited, including interpretations corrected here.

## 2. What real decode executes

### 2.1 The dense benchmark does not represent the dominant FIR work

`src/dsd.c` selects a five-stage factor-32 mastering frontend for DSD64. `src/dsd_decode.c` constructs four 57-tap half-band stages followed by one 117-tap dense terminal stage. For a long stream, per channel and per final frontend output, the first four stages produce **16 + 8 + 4 + 2 = 30 half-band outputs**, followed by one dense output. Startup, phase alignment and tail flushing affect finite-stream edge counts; the 30:1 statement is the steady-state ratio, not an exact short-file count.

The generated `feed_*`/`accept_frame_*` paths in `src/dsd_decode.c` call the selected **single-output** direct FIR. They do not call `fir_block`. Every SIMD direct FIR in `src/dsd_kernels_sse2.c`, `dsd_kernels_avx1.c`, `dsd_kernels_avx2.c` and `dsd_kernels_avx512.c` immediately calls `lsx_dsd_fir_scalar` when `halfband` is true. Thus a report saying `fir_kernel_actual: avx512` correctly identifies the selected descriptor, but does not mean every FIR invocation uses AVX-512 instructions. It also does not claim that the block implementation is connected to the graph.

The supplied `test_p11.c --bench` measured a synthetic **dense 153-tap, stride-one** bank. Both its `fir-single` and `fir-block` headlines exclude the half-band shape; its block case is not an integrated decoder path. Real factor-two blocks also have a different stride from the original benchmark. These distinctions invalidate substituting 4.21x into Amdahl's law as a speedup of all reconstruction FIR work.

The new benchmark modes preserve the old default workloads and add the actual 57/117/153/257-tap coefficient banks, explicit sparsity and stride-two single/block cases. They report the bank, taps, stride and output unit in every raw row. Production-bank does not mean full-decoder: these are still contiguous-window kernel measurements with setup, streaming rings and graph bookkeeping outside their timer.

@KERNEL_TABLE@

The equal half-band single-output timings are explained by the common scalar implementation. Faster half-band block primitives show an opportunity worth investigating, **not a measured integrated speedup**. Batching has history, phase, latency, bounded-storage and error-prefix costs that must be included before adopting it. A specialized half-band single-output path may be the smaller experiment.

### 2.2 There is also hot work outside the arithmetic kernels

`sox_dsd_decoder_process()` in `src/dsd_public.c` calls reconstruction with `consumed = 1` and `produced = 1` for each native DSD frame. It increments the native frame count and calls `lsx_dsd_count_convert()` on every such iteration, including frames that produce no final output. `src/dsd.c` implements exact, overflow-checked rounding through quotient/remainder arithmetic and several runtime integer divisions.

This is correct bookkeeping, not a demonstrated correctness defect. Its current invocation frequency is an optimization candidate. Any replacement must preserve exact rounding at all supported rate ratios, overflow behavior, partial consumption, backpressure, tail counts and sticky errors. Replacing it with floating-point estimation or weakening checked behavior would not be an acceptable optimization.

### 2.3 Measured attribution, not another guessed mechanism

The current environment is an AMD EPYC 9V74 presented by KVM, pinned to CPU 1. It is **not the supplied physical Threadripper**. We built the actual CLI and library with `-O2 -g`, then an optional executable whose link command alone adds `-pg`. Ordinary compilation does not add `-pg`, avoiding per-function `mcount` instrumentation on this exceptionally call-heavy path. GNU gprof explicitly supports viewing these samples with `-Q` when call-graph instrumentation is absent [E1].

For each tier: two warmups, 15 randomized ordinary-executable observations, and eight profiled conversions of the same four-second stereo DSD64 fixture. The raw seed, source bytes, commands, source/executable hashes, CPU and wall observations, diagnostic preflights, gmon files and flat profiles are retained. Each timed/profiled output must match its own tier's untimed diagnostic-preflight hash. The fixture is seeded native bits, **not an independent mastering-quality or music corpus**.

@PROFILE_TABLE@

The denominator is **sampled executable CPU time**, not all wall time. Shared-library and kernel time are not separately attributed. Aggregated profiles contain hundreds of samples, enough to identify large regions but not to rank tiny differences. Inlined work belongs to its containing symbol; histogram bins can straddle nearby symbols. In particular, a stray sample labeled with a neighboring block/SDM function is not evidence that decode calls that function. Source call sites resolve that question. Statistical sampling uncertainty remains [E2].

The source evidence and profiles agree: scalar FIR work is substantial, graph/control work is substantial, and the exact frame-count helper is a distinct hot component. These findings directly contradict the claim that an under-1% dense-tier effect proves FIR is only a negligible fraction of decode. They do **not** assign these percentages to the user's physical CPU or forecast the gain from an unimplemented change.

### 2.4 Final SRC and diagnostic reporting controls

@CONTROL_TABLE@

At 88.2 kHz the preflight confirms `final_src_active: false`; at 44.1 kHz it confirms the final SRC is active. Both controls retain the same frontend issue. The new evidence does not revive the withdrawn claim that final sample-rate conversion dominates the 88.2 kHz case.

`--dsd-report` is not a free tag added after conversion. `dsd_observe_input()` in `src/sox_ng.c` feeds native input statistics when a report is requested. The default profiler therefore performs reporting only in an **untimed preflight**, then times and profiles ordinary conversions without it. An explicit `--with-report` run measures the reporting workload separately. Its statistics cost must not be relabeled as baseline decode cost. The old read-to-null control is a useful workload comparison, but subtraction from a different output/conversion path is not a precise profiler decomposition.

## 3. What the SDM evidence supports

### 3.1 Mechanism: a serial time recurrence with useful within-step SIMD

`sdm_normal_step_guarded()` and the SIMD kernels read the previous state bank and quantizer decision, compute the next coordinates and decision, then commit. Successive time samples of one stream are dependent. The vector implementations nevertheless perform real SIMD over **state-coordinate updates as well as the quantizer dot product**. The brief's suggestion that only an inner product is vectorizable is too narrow for the supplied implementation.

The common commit/monitor logic in `src/sdm_normal_commit_i.h` also accounts for finite states, configured bounds, overlapping modulation windows, run lengths, maxima and saturating counters. These costs, short active orders, shuffles/reductions and the time dependency help explain why register width is not an end-to-end multiplier. The data do not isolate an exact cost for each mechanism and do not establish a fundamental 1.17x or 1.2x speed ceiling. Do not remove required guards or monitors to improve a headline number.

The original SDM microbenchmark keeps guards and monitoring active but supplies synthetic `1e18` state bounds. Its profile and bounded arithmetic are meaningful kernel tests; its workload is not identical to the complete certified encoder. The new metadata makes that distinction explicit rather than silently presenting it as a mastering qualification run.

### 3.2 Separate the retained reference from the eventual default

The scalar SDM comment in `src/dsd_dispatch.c` is a certification constraint, not a claim that scalar is fastest. P11-P13 add and qualify execution tiers; the design deliberately defers automatic-default promotion to P15. Existing data not yet causing a default change is therefore not, by itself, a phase defect.

The supplied physical medians imply 11.22% more throughput for SSE2 and 11.51% for AVX2 relative to scalar, or about 10.09% and 10.32% less elapsed time. AVX2 adds only **0.26%** over SSE2 in that case. That difference does not support a general AVX2 preference. Design section 8.4 already favors SSE2 as the conservative optimized tier for an unknown CPU when qualified; section 10.7 requires reliable measured benefits for more specific preferences. AVX-512 remains forceable, but these encode results do not favor it over SSE2/AVX2.

@ENCODE_TABLE@

The local run corroborates a useful scalar-to-SIMD direction, not the exact physical margins or a portable preference. The scalar local encode wall MAD exceeds 2%; the virtual host and single stimulus independently prevent using this run as a default-promotion certificate. Different scalar/vector output hashes are recorded, not treated as a cross-ISA failure. Repeated runs within each tier must remain deterministic.

### 3.3 The smallest coherent qualification action

Retain the existing P10 scalar reference, coefficients, envelopes, analysis filters and certificate identity. Select existing SSE2 as the conservative candidate and make a coverage map from the accepted P11-P13 receipts to the exact candidate source/profile/guard identities. Reuse valid existing numerical and soak evidence; do not order a new modulator design or blindly repeat already-covered long runs.

Close only the candidate's actual coverage gaps: the applicable profiles/rates/orders, within-tier determinism, guard and monitor behavior, cross-ISA quality, and representative end-to-end performance. Section 10.6's quality tests include gain within 0.001 dB, floor-aware residual/noise comparisons within their 1 dB degradation limits, plus phase, spurs, run lengths and stability checks. Cross-ISA native-byte equality is not the quality gate. Section 10.7 supplies the dispatch performance criteria; small tier differences below noise are not preferences.

Record the execution-tier certificate or certification addendum and its supported workload/CPU scope. P15 may then activate the qualified preference while scalar remains explicitly selectable and serves as the retained reference. No coefficient retuning, FMA promotion, guard removal, universal highest-ISA policy or decode redesign is a prerequisite to this evaluation. Broader P15 release acceptance remains governed by the original authority and is not closed by this investigation.

## 4. Corrections to arithmetic, evidence and interpretation

| Item | Finding and consequence |
|---|---|
| Second decode pass spans 1.2% | The full max/min span is **2.2613%**: `0.8954 / 0.8756 - 1`. About 1.2094% is AVX-512 versus scalar, a different denominator. First-pass max/min span is 1.6221%. |
| Decode moves under 1% | Not literally true of the entire supplied tier range. This correction does not turn the small/noisy differences into a useful preference. |
| SDM is roughly 80% of encode | `f = (1 - 1/S) / (1 - 1/k)` gives **70.98%** for `S=1.115`, `k=1.17`; actual recorded AVX2 ratios give **69.63%**. Even that is only a consistency calculation assuming the same accelerated workload, not measured attribution. |
| 11.5% encode improvement | Correct as rounded throughput increase; the elapsed-time reduction is **10.32%**. Keep the two definitions distinct. |
| FIR is insignificant because dense tier changes barely move decode | Invalid substitution of a dense/block microbenchmark for predominantly scalar half-band streaming FIR work. Source and profiles identify the actual mismatch. |
| FIR follows width uniformly | The supplied single-output row already peaks at AVX2, not AVX-512. The strongest width trend belongs to a particular dense block workload. Production stride and bank shape matter. |
| SDM does not vectorize / has a measured fundamental cap | The code vectorizes state coordinates and reductions. Limited observed scaling is real; an ISA-independent or algorithmic ceiling is not established. |
| Independent kernel stimuli | The delivered harness uses fixed synthetic input/coefficient constructions. Repeating phases or changing frame counts does not by itself establish independent kernel stimuli. Fresh end-to-end source files are a separate matter. |
| All physical raw evidence is present | The delivered physical matrix names **seven child JSON artifacts absent from the archive**. Five-tier medians survive in text; their underlying physical repetitions cannot be recomputed here. This does not prove the runs never happened. |
| Physical five-tier benchmark meets the short-run repetition rule | Its accompanying records specify seven and nine repetitions. The authority requests warmups and at least 15 timed short-run repetitions with dispersion/confidence. Existing medians are exploratory evidence, not a new dispatch preference certificate. |
| All physical matrix work pinned to CPU 8 | Its parent JSON records affinity CPUs 8-23; the separate five-tier notes say CPU 8. Without the child records, reconcile those run identities before treating the parent matrix as single-CPU-pinned evidence. No claim is made that the separately described CPU-8 runs violated their stated affinity. |
| VM/unavailable-AMD labels in matrix runner | These were static historical literals. Future output now records observed model/vendor/hypervisor flag and leaves physical qualification unassessed. An absent hypervisor flag does not prove bare metal. Historical JSON remains untouched. |
| Intel AVX-512 is unavailable because client Intel disabled it | Project access constraints may be real, but this is not a hardware-existence argument: Intel documents AVX-512 on Xeon products [E3]. No purchase is requested. Under the unchanged design, an unavailable required host remains a named gap or requires an explicit authority/scope amendment, not a fabricated passing test. |

The three source hashes recorded by the supplied physical matrix match the delivered dispatcher, AVX2 and AVX-512 source bytes. The source/evidence audit and exact arithmetic are machine-readable in `source-and-arithmetic-audit.json`. Historical P12 raw kernel JSON exists and supports its summarized comparison; this report does not repeat the withdrawn claim that the data were absent.

## 5. Next optimization experiment, not an implementation order

Two bounded experiments are justified: reduce redundant per-native-frame count/control work without changing exact streaming semantics; and accelerate the actual 57-tap half-band path, comparing a specialized direct kernel with bounded use of existing block primitives. The scalar reference and current public behavior remain the oracle. Evaluate each independently on ordinary decode before combining changes. Keep only a small coherent change whose whole-path gain survives output, numerical, latency, bounded-memory, error/backpressure and unchanged-path regression tests.

Do not begin another general dense-FIR widening campaign on the strength of the 4.21x headline. Do not make speculative batching architecture mandatory. Do not couple the SDM default decision to completion of decode optimization. This investigation demonstrates where to look and supplies a reproducible tool; it does not promise a particular unimplemented speedup.

## 6. Reproduction and implementation scope

From the extracted source root, using the actual optional library/link configuration of the build host:

```sh
autoreconf -fi
./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'
make -j2
make -C test dsd_test_p11 sox_dsd_profile sox_p10_candidate
python3 tests/dsd/test_perf_measurements.py

# Replace 8 with an allowed, intentionally chosen CPU on the target host.
taskset -c 8 python3 tests/dsd/bench_p11.py \
  --unit test/dsd_test_p11 --phase INVESTIGATION --results results/kernel-new \
  --repetitions 15 --frames 1000000 --tiers scalar sse2 avx1 avx2 avx512 \
  --modes fir-single fir-block sdm fir-halfband-single fir-halfband-block \
    fir-master64-single fir-master64-block fir-master128-single \
    fir-master128-block fir-wideband-single fir-wideband-block

python3 tests/dsd/profile_decode.py --results results/decode-new \
  --cpu 8 --seconds 4 --repetitions 15 --profile-repetitions 8
# Add --source /path/to/source.dsf with matching --native-rate and --channels
# to profile an independently selected source instead of the synthetic fixture.
# Use --pcm-rate 44100 for the final-SRC control, or --with-report for its
# separately identified reporting workload. Supply only supported --tiers.

taskset -c 8 python3 tests/dsd/bench_p11_e2e.py --phase INVESTIGATION \
  --results results/encode-new --sox src/sox_ng --candidate test/sox_p10_candidate \
  --repetitions 15 --warmups 2 --decode-seconds 1 --encode-seconds 1 \
  --native-rate 2822400 --pcm-rate 176400 --channels 2 --threads 1 \
  --tiers scalar sse2 avx1 avx2 avx512

make check
make check-dsd DSD_PHASE=P14 DSD_RESULTS="$PWD/results/regression-new"
```

The profiling executable is optional, uninstalled and uses GNU-compatible `-pg` startup support plus GNU gprof. It is not a new production dependency. The profiler records partial progress atomically and refuses to overwrite a nonempty results directory. Rerun into a new directory after interruption; preserve earlier evidence. It records the actual host affinity but does not change governor/boost or certify the machine as physical. Run benchmarks without competing builds, retain raw results, and measure representative file I/O separately from controlled memory-backed work when qualifying a preference.

Measurement-tool tests cover exact bank/stride metadata; scalar/SIMD and single/block checksums; old synthetic workloads; invalid and duplicate modes; source identity; observed-host labels; DSF chronology against the existing independent fixture oracle, including partial bytes/blocks and mono/stereo/six-channel layouts; profile denominator/error handling; timeout enforcement; log capture; and protection of pre-existing evidence. Performance thresholds are deliberately absent from unit tests.

A preliminary investigation script used POSIX timeout polling, which can quantize parent wall observations. Its version and affected preliminary runs are retained under exploratory evidence, and are **not** the final timing basis. The corrected runner blocks on child exit and uses a sleeping timeout watchdog; stdout/stderr remain disk-backed. Kernel self-CPU timings and the unchanged pipe-capturing end-to-end runner were not affected. The final controlled decoder runs were repeated with the corrected script.

## 7. Validation and retained artifacts

@VALIDATION@

All local timing is host/workload-specific. No new physical Threadripper run, Intel/older-AVX physical qualification, default promotion, P15 completion or mastering-certificate replacement is claimed. Existing hardware/qualification records retain their historical status; missing raw files limit this independent audit but are not silently turned into new implementation requirements.

The bundle includes a complete clean continuation source tree, a minimal review patch, the original brief, full measurement and regression evidence, the exact optional profiling executable needed to interpret retained gmon files, source/executable hashes, a current-tree SHA-256 inventory and a resume checkpoint. Build products outside explicitly labeled evidence are excluded. The original archive is not nested redundantly inside the new source bundle.

### External method/context references

[E1] GNU gprof, "Compiling a Program for Profiling," especially its link-only time-sample discussion and `-Q`: `https://sourceware.org/binutils/docs/gprof/Compiling.html` (accessed 2026-10-12).

[E2] GNU gprof, "Statistical Sampling Error": `https://sourceware.org/binutils/docs/gprof/Sampling-Error.html` (accessed 2026-10-12). These sources explain the measurement method, not the repository-specific findings.

[E3] Intel, "Intel AVX-512 - FP16 Instruction Set for Intel Xeon Processor Based Products Technology Guide," updated 2024-03-11; describes AVX-512 on fourth-generation Xeon and existing 32/64-bit operations: `https://builders.intel.com/solutionslibrary/intel-avx-512-fp16-instruction-set-for-intel-xeon-processor-based-products-technology-guide` (accessed 2026-10-12). This establishes existence, not project access or qualification.

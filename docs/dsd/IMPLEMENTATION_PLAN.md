# Dependency-ordered implementation plan

This plan implements `DSD_DESIGN.md`, revision 1.0. The preferred integration sequence is P00 through P18. P00-P15 are the first release; P16-P18 are a separately gated extension. Dependencies below state the minimum semantic prerequisites; use the authoritative continuation tree from all preceding accepted phases in the recommended sequence. Do not implement multiple adjacent phases merely because their source files overlap.

Each SOW is a fresh-session prompt. Before P00, install this package's documentation overlay in the attached baseline repository. After that, the repository bundle itself contains the design and all SOWs. No SOW relies on hidden chat history. Phase output must be one complete authoritative continuation tree containing code, tests, evidence and a human-readable handoff, not a patch against an unspecified intermediate tree.

P00 creates the `check-dsd` target and the `run.py`, `measure.py` and `bench.py` interfaces named below. A phase that has no new DSP uses the numerical runner for bit/count invariants; it does not invent a numerical quality result. Existing optional dependencies may be absent, but every skip must name the unavailable capability. Full hardware and long-run certification are P15/P17 gates; test programs can be implemented earlier without pretending the long run already happened.

All phases preserve unrelated PCM behavior, existing public struct layouts, existing supported command syntax and native bit chronology unless this specification explicitly corrects it. Production changes are limited to the stated objective. No phase may remove an earlier accepted regression test, turn a failure into an unexplained xfail, or fabricate a benchmark/qualification result.

## Required continuation handoff

For each phase write `docs/dsd/handoffs/Pxx.md` with objective, files changed, commands and exit codes, test/benchmark evidence paths, passed/failed/skipped gates, design deviations and the next permitted phase. Include a patch/diff and hashes against the actual input tree as convenient review aids, but return the complete tree. Preserve checkpoints during long tests; a resumed test records its state/source hashes. Do not overwrite the phase's failing evidence with a successful rerun without retaining both.

## Release dependency graph

```text
P00 -> P01 -> P02 -> P03 -> P04 -> P05 -> P06 -> P07 -> P08
    -> P09 -> P10 -> P11 -> P12 -> P13 -> P14 -> P15
                                                    |
                                                    v
                                                  P16 -> P17 -> P18
```

This deliberately serial review order prevents simultaneous edits to format state, planner semantics and kernel interfaces. A team may parallelize independent test development, but merge only against the declared interfaces and rerun all accepted prerequisites.


## P00: Freeze independent evidence and test infrastructure

**Dependencies:** None; start from the attached baseline.

**Objective and requirements:** Handoff C1-C5; additional D1 first-cluster corruption and D2 WAV private seek state; all subsequent acceptance machinery.

**Read:** DSD_DESIGN sections 1, 4, 10 and 14; src/Makefile.am; test/Makefile.am; dsf.c; dsdiff.c; formats.c; wav.c; evidence/probe_io.c and reproduce.py.

**Existing files/components:** Makefile.am, src/Makefile.am and test/Makefile.am only as needed to register maintainer/test targets.

**New files/components:** tests/dsd/{fixtures,reference,results}; tests/dsd/run.py; tests/dsd/measure.py; tests/dsd/bench.py; tests/dsd/test_io.c; docs/dsd/BASELINE.md.

**Implementation:** Install the approved design/plan/SOW overlay under docs/dsd. Record source and toolchain hashes. Build the untouched baseline. Generate hand-derived tiny DSF/DFF/DoP vectors and independent chunk walking. Port the supplied reproductions into explicit named xfails. Establish deterministic seeds, JSON result schemas, CPU/build metadata and a throughput harness. Add test modes that later phases can extend rather than creating a separate runner per phase.

**Unit acceptance:** Fixture generator self-tests; independently checked bit chronology; chunk spans; exact integer count helpers in the harness; xfail classification that fails if the expected defect disappears or changes unexpectedly.

**Integration/known-answer acceptance:** Reproduce small reads, MSB rejection, first DFF cluster under allocator perturbation, odd/tail chunk defects, multichannel seek, MANF, DSF Type 5 loss and WAV rewind after manual core-position correction. Run existing make check.

**Numerical acceptance:** Implement measurement definitions and data schemas, not new acceptance claims. Record filter feasibility as supplied evidence only. Prepare analysis-v1 generation entry point and synthetic PCM source fixtures.

**Benchmarks:** Record native transcode and direct ultra-quality decode baselines for DSD64/128/256, 1/2/6 channels, including 352.8/705.6 kHz; a short development matrix is acceptable here if full commands and durations are stored.

**Completion:** Untouched behavior still reproduces each named defect; generic tests pass; make check-dsd succeeds with only enumerated baseline xfails; all logs identify actual executed commands.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. The repository is commit 16aa7e17531dd3612f29247da98c8ea570cd905a. Do not alter production behavior. Public SoX I/O counts interleaved samples; fixture truth must distinguish chronological per-channel frames. Preserve a known failing test for each defect, including the newly demonstrated first DFF byte and WAV counter defects. A test being skipped is not a pass.

**Risks:** Accidentally using the writer under test as the fixture oracle; blanket xfails; host-specific timings mistaken for universal results.

**Out of scope:** Production fixes, new DSP, new defaults, ISA optimization and full proprietary/hardware validation.

**Fresh-session SOW:** `sows/P00.md`.


## P01: Repair DSDIFF output structure and first-cluster bits

**Dependencies:** P00.

**Objective and requirements:** C1.1-C1.4 and additional confirmed defect D1.

**Read:** DSD_DESIGN sections 1.2 and 4.1; src/dsdiff.c dff_writeheader/startwrite/write_bits/write_buf/stopwrite; tests/dsd writer fixtures.

**Existing files/components:** src/dsdiff.c; test registration only if needed.

**New files/components:** Focused writer regression vectors and chunk-walker expected structures in tests/dsd.

**Implementation:** Zero the initial byte-cluster accumulator. Define checked physical span(n)=12+n+(n&1). Correct FRM8/PROP size accumulation. Use CMPR name length 14 and payload length 19 with external pad. Count a silence-completed final cluster in audio size. Write external audio padding without counting it as audio. Preserve the existing 0x69 chronological completion convention and propagate write/seek failures.

**Unit acceptance:** Size arithmetic; CMPR count/payload; initial accumulator; partial final cluster for each residual bit count 1..7.

**Integration/known-answer acceptance:** Independent walker over empty, one-byte, even/odd and multichannel files; byte-for-byte program payload under allocator perturbation; original generic suite; cross-format chronology with expected DFF completion.

**Numerical acceptance:** No DSP changes. Assert native source bits remain identical through their logical endpoint; DFF logical output rounds up to eight frames only when completion is required.

**Benchmarks:** Native DFF writing at 1/2/6 channels versus P00; reject a repeatable regression beyond the unchanged-path tolerance.

**Completion:** All C1/D1 xfails become hard passes; first output bits do not depend on allocator contents; declared and physical spans agree for every fixture.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. This is a localized DFF writer patch. A nine-frame mono source becomes sixteen DFF frames because DFF has byte-granular duration; the last seven are the existing explicit completion pattern. That is not a reason to corrupt the first nine. Never reintroduce payload double counting or count CMPR NUL as text.

**Risks:** Counting a pad as sound; completing one byte instead of one byte per channel; arithmetic fixes concealing an incorrect physical file.

**Out of scope:** Reader redesign, seek fixes, channel metadata, DSP, automatic mode and ISA changes.

**Fresh-session SOW:** `sows/P01.md`.


## P02: Make DSD readers retained-bit streaming state machines

**Dependencies:** P00, P01.

**Objective and requirements:** C3, C4; tiny/empty valid files; shared DFF/WSD state constraints; DoP capacity invariance if its API probe exposes a defect.

**Read:** DSD_DESIGN sections 2.2, 4.2 and 4.5; src/dsf.c; src/dsdiff.c; src/dop.c; P00 small-capacity tests.

**Existing files/components:** src/dsf.c; src/dsdiff.c; src/dop.c only for an independently tested capacity correction.

**New files/components:** Small-read, bit-order, zero-capacity and parser extent tests in tests/dsd.

**Implementation:** Retain byte/block/bit position across calls. Load a DFF/WSD byte cluster only when the cached cluster is exhausted. Make one-frame capacity progress. Accept DSF bps 1 and 8 with normalization outside the hot bit loop. Remove the invalid eight-byte DFF minimum; require complete channel clusters. Handle zero logical frames explicitly. Initialize required parser fields and validate enclosing spans/skip results. Add no duplicate DFF remaining-audio counter. Check DoP pending output before writing to a zero-capacity destination.

**Unit acceptance:** Capacities 0 and 1..17 frames; bytes with asymmetric reversal patterns; tails 1..7 bits; cache invalidation; mandatory-field/extent initialization.

**Integration/known-answer acceptance:** Channels 1..6 including CLI --buffer 32; multiple DSF blocks; mono one-byte DFF; forward-only streams where supported; baseline DoP hand vectors and backpressure.

**Numerical acceptance:** Concatenated small-read output equals the independent large-read chronological reference exactly. No DSP or level change.

**Benchmarks:** Small/large-buffer native reads and native transcodes; retained state must not cause a large-read throughput regression outside the specified tolerance.

**Completion:** C3/C4 xfails become hard passes; no legal positive whole-frame read returns false EOF; all source-order forms yield identical chronology.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. Public read capacity is interleaved samples, rounded down to a complete channel frame. A request for one frame means channels samples, not one byte per channel. DSF bps=8 is MSB-first one-bit DSD, not 8-bit PCM. A cache is justified streaming state; a second remaining-audio counter for the old MANF symptom is not.

**Risks:** Decoding a fresh cluster over a partially consumed one; treating numeric zero as a DSD silence bit; accepting malformed extents as a substitute for proper empty-file handling.

**Out of scope:** Core seek bookkeeping, new layout model, reconstruction filters, SDM selection and speculative WSD speaker mapping.

**Fresh-session SOW:** `sows/P02.md`.


## P03: Unify seek units and reset logical and private positions

**Dependencies:** P00-P02.

**Objective and requirements:** C2.1-C2.3; additional WAV defect D2; representative non-DSD seek behavior.

**Read:** DSD_DESIGN section 4.3; src/formats.c sox_read/sox_seek; formats_i.c lsx_offset_seek; dsf.c/dsdiff.c seeks; wav.c seek_wav; sox_ng.c interactive seek/optimize_trim; raw, msupcm, prc, smp, flac, opus, vorbis and wavpack seek handlers.

**Existing files/components:** src/formats.c; src/sox_ng.h seek documentation; src/dsf.c; src/dsdiff.c; src/wav.c; src/sox_ng.c; other named handlers only when their target/state audit demonstrates a mismatch.

**New files/components:** Seek-handler inventory; unit conversion helper tests; optional-codec fixtures/tests; docs/dsd/SEEK_CONTRACT.md.

**Implementation:** Normalize offset down to a complete channel frame once in core. Check known bounds and arithmetic. On successful seek commit olength to normalized interleaved target. Clamp known-length reads without unsigned underflow. Normalize native handlers to per-channel positions and clear caches. Reset WAV numSamples from original total; implement exact GSM block seek plus discard or return unsupported. Correct interactive callers and only update their counters on success. Verify pending FLAC seeks cannot leak old buffered samples.

**Unit acceptance:** Aligned and unaligned public offsets; byte/non-byte DSD positions; end and out-of-range seeks; multiplication overflow; pending cache state; failure before physical movement.

**Integration/known-answer acceptance:** Read-rewind-read, seek after prior reads, DFF MANF, sequential versus seek-optimized native trim; WAV PCM and GSM, raw PCM and available optional codecs; channels 1..6.

**Numerical acceptance:** Exact slice equality and remaining frame counts. No filter, gain or encoder changes.

**Benchmarks:** Seek latency and sequential read throughput versus P00; no per-sample generic overhead beyond bounded remaining-length checks.

**Completion:** Every successful built-in seek in the audited set resolves to the normalized target; C2/D2 cases pass; optional dependency gaps are named, not inferred passed.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. sox_seek offsets remain interleaved samples. For compatibility, floor an unaligned request to its containing whole frame and document it. Exact-end seek is valid. A DFF MANF over-read is resolved by core position and correct native units; WAV independently needs its private remaining counter reset. Do not merge these root causes or pretend one assignment fixes both.

**Risks:** Assigning olength while a decoder lands elsewhere; double channel multiplication; fixing core but leaving WAV private state stale.

**Out of scope:** SEEK_CUR/END, a general random-access decoder redesign, DFF-private MANF counters and DSP pre-roll optimization.

**Fresh-session SOW:** `sows/P03.md`.


## P04: Preserve DSD channel identity with bounded metadata APIs

**Dependencies:** P00-P03.

**Objective and requirements:** C5; pre-header layout installation; DSF Type 4 versus 5; DFF CHNL/LSCO; bounded WAV extensible bridge.

**Read:** DSD_DESIGN sections 3.2 and 4.4; src/sox_ng.h public structs; formats.c open_write; dsf.c; dsdiff.c; wav.c mask handling; sox_ng.c output opening; remix.c metadata parsing.

**Existing files/components:** src/formats.c; src/dsf.c; src/dsdiff.c; src/wav.c; src/sox_ng.c; src/remix.c only for a bounded pure-map metadata query; build/export lists.

**New files/components:** src/sox_dsd.h; src/dsd_layout.c; private layout declarations; layout fixture/mapping tests.

**Implementation:** Implement opaque layout ownership and copy-out APIs. Preserve original DSF type, DFF IDs/order and optional LSCO. Add sox_open_write_dsd as an additive wrapper installing copied layout before startwrite. Implement explicit mapping/permutation and loss behavior. Bridge representable layouts to WAV extensible masks/order. Expose WSD assignment only as opaque provenance. Preserve or invalidate layout according to a known pure-map versus mix operation; no global comment-tag or pointer registry.

**Unit acceptance:** Ownership/deep-copy/lifetime; Type 4/5 distinction; representable and ambiguous role maps; LSCO consistency; pure permutation versus mix invalidation.

**Integration/known-answer acceptance:** Native DSF/DFF round trips, standard/context IDs, WAV mask and actual channel sample order, explicit metadata-loss rejection/override, header values correct before first audio write.

**Numerical acceptance:** Native bits unchanged except an explicitly planned permutation; no DSP changes. Mapping tests use distinct channel impulses/bit sequences.

**Benchmarks:** Native transcode overhead and peak allocation versus P00; no metadata work in per-bit loops.

**Completion:** C5 fixtures pass without widening existing public structs; ownership and destination loss semantics are documented and tested.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. Keep existing public struct layouts/entry points ABI-compatible. New layout APIs are additive and opaque. DFF IDs define sample order; LSCO cannot silently override it. DSF cannot truthfully encode an arbitrary unknown layout. A float WAV file still needs a correct speaker mask; its encoding does not solve channel semantics.

**Risks:** Mistaking speaker count for identity; guessing side/back angles; setting metadata only after headers open; ownership bugs from shallow copies.

**Out of scope:** Full SoX speaker-routing architecture, ancillary tag overhaul, WSD semantic claims without its specification and DST support.

**Fresh-session SOW:** `sows/P04.md`.


## P05: Implement the DSD contract and preflight domain planner

**Dependencies:** P00-P04.

**Objective and requirements:** Explicit native/PCM/DoP boundary; pre-combiner scaling/mixing; headers before effects; retained DSD reference level; versioned rate/profile descriptors and CLI policy.

**Read:** DSD_DESIGN sections 2, 3 and 5; src/sox_ng.c process/create_user_effects/calculate_* /balance_input/combiner/add_effects; effects.c cloning; rate/dop/sdm/dither option handlers.

**Existing files/components:** src/sox_ng.c; effect registration/help/manpages; private configuration declarations; no automatic default activation yet.

**New files/components:** src/dsd.h; src/dsd.c; src/dsd_plan.c; planner fixtures and plan-only test entry point.

**Implementation:** Implement exact native rate capabilities with 512/1024 disabled. Parse and validate the specified options/effect configurations. Produce immutable plans before open_output_file. Keep native and effective per-input signals separate. Classify unknown effects as PCM and unknown multichannel layout transforms conservatively. Resolve working rates, reference-level tags/inverse decoder gain for remodulation, explicit rate semantics, transport requirements, clip/layout policies and trim optimization eligibility without starting effects twice. Emit inspectable plan JSON for tests.

**Unit acceptance:** Every domain transition and illegal ordering; explicit/implicit duplicate decode/encode; noninteger new-profile PCM rate rejection; no-op/native paths; output negotiation conflicts.

**Integration/known-answer acceptance:** Plan tests for pure transcode, PCM decode, overdrive, input -v/replay gain, mix/multiply/merge padding, processed DSD output, terminal DoP, explicit rate and sequence boundaries.

**Numerical acceptance:** No new production DSP is required in this phase. Verify exact integer count/capability helpers and all specified effective-bandwidth calculations.

**Benchmarks:** Preflight allocation/time on small and many-input invocations; no per-sample cost added to unchanged paths.

**Completion:** Every specified example has an unambiguous plan before headers open; unsupported requests fail early; new defaults remain opt-in.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. The three domains are native DSD, PCM audio and DoP transport. Unknown effects need PCM. Native repacking/terminal DoP stay native. Input volume and parallel combination require per-input reconstruction before balance_input; adding an effect after the combiner is too late. A leading ordinary rate operates on reconstructed PCM and retains its options. This phase establishes plans, not a claim that unimplemented DSP already works.

**Risks:** Looking only at effect precision or endpoint encoding; forgetting operations before add_effects; dry-running stateful starts; ambiguous option precedence.

**Out of scope:** New FIR implementation, SDM profile promotion, ISA optimization and a replacement effects engine.

**Fresh-session SOW:** `sows/P05.md`.


## P06: Generate certified filters and implement scalar reconstruction

**Dependencies:** P00-P05.

**Objective and requirements:** Mastering/wideband profiles; scalar FIR/half-band engine; source-rate-aware DSD64/128/256; exact phase and finite boundaries.

**Read:** DSD_DESIGN section 6 and 8.6; evidence/probe_filters.py and filter_feasibility.json; src/dsd.h; rate_half_fir.h as context only.

**Existing files/components:** Build/test registration; src/dsd.c profile descriptors.

**New files/components:** src/dsd_decode.c; src/dsd_coeffs.h; src/dsd_kernels_scalar.c; tests/dsd/generate_coeffs.py; independent convolution/extremum/alias tests and coefficient manifests.

**Implementation:** Generate high-precision symmetric Kaiser banks and checked-in binary64 hex constants. Verify final coefficient bytes independently. Implement per-channel rings, factor-two phases, scalar symmetric kernels and bounded streaming. Use candidate tap sequences 57x4+117, 57x4+153, 57x5+117 and 57x4+257, increasing only with documented regenerated evidence. Align phase G mod D and discard floor(G/D). Produce centered intermediate samples with the specified finite zero-extension policy.

**Unit acceptance:** Structural half-band zeros/center/DC/symmetry; coefficient hashes; ring wrap; phase bits; counts for input lengths 0..33; zero capacity/finish idempotence; allocation cleanup.

**Integration/known-answer acceptance:** Scalar intermediate outputs for all three native rates, channels 1/2/5/6 and irregular buffers; native bit interface rejects noncanonical values; no public automatic activation.

**Numerical acceptance:** P/S/ripple <=0.0001 dB and composite alias/stop <=-160 dB; stage target >=185 dB; adaptive extrema and coherent image sums; high-precision finite convolution, impulse and boundary oracle.

**Benchmarks:** Scalar kernel and front-end throughput/memory for 64/128/256, 1/2/6 channels; record tap-count costs without claiming SIMD speedup.

**Completion:** Coefficient bytes, mathematical oracles, stream endpoints and scalar response all pass; candidate feasibility files are not blindly promoted as certificates.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. Mastering P/S/R in Hz: 64=20000/40000/88200; 128=30000/60000/176400; 256=40000/80000/176400. Wideband R=Fs/32, P=.4R, S=.5R. All are linear phase and unity DC. Scalar output uses binary64. Finite boundaries are numeric zero outside the input, not 0x69 or all-zero DSD bits. No new arbitrary-ratio resampler is authorized.

**Risks:** Confusing stage input rate with output rate; last-stage-only alias testing; wrong fractional phase; numeric zero versus a DSD zero bit.

**Out of scope:** Arbitrary-ratio SRC, automatic CLI routing, encoder profiles, SIMD and higher native-rate enablement.

**Fresh-session SOW:** `sows/P06.md`.


## P07: Integrate the private double SRC and explicit dsdpcm effect

**Dependencies:** P00-P06.

**Objective and requirements:** All nine PCM outputs through 705.6 kHz; one final quantization; exact composite counts; level/headroom behavior.

**Read:** DSD_DESIGN sections 3.3-3.4 and 6.4-6.6; src/rate.c backend and public wrapper; effects.c flow cloning; src/dsd_decode.c.

**Existing files/components:** src/rate.c; src/effects.c and sox_i.h private fatal-status propagation; src/sox_ng.c failure/finalization handling; effect/export/build registration; src/sox_dsd.h and decoder implementation.

**New files/components:** src/rate_internal.h; src/dsdpcm.c; private SRC adapter tests; public double decoder tests.

**Implementation:** Expose an opaque binary64 wrapper around the existing static rate backend without altering the public effect. Use linear phase, rejection 180 and 95-percent 0-dB bandwidth, equivalent to -B not -b. Implement explicit zero-extension and caller-controlled final frame limits. Compose reconstruction with final SRC. Add public multichannel decoder and a mono-per-flow dsdpcm adapter. Apply preserve or exact gain two once, then explicit graph clipping policy. Add the private fatal status so strict clipping stops before a failed block is interleaved/emitted; latch details, preserve normal EOF semantics and make CLI exit/finalization status truthful.

**Unit acceptance:** Identity SRC; rational count arithmetic; tiny streams and double-rounding counterexamples; finish with needed extra support; separate contexts and per-channel ownership; API overrange values.

**Integration/known-answer acceptance:** Explicit dsdpcm across 3x9x2 matrix; buffer/thread invariance; float output still graph-clipped in CLI; clipping warnings/errors including mono/multichannel fatal flow/drain and a following chain; finalization failure; strict versus adapt bandwidth; legacy public rate regression goldens.

**Numerical acceptance:** Full impulse/phase/endpoint and response envelope; independent final-SRC reference at 48 kHz-family ratios; <=1 int32 LSB scalar/vector-ready FIR-boundary tolerance; exact output counts.

**Benchmarks:** Explicit decode throughput and memory, especially master64->705600 and wide256->705600, versus direct and bandwidth-matched staged controls.

**Completion:** All explicit conversions work to 705.6 kHz; public rate behavior remains unchanged; no false claim that float output bypasses int32 graph limits.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. Pure conversion count is floor(Nnative*Fout/Fnative+1/2), computed with checked integer arithmetic. Generate ceil(N/D) intermediate samples, zero-extend that finite sequence for the final SRC, and return only the original-timebase final count. Preserve is unity; sacd is exactly gain two. Double API values may exceed one; ordinary SoX graph samples cannot.

**Risks:** Inheriting legacy LPC extrapolation accidentally; rounding intermediate length twice; owning pointers allocated before effect cloning; using -b as a 0-dB bandwidth.

**Out of scope:** Automatic input adapters/defaults, new encoder selection, ISA specialization and a direct floating CLI writer pipeline.

**Fresh-session SOW:** `sows/P07.md`.


## P08: Activate correct DSD boundaries including input adapters

**Dependencies:** P00-P07.

**Objective and requirements:** A1/A2 pre-combiner and pre-header constraints; native pass-through; generic effects; DSD remodulation planning; trim/sequence semantics.

**Read:** DSD_DESIGN section 5; src/dsd_plan.c; src/sox_ng.c balance_input/combiner/read_wide/process/add_effects/optimize_trim; dsdpcm and layout APIs.

**Existing files/components:** src/sox_ng.c; src/dsd_plan.c; targeted effect metadata queries; CLI/manpage examples.

**New files/components:** Input-adapter integration fixtures, nonlinear/mix/volume/sequence tests and resolved-plan snapshots.

**Implementation:** Use plan-resolved effective signals in combiner accounting without mutating native reader metadata. Attach per-input decoders before volume/replay gain/parallel mixing and padding. Apply known file gain to binary64 reconstructed PCM before graph quantization and suppress duplicate balance_input gain. Carry DSD-origin calibration into planned remodulation. Insert explicit/automatic boundaries once. Preserve native repacking and DoP. Disable native trim seek optimization in reconstructed chains until context-aware parity exists. Enforce downstream-domain constraints and headers/layout before audio. Keep encoder automatic promotion unavailable until P10/P15, with a clear interim unsupported/opt-in state rather than a false mastering claim.

**Unit acceptance:** Adapter state/cursor/EOF/reset ownership; common working-rate choice; sequence transitions; no duplicate stage; layout clearing and output negotiation.

**Integration/known-answer acceptance:** Compare overdrive and gain to explicit reconstruct-first PCM; test -v/replay gain, mix/multiply/merge tails, concatenation policy, native trim, DoP prohibition after PCM effects and processed DSD chain planning.

**Numerical acceptance:** Adapter output equals explicit dsdpcm reference under the same finite-file policy; no extra samples/clipping or hidden gain; native bit paths remain exact.

**Benchmarks:** Native transcode overhead and adapted multichannel throughput; compare single downstream decoder versus per-input adapters only where semantics allow.

**Completion:** No generic arithmetic operates on native pulses in auto mode, including before user effects; no DSP runs for unprocessed native transcodes; all routing tests pass.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. Pure same-rate native repacking remains native. PCM effects force reconstruction; terminal DSD output later requires one pcmdsd. Input-level gain and parallel combination are the special case requiring conversion before the combiner. Unknown effects are PCM. The old trim seek optimization is disabled on reconstructed paths; do not fake sequential parity with an unprimed filter.

**Risks:** Fixing only add_effects; progress counters in the wrong rate domain; a seek shortcut skipping filter pre-roll; resetting a continuous native concatenation accidentally.

**Out of scope:** A new general mixer/SRC engine, sample-identical interactive DSP seeking, new SDM coefficient design and default release promotion.

**Fresh-session SOW:** `sows/P08.md`.


## P09: Extract exact-rate SDM profiles and freeze independent metrology

**Dependencies:** P00-P08.

**Objective and requirements:** Hidden first-match selection; formal analysis-v1; state/28-bit diagnostics; separation of normal SDM and trellis ownership.

**Read:** DSD_DESIGN sections 7 and 10.2/10.5; src/sdm.c, sdm.h, sdm_x86.h, dither.c; evidence/probe_sdm.c and sdm_short_stress.json.

**Existing files/components:** src/sdm.c; src/sdm.h; src/dsd.c; normal-path wrapper and test hooks only; no default behavior change.

**New files/components:** Exact-rate/profile registry; small normal-state interface; tests/dsd/reference/analysis-v1; independent coefficient generator and reconstruction/measurement runner.

**Implementation:** Extract normal recurrence/profile data without changing coefficient bits or quantizer tie rule. Preserve legacy wrapper scaling and trellis behavior. Require exact lookup in new APIs; keep legacy fallback explicit only. Add monitoring hooks/counters without silently resetting state. Freeze a single independent 20/24 kHz analysis FIR per native rate and all power/window/fit conventions. Record candidate/legacy results and training/holdout corpus identities.

**Unit acceptance:** Exact lookup rejection, coefficient hashes, state initialization, negative-zero tie, 28-bit windows across buffers, counter overflow handling and profile lifetime.

**Integration/known-answer acceptance:** Existing explicit sdm/dither/trellis compatibility; scalar candidate probes and metadata; source rates 64/128/256; unsupported future rates rejected by new profile APIs.

**Numerical acceptance:** Independent analysis filter response and output count; coherent and windowed signal-fit self-tests with known noise/distortion; candidate rankings reported only under analysis-v1.

**Benchmarks:** Normal state allocation footprint, legacy normal/trellis throughput and monitor overhead; preserve legacy controls for later comparison.

**Completion:** New profile selection cannot reuse lower-rate coefficients implicitly; metrology is frozen and reproducible; no candidate has been relabeled qualified without its tests.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. Selected mastering candidate is exact-rate sdm-8, but qualification is not complete. Preserve the original recurrence and coefficient bits. The supplied 0.125-second probe bypasses interpolation and is not a release test. Freeze analysis-v1 before comparing absolute dB numbers. Cross-ISA byte identity is not a quality criterion.

**Risks:** Treating raw states of millions as automatic failure; treating isfinite as sufficient stability; self-reconstruction mistaken for an independent oracle.

**Out of scope:** Default selection change, automatic stabilizer, new coefficients without evidence, SIMD and higher-rate writing.

**Fresh-session SOW:** `sows/P09.md`.


## P10: Implement and qualify composite PCM-to-DSD mastering profiles

**Dependencies:** P00-P09.

**Objective and requirements:** Explicit interpolation/modulator/level/stability contract; sdm-8 candidate qualification; processed DSD output; sources through 705.6 kHz.

**Read:** DSD_DESIGN sections 7, 10.2 and 10.5; rate_internal.h; sdm profile registry; src/dsd_plan.c; dither.c; analysis-v1.

**Existing files/components:** src/sdm.c normal-profile integration; src/dsd.c; src/sox_ng.c automatic encoding hook; effect registration/help; no default promotion before P15.

**New files/components:** src/pcmdsd.c; encoder prefilter coefficients/manifests; profile certificates and overload/holdout tests.

**Implementation:** Implement local binary64 source-to-R SRC, non-decimating P/S prefilter at R and interpolation to native rate. Apply reference scaling once: 0.5 for ordinary PCM, inverse decoder-reference gain for DSD-origin auto remodulation. Initialize exact-rate sdm-8 state deterministically. Enforce admitted peak and frozen per-coordinate guard bounds; use the established fatal-status path to fail/report overload without limiter/reset/fallback or false successful EOF. Generate profile certificates from training and independent holdout/soak evidence. Insert one explicit/opt-in composite encoder after PCM processing and avoid precision-1 dither duplication.

**Unit acceptance:** Input envelope including SOX_SAMPLE_MIN margin, guard/NaN failure, first failing frame/channel, block commit count, exact output duration and final container completion.

**Integration/known-answer acceptance:** 9 PCM source rates x 3 DSD targets; unity and -3 dB DSD-origin remodulation without an extra 6.0206 dB loss; explicit pcmdsd; processed DSD-to-DSD; -D semantics; manual sdm compatibility; full-scale interpolation overload with required explicit attenuation.

**Numerical acceptance:** Analysis-v1 tone/noise/spur/stability suite; DSD64 28-bit guarantee for admitted corpus; rate-specific higher-rate diagnostics; >=6 dB DSD64 aggregate residual improvement target and no material per-case regressions; held-out state bounds.

**Benchmarks:** Whole composite encode plus normal kernel, monitor overhead, 1/2/6 channels, all native rates; compare identical legacy/candidate analysis settings.

**Completion:** Qualified profile manifests identify actual passed tests; failure of the selected candidate blocks promotion and preserves evidence rather than triggering a hidden substitute. Routing/count/overload tests pass.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. Use exact-rate sdm-8 with mastering64 P/S/R=20k/40k/88.2k, mastering128=30k/60k/176.4k and mastering256=40k/80k/176.4k. Prefilter is at R, not 2R. Ordinary PCM scales by .5, while DSD-origin auto remodulation preserves its reference amplitude. Nominal DSD-domain input peak is .5 plus the defined representation margin; interpolation overload fails rather than clips. If qualification fails, return the failing evidence and an unpromoted profile, not a false completion.

**Risks:** Clipping interpolation before SDM and calling it stable; accepting huge finite state; changing an NTF/rate silently; hiding failed candidate tests behind an experimental label.

**Out of scope:** Trellis defaulting, automatic reset/normalization, unqualified wideband encoding, higher native rates and default release activation.

**Fresh-session SOW:** `sows/P10.md`.


## P11: Introduce runtime kernels and retain scalar SSE2 AVX1

**Dependencies:** P00-P10.

**Objective and requirements:** Runtime framework; scalar oracle; retained AVX1 compatibility; per-context ISA selection; baseline FP and ownership.

**Read:** DSD_DESIGN section 8; src/sdm_x86.h; scalar decoder/encoder kernels; configure.ac; src/Makefile.am; effect per-channel scheduling.

**Existing files/components:** configure.ac; src/Makefile.am; src/sdm.c and sdm_x86.h extraction; decoder kernel calls; no unrelated global compiler changes.

**New files/components:** src/dsd_kernels.h; src/dsd_dispatch.c; scalar/SSE2/AVX1 translation units; CPU capability mock tests and instruction-isolation tests.

**Implementation:** Introduce block vtables and one-time context dispatch. Keep scalar universally compiled. Port existing SSE2 and AVX1 SDM arithmetic into isolated block kernels; add corresponding FIR implementations. Detect CPU plus OS state correctly. Provide independent FIR/SDM force hooks and clean unsupported-tier errors. Unknown CPUs select SSE2 or scalar conservatively. Preserve existing thread ownership and no hot-loop indirect calls.

**Unit acceptance:** CPUID/XGETBV decision matrix, absent leaves, unsupported forced tiers, independent contexts, aligned/unaligned inputs and bounded tails, negative-zero behavior.

**Integration/known-answer acceptance:** Run forced scalar/SSE2/AVX1 on supported hardware and an AVX-without-AVX2 environment; baseline executable starts without AVX; native container tests unchanged.

**Numerical acceptance:** FIR scalar/high-precision tolerance and one-LSB graph bound; analysis-v1 SDM gain/residual/spur/state equivalence; within-kernel buffer/thread byte invariance.

**Benchmarks:** FIR first, then SDM, with production guards; per-tier and end-to-end timings including AVX1 versus SSE2; no assumed preference from ISA width.

**Completion:** AVX1 remains genuinely compiled and independently runnable without AVX2; dispatcher cannot execute unsupported state/instructions; all available numerical checks pass.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. AVX1 is a required compatibility tier, not an alias for an AVX2 build. Compile its unit with AVX but without AVX2/FMA. Check OSXSAVE before XGETBV and XCR0 XMM/YMM support before AVX. Selection is per family/context. SDM cross-ISA validation is spectral/state based, not a raw DSD hash test.

**Risks:** Global -mavx flags leaking into startup/scalar code; LTO cross-target inlining; state pointers copied between channel flows; claiming hardware performance from CPUID masking.

**Out of scope:** AVX2/AVX-512 implementation, FMA defaults, global graph packing and new profile arithmetic.

**Fresh-session SOW:** `sows/P11.md`.


## P12: Add genuine baseline AVX2 kernels

**Dependencies:** P00-P11.

**Objective and requirements:** Required AVX2 FIR and normal SDM; optional separately qualified AVX2+FMA; performance-backed preferences.

**Read:** DSD_DESIGN sections 8 and 10.6-10.7; dsd_kernels.h; AVX1/SSE2 kernels; dispatcher and existing numerical/benchmark harness.

**Existing files/components:** configure.ac; src/Makefile.am; src/dsd_dispatch.c; kernel registry.

**New files/components:** src/dsd_kernels_avx2.c; optional separate AVX2-FMA unit; assembly and benchmark evidence.

**Implementation:** Implement AVX2 full-width lane-permutation window assembly for FIR and state-neighbor/reduction work for normal SDM. Maintain canonical coefficient order where practical. Keep a no-FMA baseline with contraction off. Add optional FMA only as a separate descriptor after its own tests. Update preference entries only for measured CPU/workload classes.

**Unit acceptance:** All tap counts/orders, odd frame counts, channel wrappers, unaligned input/tails, unsupported force behavior, FMA capability separation.

**Integration/known-answer acceptance:** Forced AVX2 on an AVX2 host; forced AVX1 still independent; all DSD correctness and automatic routing tests; baseline non-AVX startup unchanged.

**Numerical acceptance:** Full FIR tolerance and analysis-v1 cross-ISA SDM suite; no new spur/stability/clipping regression; within-kernel invariance; separate FMA results if present.

**Benchmarks:** AVX2 versus scalar/SSE2/AVX1 kernels and 64/128/256 end-to-end conversions; verify benefit with monitor overhead included; report assembly without treating instruction count as speed.

**Completion:** A genuine AVX2 algorithm is delivered and forceable; no-FMA baseline remains; preference only changes where benchmark gates support it.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. Use AVX2-specific data movement, not only a compiler flag. SIMD parallelizes independent FIR outputs or SDM state coordinates, never independent time lanes in one recurrence. Required baseline AVX2 cannot depend on FMA. It may lose to another tier on a CPU class; availability and performance preference are separate.

**Risks:** Shipping AVX1 code under -mavx2 as the entire deliverable; accidental contraction; optimizing recurrence across dependent time samples.

**Out of scope:** AVX-512, unrelated generic rate optimizations, coefficient/default changes and automatic startup calibration.

**Fresh-session SOW:** `sows/P12.md`.


## P13: Add baseline AVX-512 and qualify its selection

**Dependencies:** P00-P12.

**Objective and requirements:** Required AVX-512 FIR/SDM; optional separate FMA; Intel/AMD comparison without AVX1/AVX2 regression.

**Read:** DSD_DESIGN sections 8 and 10.6-10.7; AVX2 kernels, dispatcher feature masks and profile qualification suite.

**Existing files/components:** configure.ac; src/Makefile.am; src/dsd_dispatch.c; kernel registry.

**New files/components:** src/dsd_kernels_avx512.c; optional separate AVX-512-FMA unit; vendor/workload benchmark results.

**Implementation:** Implement eight-output FIR vectors and an eight-coordinate SDM kernel with bounded tails/masks. Declare every required ISA subset and match compiler flags/detection to it. Require XCR0 0xE6 for ZMM/opmask state. Keep noncontracted baseline arithmetic. Benchmark versus AVX2 including full conversion and frequency effects. Add preference entries only when supported by actual host evidence.

**Unit acceptance:** Subset/OS-state masks, incomplete XCR0, all orders/tap counts, short buffers, masked tails, independent FMA forcing and baseline isolation.

**Integration/known-answer acceptance:** Force AVX-512 only on capable hosts; rerun scalar/SSE2/AVX1/AVX2 coverage; all automatic and native operations remain correct.

**Numerical acceptance:** FIR envelope and analysis-v1 SDM equivalence, startup/end behavior, state guards and noise bands; optional FMA separately.

**Benchmarks:** Intel AVX-512 and AMD AVX-512 when available; kernel and end-to-end comparisons with AVX2, single/multithread and short/long files; record missing hardware explicitly.

**Completion:** Genuine AVX-512 is independently available without making the executable require it; a slower AVX-512 path is not chosen merely because it exists.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. AVX-512 baseline is required but need not win dispatch. Preserve the entire scalar/SSE2/AVX1/AVX2 matrix. Check CPU features and OS extended-state support. Do not claim Intel coverage from an AMD VM or vice versa. A missing hardware run is an open gate, not proof of a kernel defect or proof of success.

**Risks:** Hidden AVX-512DQ/BW/VL use; wider recurrence reduction changing quality; AVX frequency penalties concealed by kernel-only benchmarks.

**Out of scope:** Removing lower tiers, automatic highest-ISA policy, untested FMA preference, ARM SIMD and future-rate enabling.

**Fresh-session SOW:** `sows/P13.md`.


## P14: Publish stable DSD statistics and conversion reports

**Dependencies:** P00-P13.

**Objective and requirements:** User-visible QA, profile/kernel provenance, level/modulation/stability/band energy and failed-conversion status.

**Read:** DSD_DESIGN sections 9 and 10.2; existing internal stats/profile certificates; src/sox_ng.c error/output handling; native analysis effect registration.

**Existing files/components:** src/sox_ng.c; decode/encode report plumbing; help/manpages; build/effect registration.

**New files/components:** src/dsd_stats.c; src/dsdstat.c; versioned JSON schema and golden reports; independent digital measurement-filter tests.

**Implementation:** Expose stable report fields and actual selected IDs. Implement bit-preserving dsdstat and optional -a spectral/level analysis on original native bits. Keep basic required counters independent of expensive analysis. Label SACD-style digital filters separately from exact bit-window statistics. Handle output/report stream conflicts, errors, cancellation, unknown values and integer counters without corrupting audio.

**Unit acceptance:** JSON validity and schema evolution, null/large integer fields, window continuity, report status, filename/stdout policy, stable ordering and first-event indices.

**Integration/known-answer acceptance:** Native pass-through bit hash with/without dsdstat; completed/failed/clipped/overloaded/DoP reports; quiet versus verbose operation; no audio contamination.

**Numerical acceptance:** Independent SOS transfer and averaging tests; known-level/band-energy sources; original native ultrasonic energy not measured after a bandwidth-limited mastering decoder.

**Benchmarks:** Basic-counter overhead and optional full-analysis overhead separately; do not disable required guards to improve benchmarks.

**Completion:** Reports describe what actually ran and whether it completed; spectral labels/units are unambiguous; all analysis is observational and cannot alter samples.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. The report must contain actual profile/coefficient/kernel identities, source/effective bandwidth, level mapping, counts/latency, clipping and stability events. dsdstat never replaces native samples with reconstructed PCM. Native 40-100 kHz analysis must observe native input independently, not a mastering output that intentionally suppresses that band.

**Risks:** Conflating dBFS/dB SACD; NaN JSON; recording requested instead of actual ISA; measuring removed ultrasonics from the wrong point in the chain.

**Out of scope:** GUI, telemetry service, audio normalization/reset, formal SACD hardware certification and proprietary converter claims.

**Fresh-session SOW:** `sows/P14.md`.


## P15: Close release qualification and migrate automatic defaults

**Dependencies:** P00-P14.

**Objective and requirements:** Full first-release acceptance; compatibility migration; honest hardware/quality claims and default promotion.

**Read:** Entire DSD_DESIGN and IMPLEMENTATION_PLAN; every phase handoff; profile/dispatch certificates; existing manpages and generic test suite.

**Existing files/components:** Default selection/version aliases and release documentation only, plus tightly scoped fixes supported by failed acceptance evidence.

**New files/components:** docs/dsd/QUALIFICATION.md; release result manifest; migration guide; final CPU preference entries backed by measurements.

**Implementation:** Run the complete correctness, 3x9x2 reconstruction, encoder, cross-ISA and benchmark matrices. Execute/collect required long-run and hardware tests. Verify old generic PCM and explicit legacy commands. Resolve all named gaps required for advertised features. Promote qualified mastering/auto defaults and versioned aliases only when gates close. Keep correctness-only release notes separable if DSP qualification is still blocked.

**Unit acceptance:** Default/alias selection, reference-level preservation and supported capability bits; no stale xfails for closed defects; option conflict/error messages.

**Integration/known-answer acceptance:** End-to-end examples, headers/layout, nonlinearity, input adapters, native repacking, DoP and representative non-DSD workflows under final defaults.

**Numerical acceptance:** All profile envelopes/counts/stability/metrology/cross-ISA requirements; long-duration holdout/soak evidence; no vendor-equivalence assertion without matched executable tests.

**Benchmarks:** Full hardware matrix and declared performance targets; verify dispatch preferences and unchanged-path regression limits with confidence intervals.

**Completion:** Every advertised first-release feature has a passing evidence ID; defaults match certified profiles; missing mandatory evidence leaves promotion blocked and is reported.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. The first release is DSD64/128/256 with PCM through705.6 kHz, two decode profiles and qualified mastering encoding. Scalar/SSE2/AVX1/AVX2/AVX-512 remain forceable where supported. No silent +6 dB, limiter, reset, coefficient fallback or highest-ISA selection. A skipped required test does not close this phase.

**Risks:** Declaring completion from the design-session build; accepting an unrun host test; promoting a failed encoder candidate; release notes hiding changed domain or level semantics.

**Out of scope:** DSD512/1024 writes, new subjective claims, broad architecture cleanup and unsupported hardware certification.

**Fresh-session SOW:** `sows/P15.md`.


## P16: Add a packed first-stage DSD input extension

**Dependencies:** P00-P15.

**Objective and requirements:** Future-rate memory traffic without changing the generic SoX graph; packed/expanded parity and shared cursor ownership.

**Read:** DSD_DESIGN sections 3, 4 and 12.1; native reader caches; input adapters; scalar/ISA FIR front ends.

**Existing files/components:** src/dsf.c; src/dsdiff.c; src/dsd_decode.c; src/sox_ng.c input adapter; private format dispatch and optional public packed decoder API.

**New files/components:** Packed block descriptor and reader/decoder entry points; packed parity/bit-offset/traffic benchmarks.

**Implementation:** Expose borrowed packed blocks with explicit layout/stride/order/valid-bit count. Restrict each handle to one access mode until reset/seek. Share one logical cursor/cache and preserve normal expanded API behavior. Decode early stages directly from packed data into bounded floating workspace, first with a simple reference implementation. Reuse downstream profile/count contracts. Benchmark before adding byte-contribution tables or extra vector packing.

**Unit acceptance:** Borrow lifetime, mode transition rejection/reset, all bit offsets, DSF planar versus DFF clustered layouts, last partial byte, seek cursor once-only accounting.

**Integration/known-answer acceptance:** Packed versus expanded 64/128/256 conversions under every profile/rate/ISA; native I/O still unchanged; no extra block padding decoded as audio.

**Numerical acceptance:** Same finite operator, phase/count and defined FIR tolerance; independently check first-stage contribution tables if implemented.

**Benchmarks:** Measure payload traffic, peak RSS and end-to-end improvement at256 and simulated512/1024 clocks with descriptors still unenabled for writing.

**Completion:** Packed input is optional, bounded and parity-tested; generic effects still consume the existing representation; higher-rate writing remains disabled.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. This is an input/first-stage extension, not a SoX sample-type rewrite. Reader owns borrowed bytes until its next block call; decoder must consume/copy first. Packed and expanded APIs share one logical position and may not be interleaved without reset. The required output is numerical/count parity and measured traffic reduction, not new writer rate checkboxes.

**Risks:** Confusing DSF memory layout with DFF clusters; double-advancing olength; a packed optimization silently changing phase/tails.

**Out of scope:** Full packed effects graph, higher-rate modulator assumptions, automatic writer enablement and speculative transport support.

**Fresh-session SOW:** `sows/P16.md`.


## P17: Design and qualify DSD512 and DSD1024 DSP

**Dependencies:** P00-P16.

**Objective and requirements:** Exact-rate high-rate reconstruction and modulation; independent reference corpus and future state/traffic validation.

**Read:** DSD_DESIGN sections 7, 10 and 12; existing profile/certificate generator; exact-rate SDM registry; packed engine.

**Existing files/components:** src/dsd.c descriptors; coefficient manifests; decode/encode profile registry and tests; writer capability bits remain disabled.

**New files/components:** 512/1024 reconstruction banks and delay manifests; explicit high-rate SDM coefficient/profile records; independent corpus and qualification results.

**Implementation:** Implement planned mastering P40k/S80k/R176.4k and wideband R=Fs/32, P=.4R/S=.5R. Regenerate all delay/alias/count evidence. Derive or rigorously justify exact-rate SDM coefficients and state scaling rather than inherit256. Validate interpolation/envelope/guards and independent spectra/corpus. Keep public higher-rate output capability disabled until container/transport qualification in P18.

**Unit acceptance:** Strict registry rejection of absent profiles; uint64 count extremes; additional stage phases; output intersection including1024wide->705.6k; state initialization/guards.

**Integration/known-answer acceptance:** Internal/explicit experimental512/1024 decode/encode and packed parity; all64/128/256 regressions; reference interoperability input checks.

**Numerical acceptance:** Full response/alias/baseband/wideband/state/soak matrix at22.5792/45.1584MHz; cross-ISA qualification; higher-rate28-bit statistic labeled diagnostic only.

**Benchmarks:** Throughput/memory traffic1/2/6channels; expanded versus packed front end; native encoding kernel costs and sustained operation.

**Completion:** Rate-specific DSP has independent evidence and versioned certificates, or remains explicitly unqualified with no writer enablement.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. DSD512=22579200Hz and1024=45158400Hz. New DSP must not select256 coefficients by a less-than-or-equal lookup. Wide1024 has1.4112MHz internal PCM and a564.48kHz passband; a705.6kHz output cannot preserve that whole band. Missing independent corpus/qualification means disabled capability, not fabricated success.

**Risks:** Treating higher rate as a constant change; unproven coefficient normalization; measured wideband response mistaken for proven source information.

**Out of scope:** Production file/DoP writer enabling, new PCM rate promises beyond the stated output matrix and inherited SACD normative claims.

**Fresh-session SOW:** `sows/P17.md`.


## P18: Enable only qualified higher-rate files and transports

**Dependencies:** P00-P17.

**Objective and requirements:** Container-specific512/1024 capabilities; explicit DoP rates; interoperability and release claims.

**Read:** DSD_DESIGN sections 4.5 and12;512/1024 DSP certificates; DSF/DSDIFF/DoP primary specifications and actual destination handler capabilities.

**Existing files/components:** DSF/DFF writer capability lists; DSD capability registry; DoP preflight; help/manpages/release notes.

**New files/components:** High-rate format/transport fixture matrix, compatibility ledger and capability-specific release manifest.

**Implementation:** Enable a capability only for its passed DSP and format pair. Document DSF high-rate ecosystem extensions and DFF general versus Edited Master constraints. Validate uint32 rates, uint64 lengths, padding, layouts and round trips. Require DoP1.4112/2.8224MHz transport for512/1024 and reject unsupported negotiation. Collect independent software/player evidence; distinguish file validity from physical device support.

**Unit acceptance:** Per-container/per-operation capability gates; transport-rate arithmetic; unsupported output failures; long-duration size/accounting.

**Integration/known-answer acceptance:** Independent512/1024 files and software round trips; packed/expanded paths; high-rate DoP payload/marker/tail vectors; hardware tests only for claimed devices.

**Numerical acceptance:** Reuse passing P17 DSP certificates without changing coefficients; verify format/transport does not alter native program bits or counts beyond declared completion.

**Benchmarks:** End-to-end high-rate file/transport throughput, memory and storage traffic; no regressions to the qualified64/128/256 release.

**Completion:** Each enabled capability has a complete evidence chain; unverified transports/devices stay unsupported or explicitly unclaimed; documentation matches the actual gates.

**Regression constraints:** Preserve all prior accepted DSD and generic tests; confine behavior changes to this phase. A rate field fitting in a container is not sufficient support. DSP, native file writing and DoP transport are separate gates. DoP512 requires1.4112MHz PCM and DoP1024 requires2.8224MHz. Keep unsupported pairs disabled and return a concrete capability error; do not silently down-rate or substitute coefficients.

**Risks:** A writer allow-list change outrunning DSP qualification; calling a general DFF a SACD Edited Master; hardware claims based only on byte packing.

**Out of scope:** Universal DAC support, unmeasured subjective superiority, a new transport framing scheme and unrelated container redesign.

**Fresh-session SOW:** `sows/P18.md`.

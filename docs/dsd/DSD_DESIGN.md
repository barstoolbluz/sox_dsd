# sox_ng DSD engine: implementation specification and refactoring contract

**Design revision:** 1.0, 2026-10-07  
**Source baseline:** `16aa7e17531dd3612f29247da98c8ea570cd905a`  
**Status:** implementation-ready architecture, algorithms, interfaces, acceptance contracts and phase instructions. This is not an implemented or release-qualified converter.  
**Scope:** DSD engineering, fidelity, interoperability, performance and production diagnostics. No security assessment.

## Reading and implementation order

Read this specification, then `IMPLEMENTATION_PLAN.md`, then the SOW for the next permitted phase. The combined handoff contains all three. The files under `evidence/` record tests actually performed during this design session; they are not a substitute for the implementation phases' acceptance tests.

The first release consists of P00–P15 and supports DSD64, DSD128 and DSD256. P16–P18 are a separately gated extension for packed input, DSD512 and DSD1024. Do not advertise the extension as present merely because the type system can represent its rates.

Requirements marked **MUST** are release conditions. Numerical specifications below distinguish a designed transfer-function requirement from a measured property of a particular recording. Neither a filter's stopband nor a sigma-delta modulator's performance on one tone establishes an end-to-end noise floor for arbitrary DSD material.

# 1. Evidence, corrections and decisions

## 1.1 What was examined and executed

The attached source archive has SHA-256 `c50f7f53fb53dd54467028abe310d29001262b7d37cc58c0f0937bae105604e0`. The attached handoff has SHA-256 `5ff94e9815fd1eae76a4cb4193dca7133cadf2a074d5d866b7badc994e7c4c77`. Its filename says v3, while its internal revision banner still says v2. This specification identifies the input by hash and does not infer an unrecorded revision history.

A fresh extraction was built with GCC 14.2.0 using:

```sh
autoreconf -fi
./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'
make -j3
make check
```

All four commands completed successfully. The generic suite includes VOID cases; this result is not a claim that every optional format was exercised. The build lacked optional FLAC, Opus, WavPack, Vorbis, libsndfile and MP3 development dependencies. OpenMP was enabled. The host exposed five virtual CPUs of an AMD EPYC 9V74 under KVM, with AVX, AVX2 and AVX-512 features. That environment establishes neither AVX1-only hardware performance nor Intel AVX-512 behavior.

The design review read the DSD handlers, DoP, sigma-delta code, rate engine and half-band kernels, effect construction/cloning, the input combiner, output opening, generic seek/read bookkeeping and relevant non-DSD seek implementations. Evidence is anchored to the baseline's named functions; line numbers are useful for the baseline, not a requirement that later patches retain them.

Four executable evidence sets accompany this document:

* `reproduce.py`, `probe_io.c`, `reproductions.json`: independently constructed format/seek fixtures and short C API reproductions.
* `probe_filters.py`, `candidate_filter_coefficients.npz`, `filter_feasibility.json`: binary64 filter-design feasibility and sampled frequency-response calculations. These are candidate coefficients, not the release coefficient authority.
* `probe_sdm.c`, `sdm_short_stress.json`: 192 short scalar recurrence tests, each 0.125 second. They bypass PCM interpolation deliberately and cannot establish mastering-profile stability.
* `probe_remodulation.py`, `remodulation_level.json`: a baseline ordering/level experiment showing why the new remodulation plan must carry the DSD reference level rather than blindly apply ordinary PCM half scaling.

## 1.2 Verified baseline findings and additional findings

**Confirmed defects, retained from the handoff.** `dff_writeheader` double-counts audio in FRM8, includes the C terminator in the CMPR name length, and `dff_stopwrite` fails to count a final completed audio cluster or add an external odd-payload pad. The DSF/DFF/WSD read interfaces can fail to progress on small legal capacities. DSF rejects standardized MSB-first storage. Native DSD seek handlers interpret an interleaved offset as a per-channel offset. Core `sox_seek` leaves `olength` stale. Interactive seek callers pass wide-frame counts without multiplying by channel count. DSF Type 5 becomes Type 4 in a four-channel round trip. DSDIFF channel identity is discarded. See `src/dsf.c`, `src/dsdiff.c`, `src/formats.c:1415–1428,1510–1521`, and `src/sox_ng.c` interactive seek paths.

The fresh reproductions confirm the handoff's DFF/MANF root-cause correction: after a seek eight samples into a 128-sample mono file, the uncorrected API can return 128 samples. Correcting the logical position yields the proper remaining 120. **Do not add a second DFF remaining-audio counter to cure this symptom.** A cached byte/cluster and parser chunk extents have separate purposes and are still necessary.

**Additional confirmed defect D1: first DFF output cluster uses uninitialized accumulator bytes.** `dff_startwrite` allocates `dff->buf` with `lsx_malloc`; `dff_write_bits` ORs into it; clearing occurs only after `dff_write_buf` writes the cluster. Under `MALLOC_PERTURB_=85`, a requested all-zero first channel byte becomes `0xaa`. This affects ordinary bit chronology, not merely header validity. Zero-initialize the accumulator before the first write. Prior bit-preservation results were allocation-dependent and are insufficient to declare this writer sound. The reproducer covers mono and multiple channel counts.

**Additional confirmed defect D2: WAV maintains stale private remaining-sample state after seek.** The uncompressed branch of `seek_wav` subtracts the requested frame position from the current `wav->numSamples`, rather than resetting it from the stream's total frame count. Reading eight frames from a 441-frame WAV and rewinding permits only 433 frames afterward, even when the probe corrects `ft->olength`. Fix the private counter as part of the seek-contract phase; fixing only core bookkeeping is insufficient. The GSM branch's coarse seek and decoder state also require a targeted test. See `src/wav.c:2135–2170`.

**Confirmed architectural limitation A1: the boundary is earlier than `add_effects`.** `balance_input` can apply input volume/replay gain to native one-bit pulses, and the input combiner can mix, multiply or insert numeric zero padding before user effects. Merely prepending a DSD effect inside `add_effects` does not repair these operations. Per-input conversion adapters are required for those cases. See `progress_to_next_input_file`, `balance_input`, `combiner_start`, `combiner_drain` and `sox_read_wide` in `src/sox_ng.c`.

**Confirmed architectural limitation A2: headers open before effect execution.** `process` calls `open_output_file` before `add_effects`. Layout and domain planning must happen before opening the output. Do not discover a layout loss after a DSF or WAV header has already encoded the wrong speakers.

**Confirmed architectural limitation A3: public graph samples remain int32.** A floating-point output container does not make the effects graph floating-point. The new local DSD engine can preserve binary64 values, but a normal CLI chain clips values outside the graph range before the writer. This release explicitly documents that limit instead of promising over-0 dBFS preservation it cannot deliver.

**Additional verified design constraint A4: level reference must survive remodulation.** In a baseline 1 kHz experiment, explicit reconstruction to 88.2 kHz, `gain -3`, and re-interpolation/modulation produced about -9.02058 dB relative to the source, not -3 dB. Ordinary PCM-to-DSD half scaling was applied to PCM that already represented theoretical DSD amplitude. The old direct pulse-domain gain path performed much worse in this particular test, which corroborates the known ordering limitation but is not a general quality benchmark. The new planner must retain a level-reference tag and use a unit-preserving remodulation scale. This is not permission for hidden +6 dB in DSD-to-PCM output. See `remodulation_level.json` and section 5.4.

**Validated behavior, with the DFF writer qualification above.** DSF logical-bit chronology and DSD container bit-order reversal have useful existing implementations. DoP's documented payload/marker convention is retained. The intentional PCM-to-DSD factor of 0.5 is retained. Cross-ISA sigma-delta byte differences alone are not defects. Generic `rate` remains a capable PCM resampler. It is the implicit bandwidth/domain policy, not a demonstrated universal SRC-quality defect, that this project changes.

## 1.3 Architecture selection

Select a **dedicated DSD reconstruction/decimation front end followed, when needed, by a private binary64 adapter to the existing `rate` backend**.

A dedicated front end gives explicit source bandwidth, predictable linear-phase state, a narrow kernel interface, and a future packed-input entry point. It avoids processing the highest-rate stages with the current generic scalar half-band loop. It does not require a second arbitrary-ratio resampler.

Staging the public `rate` effect through a selected intermediate rate remains a valuable comparison implementation and legacy option. It is not the production architecture: it introduces a graph-level int32 boundary, hides filter/state policy in a general-purpose effect and does not provide the desired packed front end or isolated runtime kernels. A DSD-aware mode inside `rate` would reuse code but couple source semantics, transport and DSD profile policy to a generic PCM component. The thin adapter is the smaller long-term boundary.

The candidate FIR designs satisfy sampled feasibility checks with substantial margin over the proposed public response envelope. No new-engine speedup has been measured. Performance remains an implementation gate, not a conclusion inferred from register width or coefficient count.

## 1.4 Fixed release decisions

The release defaults to conservative, source-aware **mastering** reconstruction; **wideband** is explicit. High PCM output rates never expand a profile's source bandwidth. Default level is **preserve**, with no automatic +6 dB. The graph remains int32; DSD-only internals use binary64. Normal conversion is not cross-CPU byte-deterministic sigma-delta encoding. Scalar, SSE2, AVX1, AVX2 and AVX-512 are independently selectable implementation tiers. FMA is separate and optional. There is no silent limiter, normalizer, modulator reset, profile downgrade or unsupported-rate coefficient substitution.

The selected mastering encoder candidate is the existing rate-specific **`sdm-8`** family, with a specified band-limited interpolation path and a fail-on-overload contract. It becomes a released/default profile only after P09/P10 qualification. This is a concrete algorithm selection with a falsifiable gate, not a claim that the existing coefficients are already qualified. Failure blocks promotion; it must not silently select another filter by table order.

# 2. Rates, domains and capability model

## 2.1 Rate descriptors

Represent native sample rates as integer Hz in DSD code. Define descriptors for 2,822,400; 5,644,800; 11,289,600; 22,579,200; and 45,158,400 Hz. Each descriptor contains the 44.1 kHz-family multiplier, rate name, reconstruction profile references, encoding profile references and independent capability bits:

```c
enum lsx_dsd_capability {
  LSX_DSD_READ_NATIVE = 1u << 0,
  LSX_DSD_WRITE_NATIVE = 1u << 1,
  LSX_DSD_RECONSTRUCT = 1u << 2,
  LSX_DSD_MODULATE = 1u << 3,
  LSX_DSD_DOP = 1u << 4
};
```

Capabilities are additionally constrained by the selected container/transport. DSD512/1024 descriptors exist before their capability bits are enabled. An encoder lookup requires **exact rate, exact profile version and exact coefficient identity**. Remove `freq <= requested_freq` fallback from the new path. Existing nonstandard-rate low-level `sdm` behavior is preserved only in explicit legacy mode, with a diagnostic naming the actual coefficient rate; it must not enable a native writer at that rate.

No new 48 kHz-family DSD support is implied. Native readers that currently accept other structurally valid integer rates may still expose their bits for inspection, but automatic reconstruction/modulation without a profile is rejected. This avoids changing a permissive format parser into an undocumented DSP guarantee.

## 2.2 Domains

Use an explicit private enum: `DSD_NATIVE`, `PCM_AUDIO`, `DOP_TRANSPORT`. Precision is a property of a representation, not a sufficient domain tag. `eff->in_encoding` and `eff->out_encoding` describe chain endpoints in the current engine and are not a reliable per-node domain state.

A private PCM level-reference tag accompanies the domain plan: ordinary PCM full-scale reference or a DSD-origin reference with its explicit decoder gain. This metadata is not a new sample type and does not alter public effect structs.

The normal graph representation of native DSD remains one `sox_sample_t` per DSD bit, interleaved by channel: logical one is `+SOX_SAMPLE_MAX`, logical zero is `-SOX_SAMPLE_MAX`. Numeric zero is not a valid native bit or a DSD silence sample. Native operations must never introduce it as padding.

Use **frame** exclusively for one chronological sample from every channel. Public `sox_read`/`sox_write`/`sox_seek` retain interleaved-sample units. New DSD DSP interfaces use **per-channel frame units**. A DFF clustered frame is explicitly named a **byte cluster**, consisting of one byte per channel and eight chronological DSD frames. Do not overload `sample` or `frame` in state fields.

## 2.3 PCM output coverage

Both reconstruction profiles MUST support 44,100; 48,000; 88,200; 96,000; 176,400; 192,000; 352,800; 384,000; and 705,600 Hz, subject to the destination handler's independent capability. The fresh build successfully wrote 352.8/705.6 kHz float WAV; that is not evidence for every codec. PCM-to-DSD testing includes sources through 705.6 kHz, with intentional profile bandwidth limitation.

Rates are validated before opening an output. A filename extension is not proof of capability. No silent rounding to a nearby container-supported rate. The report distinguishes requested rate, actual rate, selected intermediate rate and effective bandwidth.

# 3. Modules, API boundaries and ownership

## 3.1 Module map

Add `src/dsd.h` and `src/dsd.c` for private descriptors, profile lookup, checked frame arithmetic and status types. Add `src/dsd_layout.c` for DSD layout conversion and the bounded WAV bridge. Add installed `src/sox_dsd.h` for additive opaque APIs, without enlarging `sox_signalinfo_t`, `sox_oob_t`, `sox_format_t` or `sox_effect_handler_t`.

Add `src/dsd_decode.c` for the multistage reconstruction context, `src/dsdpcm.c` for the explicit effect, `src/pcmdsd.c` for composite encoding, and `src/dsd_plan.c` for a private CLI planning helper. Keep CLI input-adapter glue in `src/sox_ng.c`; do not create a general replacement effects engine.

Add `src/rate_internal.h`; implement its opaque binary64 adapter in `rate.c` beside the existing static backend. The public `rate` effect's option parsing, LPC boundary extrapolation and existing outputs remain unchanged. The DSD adapter chooses its own zero-boundary behavior and explicit counters.

Add `src/dsd_kernels.h`, `src/dsd_kernels_scalar.c`, `src/dsd_kernels_sse2.c`, `src/dsd_kernels_avx1.c`, `src/dsd_kernels_avx2.c`, `src/dsd_kernels_avx512.c` and `src/dsd_dispatch.c`. Optional FMA variants have separate names and build flags. Add `src/dsd_stats.c` and `src/dsdstat.c` for diagnostics. Generated immutable coefficients live in `src/dsd_coeffs.h` with a checked-in machine-readable manifest under `tests/dsd/reference/`.

Keep existing `sdm.c`, `sdm.h`, `sdm_x86.h`, `dither.c`, `dsf.c`, `dsdiff.c`, `dop.c` and `wav.c` as the integration points. Extract only the normal SDM state kernel needed by dispatch. Trellis does not dictate the new normal encoder's allocation layout.

## 3.2 Public additive interface

Use `size` and `version` fields on new public option/result records, accepting a known prefix and rejecting unsupported semantic versions. Unknown enum values are errors. Contexts are opaque. The following signatures specify the API shape; normal export/calling-convention annotations from `sox_ng.h` apply.

```c
typedef struct sox_dsd_decoder sox_dsd_decoder_t;
typedef struct sox_dsd_layout sox_dsd_layout_t;
typedef struct sox_dsd_decode_options sox_dsd_decode_options_t;
typedef struct sox_dsd_stream_info sox_dsd_stream_info_t;
typedef struct sox_dsd_report sox_dsd_report_t;

typedef enum {
  SOX_DSD_OK = 0, SOX_DSD_NEED_INPUT, SOX_DSD_NEED_OUTPUT,
  SOX_DSD_DONE, SOX_DSD_BAD_ARGUMENT, SOX_DSD_UNSUPPORTED,
  SOX_DSD_IO_ERROR, SOX_DSD_NUMERIC_ERROR
} sox_dsd_status_t;

sox_dsd_status_t sox_dsd_get_stream_info(
    const sox_format_t *ft, sox_dsd_stream_info_t *info);
sox_dsd_layout_t *sox_dsd_layout_copy(const sox_dsd_layout_t *src);
void sox_dsd_layout_free(sox_dsd_layout_t *layout);
sox_dsd_status_t sox_dsd_get_layout(
    const sox_format_t *ft, sox_dsd_layout_t **owned_copy);

sox_format_t *sox_open_write_dsd(
    const char *path, const sox_signalinfo_t *signal,
    const sox_encodinginfo_t *encoding, const char *filetype,
    const sox_oob_t *oob,
    sox_bool (*overwrite_permitted)(const char *filename),
    const sox_dsd_layout_t *layout);

sox_dsd_status_t sox_dsd_decoder_create(
    const sox_dsd_decode_options_t *options,
    sox_dsd_decoder_t **out);
sox_dsd_status_t sox_dsd_decoder_process(
    sox_dsd_decoder_t *ctx, const sox_sample_t *interleaved_bits,
    size_t *input_frames, double *interleaved_pcm,
    size_t *output_frames);
sox_dsd_status_t sox_dsd_decoder_finish(
    sox_dsd_decoder_t *ctx, double *interleaved_pcm,
    size_t *output_frames);
sox_dsd_status_t sox_dsd_decoder_report(
    const sox_dsd_decoder_t *ctx, sox_dsd_report_t *out);
void sox_dsd_decoder_destroy(sox_dsd_decoder_t *ctx);
```

`stream_info` contains integer native Hz, channel count, known-length flag and uint64 frame length, physical bit order, source container, original DSF channel type/DSDIFF LSCO presence where applicable, and capabilities. Layout contents are accessed by copy-out getters: count; channel role; original four-byte DFF ID and its validity; original container-specific layout value. Callers never dereference opaque layouts or retain pointers into a format handle.

`decode_options` contains size/version, source Hz, output Hz, channels, profile ID/version, preserve/sacd level mode, clipping/report policy and kernel override. An options initializer supplies documented defaults. Length can be unknown; final counts come from consumed input, not a possibly inaccurate hint. Returned double PCM is normalized to theoretical DSD amplitude and may exceed ±1. The library API does not silently clip it. CLI conversion to graph samples is a separate adapter with a visible clipping policy.

The new writer entry point has the existing open-write arguments plus layout. It calls the same private `open_write` implementation with optional DSD layout metadata installed in recognized handler-private state **before** `startwrite`. Existing entry points pass NULL and keep their ABI. Unsupported formats may use the new entry point only under the explicit metadata-loss policy already resolved by the caller. `sox_close` remains the matching close operation. Memory-output variants can be added by the same private parameter path only when tests require them; do not invent a global pending-layout singleton.

## 3.3 Internal streaming contracts

The mono engine used by SoX per-channel flows has equivalent internal functions with `double` output and native-bit input. The multichannel public decoder owns one mono context per channel and a bounded transpose buffer; the SoX effect must not instantiate that multichannel wrapper once per cloned channel.

On entry, `*input_frames` and `*output_frames` are capacities. On return they are actual consumed/produced counts. An output-capacity-zero call consumes no input and performs no state transition. A positive-capacity call may consume input without producing output while filling a filter; it cannot claim DONE before finish. NEED_INPUT/NEED_OUTPUT distinguish backpressure from EOF. `finish` is idempotent after DONE and does not accept more input. A failed context remains failed until destroyed. There is no public seek on a live DSP context in the first release; reset/recreation is explicit and discards state.

Each mono reconstruction context owns its ring histories, stage phases, counters, rate-adapter context and bounded output queue. Each encoder owns its prefilter/SRC, modulation state, previous decision and diagnostic counters. A descriptor or coefficient bank is immutable process-lifetime data. There is no mutable global current profile or current ISA.

Effect `getopts` stores plain configuration values only, or immutable shared descriptors. Allocate owning contexts in `start`, after SoX's per-channel cloning; free them in `stop`. `kill` frees only option-owned objects. The current `sox_add_effect` shallow-copies private option storage before starting each flow, so putting an allocated owning decoder pointer there during `getopts` would double-own it.

## 3.4 Rate backend adapter

```c
typedef struct lsx_rate_f64 lsx_rate_f64_t;
typedef struct {
  uint64_t input_hz, output_hz;
  double rejection_db;       /* 180 for DSD mastering paths */
  double bandwidth_0db_pct;  /* 95, not the public -b quantity */
  unsigned phase_percent;   /* 50: linear phase */
} lsx_rate_f64_config;
```

Provide create/process/finish/destroy functions with the same capacity convention. The adapter accepts a final output-frame limit at finish and must generate zero-padded filter support until that limit is satisfied, rather than stop at a rounded intermediate length. Counter overflow is an error. The caller supplies endpoint length only after EOF if unknown. No LPC extrapolation, int32 conversion, dither or automatic gain occurs in this adapter. Identity-rate operation copies doubles without a filtering stage.

Reuse the backend's filter generation, processing and coefficient sharing only with explicit ownership. Do not expose `rate_t` publicly or recompile a second copy by including `rate.c` from another production translation unit. The legacy wrapper is regression-tested against baseline output independently of the new adapter.

## 3.5 Fatal processing errors are not normal end-of-stream

The reviewed effects engine treats `SOX_EOF` as both an effect termination signal and an error-like status, and the CLI can continue another chain or ultimately return success. New mastering overload and strict clipping must not be implemented as `lsx_fail` plus ordinary EOF and assumed to produce a failed command.

Add a private `LSX_EFF_FATAL` return value, distinct from SOX_SUCCESS/SOX_EOF, in the internal effects contract. Only new DSD adapters/effects need to return it initially. In `flow_effect` and `drain_effect`, collect per-channel status with a proper reduction, check fatal status **before** interleaving, asymmetry handling or advancing output-buffer endpoints, and discard the whole current output block on fatal failure. Other channel states may already have advanced; the chain is failed and cannot resume, so no state rollback mechanism is needed. Ordinary EOF/trim behavior remains unchanged.

`sox_flow_effects` must stop immediately on this private fatal status and return failure without draining the failed stage into downstream output. No public struct or vtable layout changes. New DSD contexts latch their detailed error; a small private chain/adapter status query lets the CLI distinguish fatal DSD failure from user cancellation or normal early termination. The CLI must not turn that failure into success when another input/effect chain remains, and must return a nonzero exit status. This is a bounded effects-engine correction necessary for the new error contract, not a general effects API rewrite.

A new DSD command also checks output finalization: collect needed statistics, close the output exactly once, inspect `sox_close` status, clear its handle to prevent double close, then publish final success/failure and apply existing cleanup policy. An error writing the final DFF cluster/pad or seeking back to its header cannot be reported as a completed conversion. The report survives normal failure cleanup. Previously written stdout/file data cannot always be rolled back; never label such output complete. Input adapters distinguish a known-length DSD stream ending prematurely from a clean logical endpoint.

Tests use a synthetic fatal effect and real decoder-clip/encoder-overload cases in mono and six-channel, flow and drain, including a following effect chain. Assert nonzero CLI status, no failed-block samples reaching the output, no false Done report and no change to ordinary trim/EOF or unrelated PCM behavior.

# 4. Format and seek contract

## 4.1 DSDIFF writer

Centralize checked chunk-span arithmetic:

```text
span(n) = 12 + n + (n & 1)
CMPR data = 4-byte type + 1-byte count + 14 name bytes = 19 bytes
PROP data = 4-byte SND tag + sum(span(local_chunk_data))
FRM8 data = 4-byte DSD tag + sum(span(top_level_chunk_data))
```

The CMPR trailing zero is external pad, not text. Audio `ckDataSize` is exactly the number of byte-cluster bytes written, including one final silence-completed cluster if any logical bits remain. The mandatory odd audio pad is excluded from audio size but included in FRM8's physical accounting. Count each payload once. `dff_startwrite` clears its accumulator before any OR operation.

Preserve the current chronological 0x69 completion convention. DFF cannot record a non-multiple-of-eight per-channel logical bit count: converting a nine-frame DSF to DFF produces sixteen DSD frames, the last seven being explicit completion bits. The report records source logical frames and output completed frames separately. A subsequent DFF-to-DSF conversion cannot recover the original nine without extra metadata; do not claim otherwise. Empty streams receive an explicitly empty audio chunk and valid parent sizes, not fabricated program samples.

Readers tolerate an absent external pad only for pre-existing legacy files when the declared sound payload is complete and EOF is exactly at its end; warn once and never treat following metadata as audio. New writers always comply. No broad repair of arbitrary inconsistent headers is required. Strict structural tests use independently generated compliant chunks, not the broken writer as their oracle.

## 4.2 Retained read state

DSF state contains per-channel block storage, loaded-block index, byte index, bit index, chronological frame position and source bit order. Validate channel count, positive supported block size and checked required payload extent before multiplying sizes. Support standardized 4096-byte blocks; preserve any deliberately supported legacy block-size extension only with bounded, tested semantics and a diagnostic. For zero logical frames, require no audio block and return EOF without reading one.

Normalize MSB-first DSF bytes to the LSB extraction convention once per byte/block using a reversal table; the hot bit loop must not branch on source bit order. The byte's first decoded bit always means the oldest bit in time. An exact-end seek is legal and leaves the decoder at EOF without loading a nonexistent block.

DFF/WSD state holds a **cached byte cluster**, `cluster_valid`, bit index and the initial seek bit offset. A new cluster is read only after all eight chronological bits have been consumed. A legal call with capacity for one frame must return one frame whenever one remains. Requests with less than one full channel frame return zero without consuming data; the public API's interleaved capacity is rounded down to whole frames. This does not confuse a valid one-frame capacity with EOF.

DFF requires a sound payload divisible by channel count, not a minimum of eight bytes. A mono one-byte payload is valid. Parser state records required-field presence and enclosing FRM8/PROP extents, initializes fields before use, respects chunk physical padding and verifies skipped byte counts. That parsing state is not a duplicate read-position counter. Zero audio length is handled explicitly rather than depending on core's unknown-length sentinel. WSD uses the same byte-cache logic, but retains its own header/data-start rules and does not acquire a speculative interpretation of channel assignments.

## 4.3 Unified seek semantics

Retain the interleaved-sample API. For compatibility with existing multichannel PCM handlers, normalize a requested offset down to the containing complete frame:

```text
target_samples = offset - offset % channels
target_frame = target_samples / channels
```

Document this rounding; callers seeking a frame should already supply an aligned offset. Reject zero channel count, unrepresentable offsets and known-length out-of-range targets before moving the stream. A seek exactly to the logical end succeeds. Do not reinterpret offsets as bytes or native per-channel DSD bits at the public boundary.

Core calls the handler with `target_samples`; on success it sets `ft->olength = target_samples`. Core `sox_read` clamps with a checked/saturating remaining length and cannot underflow if position is at/past a known endpoint. Respect both unknown-length conventions actually used by the source rather than treating a sentinel as a huge valid length.

DSF and DFF/WSD divide by channel count before calculating block/byte/bit coordinates, clear cached input, and load or defer loading the correct byte cluster. Failed preflight seeks leave both file position and logical counters unchanged. I/O failures after a physical seek are reported as failures; no claim of transactional recovery from a failing underlying stream is made.

Reset WAV's private remaining frames from original total frames minus target, not from the remaining count after prior reads. For GSM WAV, seek to a decodable block at or before the target, reset decoder state and discard to the requested frame; do not return success for an undocumented rounded-up position. Audit raw/offset-seek, MSU PCM, PRC, SMP, FLAC, Opus, Vorbis and WavPack. FLAC's deferred decoder seek can retain a pending logical target only if its next read resolves that target before returning samples and propagates a seek failure; success must never expose samples from the previous decoder buffer. Add optional-codec tests when dependencies are present and record skips.

Interactive `>`/`<` paths convert wide frames to interleaved samples with checked multiplication and commit display/read counters only after success. `optimize_trim` retains its interleaved offset. No new actual-position field is required if all successful built-in handlers meet the normalized target contract; a handler that cannot do so must return unsupported, not fabricate success. Do not change `SOX_SEEK_CUR`/`END` support in this project.

## 4.4 Layout ownership and transformation

A layout contains an ordered channel vector with roles `UNKNOWN`, `MONO`, `FL`, `FR`, `FC`, `LFE`, `BL`, `BR`, `SL`, `SR`, plus original DFF IDs where available. Preserve the distinction between side and back speakers internally; where a source standard merely says surround, retain that source role/provenance rather than assert a physical angle. DSF's ordered types map to their documented layouts; Type 4 and Type 5 remain different despite both having four channels. [S1]

Store the original DSF type, DFF channel-ID vector and optional LSCO in the DSD format-private layout. Getters return owned copies. DFF standard IDs and context-specific four-byte IDs must survive an unchanged DFF transcode byte-for-byte. Preserve LSCO on unchanged streams; synthesize a value only for a layout actually representable by the specification. Unknown/reserved LSCO is opaque provenance, not permission to invent a speaker map. A disagreement between known LSCO and explicit channel IDs is diagnosed, with IDs defining sample order. [S2]

Do not silently map a DFF surround role to DSF back or WAV side when the source description is not sufficiently specific. For standard five/six-channel DSF-to-DFF conventions, document the conventional surround correspondence in the mapping function and test the channel permutation; for an ambiguous reverse mapping require an explicit output role assignment or acknowledge the mapping under the metadata-loss policy. This is preferable to making a supposedly exact speaker-angle claim from a count alone.

Known channel-preserving effects keep layout. A pure channel permutation/subset keeps the corresponding identities. A genuine mix, sum, duplicated speaker, synthesized channel or unknown `SOX_EFF_CHAN` operation clears derived roles unless the user supplies an output assignment. A narrowly scoped metadata query for `remix` may expose its parsed pure-index map; do not duplicate its complete option parser in the DSD planner. No audio data is reordered merely to make a header look conventional: any required container-order permutation is explicit in the plan and tested.

For WAV, add a bounded WAVE_FORMAT_EXTENSIBLE bridge: a representable named layout produces the appropriate speaker mask and samples in mask order. Type 5 four-channel DSF must not become WAV quad merely because the writer currently selects masks by count. An unknown layout uses an unspecified mask, not a guessed one. This bridge does not add a SoX-wide routing language or retrofit unrelated PCM handlers.

Default policy rejects loss of known channel identity at a destination that cannot represent it. `--dsd-layout-loss warn` permits a generic PCM destination with a visible warning/report; it does not permit a DSF writer to claim an arbitrary defined layout. For DSF, an explicit `--dsd-layout` assignment is required when no source-preserving type exists. DFF can represent context-specific identity without falsely claiming speakers. Mono/stereo PCM sources retain existing conventional assignments when first encoded to DSD; newly encoded multichannel PCM requires an explicit layout unless the WAV bridge supplies one.

WSD's parsed `ch_asn` is exposed as raw provenance only. No authoritative WSD specification was obtained in this session. A complete semantic mapping is a validation item, not a confirmed additional defect. Ancillary tags, timestamps, album metadata and DST decoding are outside this refactor unless a separate demonstrated regression requires a local fix.

## 4.5 Streaming and DoP

DSF/DFF readers support nonseekable input by forward reading/discarding optional chunks where possible; operations that genuinely require backward access fail explicitly. DSF/DFF output remains seekable-file output in the first release because final headers require lengths and updates. Reject unsupported pipe output before writing a misleading header. Do not buffer an unbounded stream in memory or silently introduce a temporary whole-file spool.

DoP remains a native transport effect: sixteen chronological DSD bits per channel produce one 24-bit transport sample, with the existing 0x05/0xFA alternation and completion convention. No reconstruction, resampling, gain or dither may follow packing in automatic mode. The output must preserve those 24 significant integer bits. Float/lossy or volume-controlled transport is not certified by this design. Force the final rate to `native_hz / 16`; mismatched requests fail before file open. [S3]

Exercise DoP with output backpressure, including zero capacity and a pending partial transport word. Do not write a pending word unless at least one full channel frame fits. Preserve existing known-answer payloads; any capacity correction must be isolated from payload/marker semantics. Hardware playback qualification is separate from software packing tests.

# 5. Domain planning and CLI behavior

## 5.1 Plan before opening a file

Create a private immutable `lsx_dsd_plan` after user-effect `getopts` and before output opening. It records each input's native signal and effective working signal separately, initial/final domains, PCM level reference, conversion boundaries, processing rate, channel transformations, endpoint encoding, level policy and kernel/profile IDs. It also records whether native trim seek optimization is permitted. Never overwrite a reader's native `ft->signal.rate`, `length` or channel count to pretend that its adapter returns PCM.

Use parsed `out_signal` hints, destination handler capabilities and small DSD-specific metadata queries for rate/channel-changing built-ins. Do not call effects' `start` twice as a dry run: `start` can allocate state or have side effects. Reuse output-signal negotiation through a private helper where necessary, rather than writing a second format registry. After output opening, assert that actual negotiated rate/channels/encoding match the plan; an unexpected handler adjustment is an error, not a silent conversion.

Unknown effects require PCM. Unknown multichannel effects also invalidate known channel identity unless they explicitly declare a supported metadata transform through the private built-in query. Independent per-channel effects preserve channel identity. `SOX_EFF_MODIFY` is not a native-DSD-safety flag.

In the first release, the native whitelist is deliberately small: input/output repacking; `trim` in an otherwise wholly native chain; `dsdstat` pass-through; and terminal `dop`. A new explicit `sdm` or `pcmdsd` changes PCM to native DSD; explicit `dsdpcm` changes native DSD to PCM. All other user effects, including `gain`, `norm`, `overdrive`, `rate`, `speed`, generic padding and channel mixing, operate in PCM audio. A native identity operation may be optimized away only when its parsed semantics establish identity, not from its name alone.

## 5.2 Cases and boundary placement

**Unprocessed, same-rate DSD-to-DSD.** Keep native bits. Apply only an explicitly required channel permutation and format repacking. No reconstruction, TPDF dither or SDM runs. Corrected header bytes and DFF completion frames may differ from the buggy baseline; program bits may not.

**DSD-to-PCM with no user processing.** Use a composite DSD decoder directly to the requested final PCM rate. Without an explicit output/effect rate, select the profile intermediate R, not the native MHz rate. Without an explicit output encoding/width, prefer signed 24-bit PCM when the handler supports it; otherwise use the handler's normal supported PCM encoding with a diagnostic, never infer one-bit PCM from the native input precision. The front-end profile and private final SRC remain binary64 until one graph-boundary conversion.

**DSD input with generic effects.** Reconstruct before the first generic effect, normally as the first processing effect. The default working rate is the profile's intermediate rate R, not the native MHz clock. A leading explicit `dsdpcm [rate]` chooses another working rate and suppresses implicit reconstruction. A leading ordinary `rate` still runs as the user's PCM SRC after the implicit reconstruction; its quality options remain meaningful and it is not a second DSD reconstruction. Never silently delete or move a user `rate` effect across nonlinear processing.

**Processed DSD-to-DSD, including a change of native rate.** Reconstruct, execute any user PCM chain, then run one composite `pcmdsd` at the requested native output rate. Its input-reference scale comes from section 5.4 so unity processing does not lose 6.0206 dB. Without an explicit native output rate, preserve the native input rate; an ordinary PCM input encoded to DSD defaults to DSD64. Its interpolation and modulation are local, not a generic MHz-rate int32 intermediate plus accidental one-bit `dither`. A user-supplied terminal `sdm`/`pcmdsd` prevents an automatic second modulator. Generic effects after a terminal DSD modulator are rejected unless an explicit new `dsdpcm` boundary follows. DoP can follow a terminal modulator only when explicitly requested and transport checks pass.

**Input volume/replay gain and parallel combination.** When a DSD input will be scaled by input options, mixed, multiplied, or merged with possible numeric padding, attach a per-input decoder before `balance_input` and the combiner. Each adapter reconstructs binary64 PCM at the shared working rate. Apply its known file input-volume/replay-gain multiplier to those double values before the single int32 graph conversion, and mark that multiplier consumed so `balance_input` does not apply it twice. This avoids clipping an overrange reconstruction before an explicitly requested input attenuation could protect it. This is still reconstruction before gain, not arithmetic on raw pulses. The existing combiner then processes PCM normally; its ordinary int32 mix/headroom rules remain unchanged. It must never mix raw DSD pulse trains. With DSD-only parallel inputs, use the largest participating profile R as the common rate unless an explicit leading `dsdpcm` rate specifies one. With mixed PCM/DSD inputs, use the existing PCM input rate, provided all PCM inputs already agree; DSD adapters convert to it. Differing PCM input rates remain an explicit error, not a new general input-SRC feature.

**Concatenation and sequence.** Native concatenation requires matching native rates, channel identities and order; do not silently relabel the second file. When a single downstream DSD reconstruction effect consumes a compatible native concatenation, treat it as one continuous bitstream and do not reset between files. An input-adapter path caused by file-specific gain or mixed domains finishes each file's conversion separately; its finite-file boundary behavior is reported. Do not call that gapless concatenation. `sox_sequence` resets conversion state at each sequence boundary as it already restarts the processing chain. Profile changes between contiguous files require a reset or a rejected combination, never live coefficient mutation.

**Trim and seek.** Native-only trim retains bit-preserving operation and the corrected seek optimization. Once PCM reconstruction is needed, trim means trim in the effective PCM timebase. Disable the existing file-seek trim shortcut for such chains in P08: it lacks the filter pre-roll and clock phase necessary to reproduce decode-then-trim. This is a deliberate bounded performance tradeoff, not an invitation to add a random-access DSP subsystem. A future optimized path must prove identical output to sequential reconstruction with sufficient pre-roll. Interactive seek on converted DSD resets the affected decoder and downstream state according to existing interactive behavior and reports a discontinuity; do not claim sample-identical continuity across an interactive jump.

## 5.3 Public selections

The following names are the specified interface. Add them to CLI help/manpages together with the corresponding explicit effect syntax.

```text
--dsd-mode auto|native|legacy
--dsd-decode mastering|wideband|legacy
--dsd-encode mastering|legacy|experimental
--dsd-level preserve|sacd
--dsd-clip warn|error
--dsd-bandwidth adapt|strict
--dsd-layout role,role,...
--dsd-layout-loss error|warn
--dsd-report PATH

dsdpcm [-p mastering|wideband|legacy] [-l preserve|sacd] [rate]
pcmdsd [-p mastering|legacy|experimental] [--reference auto|pcm|dsd] rate
dsdstat
```

`auto` is the new release domain policy. `native` rejects any requested operation requiring PCM rather than secretly converting. `legacy` restores the old automatic domain ordering/interpolation/selection policy where applicable, but **does not restore format corruption, seek bugs or layout falsification**. Warn that generic effects may act on native DSD pulses in legacy mode. `--dsd-decode legacy` alone selects direct generic reconstruction without restoring unsafe graph ordering; distinguish these two controls in help.

The qualified release's defaults are `auto`, mastering decode, mastering encode, preserve level, clip warn, bandwidth adapt and layout-loss error. Before P15, new behavior remains opt-in while default migration tests run. Explicit `sdm -f ...` and trellis options remain available as low-level/experimental controls, not synonyms for a qualified mastering profile. Versioned IDs such as `decode.mastering.v1.dsd128` and `encode.mastering.v1.dsd128` are accepted for reproducible selection and emitted in reports; human aliases resolve to those IDs for a release.

A terminal DoP request with no explicit output rate chooses native Hz / 16 and a lossless 24-significant-bit transport representation; it does not inherit the native MHz rate as PCM transport.

`-D` disables ordinary PCM TPDF dithering. It does not disable necessary sigma-delta conversion to a DSD output in auto mode. Explicit PCM dither remains where the user placed it, but terminal precision-1 dithering is classified as a modulator and cannot cause double modulation. Contradictory explicit and automatic DSD selections fail with the conflicting nodes named.

Kernel forcing is a diagnostic environment/API surface rather than seven more normal CLI options:

```text
SOX_DSD_KERNEL_FIR=auto|scalar|sse2|avx1|avx2|avx512|avx2-fma|avx512-fma
SOX_DSD_KERNEL_SDM=auto|scalar|sse2|avx1|avx2|avx512|avx2-fma|avx512-fma
```

Unsupported forced tiers fail before processing. They do not fall back silently. Values apply to newly created DSD contexts only and are resolved once. Reports show the actual selected kernel for each family. Library option fields take precedence over environment variables.

Examples, after the qualified release:

```sh
# Conservative bandwidth remains conservative at 705.6 kHz.
sox_ng --dsd-decode mastering in.dsf -r 705600 -b 24 out.wav

# Preserve higher-rate source bandwidth explicitly.
sox_ng --dsd-decode wideband in128.dsf -r 352800 -b 24 out.wav

# Explicitly reconstruct before nonlinear PCM processing.
sox_ng in.dsf -r 88200 out.wav dsdpcm -p mastering 88200 overdrive 10

# A PCM effect between native DSD endpoints causes one decode and one encode.
sox_ng in.dsf -r 5644800 out.dsf gain -3

# Bit-preserving native repacking, except container-mandated tail completion.
sox_ng --dsd-mode native in.dsf out.dff

# DoP is transport, not high-rate PCM audio reconstruction.
sox_ng --dsd-mode native in.dsf -r 176400 -b 24 out.wav dop
```

Examples assume compatible layouts and input rates. They are future-interface examples, not claims that the reviewed executable accepts these new options.


## 5.4 Preserve reference level through DSD processing

Keep a private `dsd_amplitude_per_pcm_unit` tag on planned PCM segments. For an ordinary PCM source it is 0.5, preserving the existing PCM-full-scale to 0 dB SACD convention. For a DSD source reconstructed with explicit decoder gain G, it is 1/G: preserve mode gives 1; sacd mode gives 0.5. This tag describes the reference calibration, not an instruction to undo user gain.

A channel-preserving effect, ordinary rate conversion, remix of sources with the same tag, or explicit artistic gain retains the tag. A PCM generator/replacement such as `synth` establishes ordinary PCM reference; a synthesis mix or combination containing ordinary PCM also uses that reference and reports the choice. Unknown ordinary processing effects retain the incoming calibration unless they explicitly replace the source. User gain remains in the signal: do not divide by it at encoding.

The automatic or CLI-planned `pcmdsd --reference auto` multiplies incoming PCM by this tag before modulation. Thus a DSD source of amplitude A reconstructed in preserve mode, followed by gain K, enters the modulator at K*A, not K*A/2. An ordinary PCM source of amplitude A still enters at A/2. No decoded PCM samples are silently doubled. `pcmdsd --reference pcm` explicitly requests half scaling; `--reference dsd` explicitly requests theoretical-DSD amplitude scaling of one. The low-level library encoder without a planner defaults to ordinary PCM reference. The CLI resolves auto into an explicit immutable encoder option before `start`.

A mixed DSD/PCM input combination uses ordinary PCM reference without silently adding +6 dB to its DSD sources. Report that choice and the resulting per-input level conventions. An explicit sacd decode level or input gain can align references where the user requires it, subject to clipping checks. Compatible all-DSD concatenation/combination retains the common DSD reference. Saved PCM files do not implicitly retain this in-process provenance; re-encoding a preserve-level PCM file requires an explicit `--reference dsd` when that calibration is intended.

`norm` and guard still target PCM graph levels. In a preserve-reference DSD-to-DSD chain, normalizing to PCM peak one would request theoretical DSD peak one and may exceed the qualified encoder envelope. Diagnose this rather than insert hidden attenuation. A user can select an appropriate normalization level, explicit reference override or gain. The purpose of the tag is to preserve requested transformations, not to pretend every requested output level is encodable by a particular modulator.

Required regressions include unity and -3 dB processed DSD-to-DSD at each native rate and across native-rate changes. Reconstructed output gain must equal the requested gain within the stated measurement tolerance. Add the demonstrated explicit-staging -9.0206 dB case as a baseline control, not as the new engine's expected behavior. Reports include input reference, decoder gain and actual modulator input scale.

# 6. DSD-to-PCM DSP specification

## 6.1 Profile transfer policies

Profiles are linear-phase, unity-DC FIR reconstruction followed by optional PCM SRC. A profile's passband edge P is the end of its guaranteed approximately flat region; stopband edge S is the start of guaranteed suppression, **not** a claimed universal boundary between program content and DSD noise.

**Mastering v1** deliberately favors ultrasonic cleanup while increasing retained bandwidth with source rate:

* DSD64: P = 20,000 Hz; S = 40,000 Hz; R = 88,200 Hz; native decimation D = 32.
* DSD128: P = 30,000 Hz; S = 60,000 Hz; R = 176,400 Hz; D = 32.
* DSD256: P = 40,000 Hz; S = 80,000 Hz; R = 176,400 Hz; D = 64.

**Wideband v1** uses R = native Hz / 32, P = 0.4 R and S = 0.5 R:

* DSD64: P = 35,280 Hz; S = 44,100 Hz; R = 88,200 Hz.
* DSD128: P = 70,560 Hz; S = 88,200 Hz; R = 176,400 Hz.
* DSD256: P = 141,120 Hz; S = 176,400 Hz; R = 352,800 Hz.

These are explicit product transfer-function choices, not an inference that every recording contains useful audio through P. Wideband can preserve more source information and more shaped noise. It is not advertised as universally better sound. The independent source corpus remains necessary to evaluate practical consequences; it is not necessary to define an honest frequency response.

Both profiles require absolute passband error no greater than 0.0001 dB and end-to-end undesired alias/stopband transfer at most -160 dB relative to unity passband, across the specified pass/stop regions. Internal stage design targets at least 185 dB stopband rejection to provide cascade and numerical margin. Phase is linear only in v1. Reject an unsupported minimum-phase request; do not relabel the current filter or silently change its response.

## 6.2 Exact filter construction

Use cascaded factor-two decimation. All early stages use the same 57-tap half-band candidate: normalized cycles/input pass edge 0.10, stop edge 0.40, center coefficient 0.5, exact alternating zero taps, and noncenter coefficients normalized to sum 0.5. The final stage is an ordinary symmetric low-pass FIR with its selected profile's P and S at input rate 2R.

The design-time candidate banks are:

```text
master64:  57, 57, 57, 57, 117 taps
master128: 57, 57, 57, 57, 153 taps
master256: 57, 57, 57, 57, 57, 117 taps
wide64/128/256: 57, 57, 57, 57, 257 taps
```

The 117-tap last stage is shared in normalized frequency by mastering64 and mastering256. The 153-tap last stage is specific to mastering128. All wideband profiles share the normalized 257-tap bank.

Generate a symmetric Kaiser-windowed sinc with midpoint cutoff `(P + S)/2` and attenuation design parameter A = 190 dB, beta = `0.1102 * (A - 8.7) = 19.97926`. Candidate length starts at:

```text
ceil((A - 8) / (2.285 * 2*pi*(stop_cycles - pass_cycles))) + 1
```

Round upward to length congruent to one modulo four, then increase by four until the generated coefficients satisfy the stage contract. For a general last-stage coefficient centered at M = (L-1)/2:

```text
h[k] = 2*fc*sinc(2*fc*(k-M)) * Kaiser(k, L, beta)
```

Normalize DC gain to unity. For half-band banks, set exact structural zeros and the exact 0.5 center, then renormalize only noncenter taps. Generate symmetric pairs from one rounded value so symmetry is exact in stored binary64. Emit C99 hexadecimal double constants and a JSON manifest with generator version, source parameters, byte-order-independent coefficient hash, tap count, P/S and delay. Python/SciPy/mpmath are development tools only; the executable consumes checked-in coefficients.

The supplied SciPy probe is a feasibility implementation. P06 MUST independently verify the final coefficient bytes with high-precision arithmetic, adaptive extremum checks and alias-image summation; a dense FFT grid alone is not a certificate. Increasing taps to meet the same public envelope is permitted only with regenerated coefficient identity, delay/count goldens and benchmarks. Do not quietly weaken the envelope or change P/S to make tests pass.

## 6.3 Scalar kernels and arithmetic

For native bits `b[n]`, define `x[n] = 2*b[n] - 1`. No input gain is hidden in the filter. All filter state and accumulation use binary64. Use symmetric pair sums and a fixed documented coefficient traversal order; skip half-band structural zeros. The scalar kernel is the implementation oracle. A high-precision direct convolution is the independent mathematical oracle.

Each stage produces every second filtered sample, with a configured phase bit. Store history in bounded rings plus a contiguous halo/scratch region for block kernels; do not allocate or memmove a complete file. No requirement exists to widen the whole graph or to use extended precision in the production hot path. Compiler contraction is disabled for baseline kernels. Denormals, rounding mode and any process FP flags must be documented; do not alter the caller's global FP environment without restoring it.

For a J-stage cascade, equivalent transfer before decimation is:

```text
H_eq(z) = product over j=0..J-1 of H_j(z^(2^j))
D = 2^J
G = sum over j of ((L_j-1)/2) * 2^j  native DSD frames
```

Validate coherent alias amplitude into every guaranteed passband frequency as the sum of the absolute transfers of all undesired images `f + k*R`, k = 1..D-1, evaluated periodically at the native rate. Do not average those images away or report only the last stage's rejection. Also measure incoherent/noise-weighted alias power, but label it separately.

Design-time sampled checks found aggregate stopband transfer about -187.4 to -188.9 dB, and worst coherent alias sums about -182.4 dB for wideband and -186.8 dB or lower for mastering. Those numbers establish feasibility of the proposed envelope, not final acceptance: see the actual JSON grids/method and retain the independent-verification gate.

## 6.4 Phase, latency, startup and end behavior

Choose stage phase bits so their native-coordinate sum is `G mod D`; discard `floor(G/D)` leading decimated outputs. This aligns the first returned output with input time zero without an undocumented fractional output-sample shift. The finite-file reconstruction operator is:

```text
y[m] = sum_k h_eq[k] * x[G + m*D - k]
x[n] = 0 outside the finite input interval
```

Here the zeros are **numeric filter boundary conditions**, not extra DSD zero bits. Substituting all-zero bits would mean -1, and substituting a 0x69 pattern would be a different, phase-dependent edge policy. Neither is the defined boundary.

For the candidate banks:

* Master64: G = 1,348 frames; phase = 4; discard = 42; front-end lookahead about 0.477608 ms.
* Master128: G = 1,636; phase = 4; discard = 51; about 0.289824 ms.
* Master256: G = 2,724; phase = 36; discard = 42; about 0.241284 ms.
* Wideband: G = 2,468 at each native rate; phase = 4; discard = 77; about 0.874433 / 0.437217 / 0.218608 ms for 64/128/256.

Compensated timestamps do not eliminate streaming lookahead. Report front-end lookahead, final-SRC lookahead, buffering latency and total separately. Never emit these discarded priming samples as extra silence in the final file.

To define composite finite-file behavior without hidden stage-rounding ambiguity, generate intermediate centered samples for `m = 0 .. ceil(N/D)-1`, where N is the actual native frame count. The final PCM SRC treats that finite sequence as zero-extended. This is a deliberately defined **cascade of finite operators**; it is not claimed to equal an infinite full convolution at the first/last samples. When no final SRC is required, return only the requested rounded output count. Test the exact operator at both edges against an independent implementation.

The final frame count for a pure conversion is:

```text
N_out = floor(N_native * F_out / F_native + 1/2)
```

Implement checked integer quotient/remainder arithmetic, not double products or a chain of independently rounded intermediate lengths. An unknown input length becomes known at finish. Before EOF, do not release an output frame that could exceed the count for a stream ending at the currently consumed input position; bounded holdback makes the same rule apply to tiny streams. Finish appends only internal numeric zeros needed for filter support and returns exactly N_out frames. Zero-input conversion returns zero frames. One input DSD frame may round to zero PCM frames. Repeated finish after DONE returns zero.

The original-native count rule applies within one composite conversion. Explicit user effects that change rate, duration or sample count introduce their own ordinary graph semantics; do not pretend that a later modulator can infer an unchanged original duration after arbitrary editing.

## 6.5 Final SRC and output-bandwidth policy

For R != final PCM rate, use the private rate backend with linear phase, 180 dB rejection and **95% 0 dB bandwidth**. In public CLI terms the bandwidth quantity corresponds to `-B 95`, not `-b 95`, which denotes the 3 dB bandwidth in this repository. Disable alias-allowing modes. For R == output rate, bypass the SRC entirely.

For an SRC stage, the advertised flat composite region ends at:

```text
P_effective = min(P_profile, 0.475 * min(R, F_out))
```

For the identity-rate case it is P_profile. The source stopband is still governed by S_profile; a lower destination Nyquist imposes an additional stopband/alias requirement. Record the profile edges, final rate filter edges and measured composite envelope rather than reducing the two filters to one ambiguous 'cutoff'.

`adapt` permits this documented intersection. For example, mastering128 to 44.1 kHz cannot preserve the complete 30 kHz profile passband; it returns a high-quality lower-bandwidth conversion and reports the effective edge. `strict` rejects any output/SRC combination that cannot retain the full P_profile. All nine output rates remain valid in adapt mode. Increasing the output rate from 352.8 to 705.6 kHz does not widen a profile. Upsampling adds representation samples, not newly recovered bandwidth.

## 6.6 Levels, graph clipping and user gain

Preserve mode uses gain 1. A conventional 0 dB SACD sine with DSD-domain peak 0.5 therefore reconstructs near -6.020599913 dBFS PCM. Sacd mode uses gain **exactly 2**, not an approximate +6.0 dB. Neither mode normalizes program peaks. [S4]

The binary64 decoder returns its actual values. Before entering `sox_sample_t`, apply the selected gain once, count out-of-range samples, and use the existing documented SoX rounding/saturation convention. Record maximum pre-clamp magnitude and clipping count. `--dsd-clip error` stops the conversion and returns failure; `warn` clips at the graph boundary with an explicit warning and report. Float WAV/AIFF output does not bypass that boundary. This release does not add a parallel direct-to-writer float CLI pipeline; library consumers needing overrange values can use the new double API.

`gain`, `norm` and guard operate on reconstructed PCM, not native pulses. With preserve mode they retain their normal semantics. Sacd gain is applied before graph effects, so a later negative `gain` cannot recover samples already clipped. Reject `--dsd-level sacd` combined with automatic guard/normalization in v1 rather than imply that guard can retroactively protect that conversion. The supported headroom workflow is preserve mode followed by explicit PCM gain/normalization. A future fused gain/guard design requires a separate proof; it is not hidden inside this release.

Finite-boundary filter overshoot can exceed ±1 even in preserve mode for extreme native patterns. The same clipping policy applies. Stopband attenuation does not guarantee absence of time-domain peaks. No unreported local limiter is allowed.

# 7. PCM-to-DSD profiles and stability

## 7.1 Profile registry and interpolation

Replace implicit first-match selection in the new path with an immutable registry keyed by native rate and profile version. Each entry binds: input-bandwidth policy, prefilter coefficients, interpolation configuration, SDM coefficient identity/order, initial state, input envelope, numerical-state guard bounds, modulation diagnostics and qualification certificate hash.

**Legacy v1** binds the reviewed rate-specific `clans-4` selection, 0.5 scaling and existing automatic interpolation semantics. Keep the legacy path available for compatibility and as a measurement control. Fixing DFF bytes or runtime dispatch does not promise the legacy encoder's bytes remain identical across different kernels. A pinned legacy scalar/kernel/profile can have its own golden outputs.

**Mastering v1** binds the existing **exact-rate `sdm-8` coefficients** for each of DSD64/128/256, trellis off, zero initial integrator states and previous decision zero, with no hidden random dither or warm-up output. Preserve coefficient bits during the extraction. Initial state and first-sample behavior are part of the versioned identity. Do not reinterpret one rate's coefficients as another rate's profile.

The composite `pcmdsd` pipeline is:

```text
PCM graph samples
  -> normalize to binary64 PCM amplitude
  -> optional rate_f64 to profile working rate R
  -> source-bandwidth FIR at R
  -> rate_f64 interpolation to exact native DSD Hz
  -> apply the resolved input-reference scale exactly once
  -> qualified rate-specific SDM
  -> chronological native bits
```

Use the same mastering P/S/R policy as the corresponding decoder, but generate a **non-decimating** prefilter at R; do not accidentally reuse a last-stage decimation bank whose design input rate is 2R. The prefilter uses the documented Kaiser generator, linear phase, 185 dB stage rejection and the 0.0001 dB public passband envelope. The input-to-R SRC and R-to-native SRC use the private 180 dB, 95%-0-dB-bandwidth, linear-phase configuration. Bypass identity SRCs. A low-rate source necessarily narrows the effective passband; report this intersection.

This first mastering profile deliberately does not preserve all ultrasonic information in a 384/705.6 kHz PCM source. That is its production bandwidth contract, not an SRC bug. Wideband PCM encoding remains an explicit experimental profile until separately qualified; a wideband decoder does not automatically authorize a wideband encoder.

Ordinary PCM uses the existing 0.5 reference scale. A DSD-origin remodulation uses the explicit inverse decoder-reference gain from section 5.4; it must not be attenuated a second time. The profile's input envelope and stability qualification apply after this reference scaling.

No intermediate int32 quantization or saturation occurs inside `pcmdsd`. Interpolation overshoot is visible to the level/overload policy. Use the composite's original input count to produce exactly `round_half_up(N_pcm * F_dsd / F_pcm)` DSD frames, with the same checked rational arithmetic and explicit finite-boundary convention as the decoder. Retain the finite working sequence long enough to supply this endpoint; do not let two rounded lengths lose or add native bits. DSF records the resulting count exactly; DFF/DoP may add their declared transport completion bits.

The guaranteed count/rate matrix covers positive integer PCM rates, including every required rate through 705.6 kHz. A noninteger effective rate from a `speed`-style effect must first pass through an explicit ordinary `rate` to an integer PCM rate for this profile. Legacy behavior remains available. Do not silently approximate a floating rate and claim exact native-frame accounting.

### Normal SDM recurrence

For order N, old state s, new state d, input x in the resolved DSD amplitude domain, previous decision q, and stored coefficient vectors a and g, retain the reviewed recurrence:

```text
d[0] = s[0] - g[0]*s[1] + x - q
v = x + a[0]*d[0]
for i = 1 .. N-2:
    d[i] = s[i] + s[i-1] - g[i]*s[i+1]
    v = v + a[i]*d[i]
d[N-1] = s[N-1] + s[N-2]
v = v + a[N-1]*d[N-1]
q_new = signbit(v) ? -1 : +1
```

All right-hand state references use the old bank; swap only after the full step. The +1 tie choice, including the signbit distinction for negative zero, is specified. Do not accidentally feed a newly updated coordinate into a later coordinate and change the filter topology. SIMD may change reduction rounding only under the explicit signal-equivalence contract.

## 7.2 Admitted input and overload behavior

The profile's nominal modulator-domain admitted peak is 0.5, corresponding to ordinary PCM full scale after interpolation under PCM reference, or peak 0.5 in a preserve-reference DSD-origin PCM segment. Permit only the small representation margin required to map `SOX_SAMPLE_MIN` consistently: two source-int32 LSBs in normalized PCM, not an arbitrary percentage. Values exceeding the admitted peak are explicit overload, not a license to clamp. This can occur when a full-scale limited waveform overshoots during interpolation even though its stored PCM samples did not exceed full scale.

Mastering mode's initial policy is **fail on overload**, with the native-frame index, channel, measured peak and minimum attenuation implied by that observed peak. Users may apply explicit PCM gain and retry. Do not silently reduce gain, switch to `clans-4`, reset the modulator or continue calling the result qualified mastering output. The test suite distinguishes successful in-envelope stress from deliberate expected rejection of out-of-envelope stimuli. Passing an overload test means detecting it and failing cleanly, not producing apparently successful corrupted audio.

The proposed envelope is conservative and reviewable. Expanding it requires a new profile qualification record. The conventional SACD maximum-modulation level does not prove a particular eighth-order SDM is stable for every PCM waveform approaching that level.

For each rate and state coordinate, the P09/P10 certificate freezes a finite guard bound B_i. Derive a candidate B_i as sixteen times max(1, the largest absolute coordinate observed) over the complete in-envelope training/stress corpus, rounded upward to a power of two; then validate against a separate holdout corpus. Record both corpora and maxima. These are operational runaway guards, **not a mathematical proof of universal stability**. A profile lacking guard bounds cannot be promoted. Guard bounds must not be raised automatically at runtime or adjusted to hide a failed holdout case.

Mastering kernels check nonfinite state and these bounds during recurrence processing before declaring the current block successful. They also retain exact native-frame indices for the first violation. The output of a failed block is not committed to the next stage. Prior completed blocks may already have reached a stream; close with a nonzero status, retain a failure report and do not present the partial file as a completed master. Use existing CLI failure-cleanup rules for any partial file; do not add a new automatic rename/deletion policy. A stream such as stdout cannot be rolled back.

DSD64 mastering additionally requires every complete 28-bit window in the qualified nominal corpus to contain between four and twenty-four ones. Keep the window across processing buffers. Do not apply this as a universal file-validity rule to all DSD64 inputs, and do not present it as a normative higher-rate limit. At DSD128/256 report the same statistic as a diagnostic, plus run-length distribution, state extrema and overload events. [S4]

## 7.3 What the fresh SDM probe establishes

The attached short scalar recurrence tests found bounded-looking `sdm-8` states and no 28-bit excursions for the sampled 0.5-amplitude sine, DC, step, low-level and multitone cases at all three rates. Healthy eighth-order raw state coordinates reached roughly millions; a universal 'state must remain below 1' guard would be wrong.

Unfiltered native-rate noise and abrupt repeated full-scale square waves caused substantial growth for several candidates. Near-overload cases also produced enormous but still finite coordinates in this short run. Therefore `isfinite()` alone is not an adequate stability monitor. These stimuli bypass the proposed interpolation/prefilter and are **not evidence that an admitted, band-limited mastering conversion fails**. They justify testing interpolation, state growth and input-envelope enforcement together. They do not justify a claim that `sdm-8` is universally stable or that one chosen state threshold is already validated.

The probe also found candidate/rate-specific behavior, including substantial 28-bit excursions for some `clans-8` DSD256 cases. At that rate the statistic is diagnostic, not a claimed SACD violation. Full details are in the JSON, including scope, duration, amplitude and stimulus. Do not reduce these data to an unsupported ranking of all possible modulator profiles.

## 7.4 Promotion rule, not a hidden fallback

P10 implements and evaluates the selected `sdm-8` mastering pipeline. Promotion requires all nominal stability, level, spur, residual and output-count tests in section 10. It also requires a measured improvement over the exact-rate legacy control on the frozen reference suite: at DSD64, at least 6 dB lower geometric-mean in-band residual power level across the specified non-overload tone/multitone cases, and no material regression on individual non-floor-limited cases; at DSD128/256, no greater than 1 dB degradation on any valid comparable case and a documented quality/performance tradeoff. These are **project release targets**, not previously measured results.

If the chosen coefficients fail, preserve the failed evidence and block profile promotion. A corrective coefficient/profile revision must be explicit, versioned and requalified; neither table-order fallback nor relabeling an unqualified filter completes P10. The engineering plan resolves the architecture and candidate, while correctly leaving empirical qualification as work to execute. The final world-class release cannot claim this profile until that gate closes.

Trellis and alternative `clans-*`/`sdm-*` names stay experimental/explicit. No automatic stabilizer/reset is introduced in v1. A future reset-enabled profile must define trigger, reinitialization, output discontinuity, settling, event reporting and separate quality tests; it cannot be implemented as an undocumented rescue inside a kernel.

# 8. Runtime kernels and performance architecture

## 8.1 Block interfaces

Kernel selection occurs once when a context is created. Dispatch a block operation, never a function pointer for every DSD bit. Keep the scalar recurrence and FIR definitions available to tests regardless of host ISA.

```c
typedef void (*lsx_dsd_fir2_fn)(
    const double *input_with_history, size_t output_frames,
    const double *symmetric_coeffs, unsigned taps, unsigned phase,
    double *output);

typedef sox_dsd_status_t (*lsx_dsd_sdm_block_fn)(
    struct lsx_sdm_normal_state *state,
    const struct lsx_sdm_profile *profile,
    const double *pcm_dsd_domain, size_t frames,
    sox_sample_t *native_bits, size_t *committed_frames,
    struct lsx_dsd_kernel_stats *stats);
```

The FIR caller owns indexing/history and supplies a contiguous interval containing every referenced tap; the kernel owns no stream phase or allocation. Document the lowest/highest readable element for the selected phase and output count in the header and test it. The SDM state contains previous quantizer output, active order, two state banks and absolute frame index; profile coefficients/guard bounds are immutable. Return consumed/committed count explicitly when a block can fail, rather than imply the entire request succeeded. Optional stats storage must not change signal arithmetic.

A kernel descriptor contains name, required feature mask, family, FMA policy, alignment preferences, scalar tail function and validated profile/order mask. Dispatch may choose different ISAs for FIR and SDM. Bit unpack/reversal/packing remains scalar/table-based initially; optimize it only after profiling demonstrates meaningful remaining cost.

## 8.2 Genuine ISA implementations

**Scalar:** fixed-order binary64 arithmetic, explicit noncontracted multiply/add and a clearly documented quantizer tie rule matching `signbit(v) ? -1 : +1`. Negative zero behavior is preserved. No `-ffast-math`.

**SSE2:** two independent output times per FIR vector, with broadcasts of coefficients and symmetric pair sums; scalar tails. For SDM, retain/port the existing two-lane state-vector formulation into a selectable block kernel with the same profile/monitor interface. This is also the fallback for many older x86 CPUs.

**AVX1:** four independent FIR output times per vector, built with AVX floating instructions and 128-bit lane operations where needed. Retain an independently compiled version of the existing AVX double-state kernel, including its lane-crossing costs. Build with `-mavx -mno-avx2 -mno-fma`; it must run when AVX2 is absent. An AVX1 implementation compiled incidentally by AVX2 flags is not sufficient evidence.

**AVX2:** four-output FIR vectors using genuine AVX2 full-width lane permutations to assemble stride-two windows efficiently. The SDM kernel uses AVX2 full-width 64-bit lane permutations/shifts for adjacent state dependencies rather than merely renaming the AVX1 translation unit. Extract cross-vector boundary values explicitly. Keep a non-FMA baseline compiled with contraction disabled. Record assembly evidence and kernel/end-to-end benchmarks; the presence of a new mnemonic alone does not prove a useful optimization.

**AVX-512:** eight-output FIR vectors, using AVX-512F double operations and permutation/masking to form windows; scalar or properly bounded masked tails. An eighth-order SDM can represent its state in one eight-lane vector, with inactive lanes masked for lower orders and a defined reduction order. Baseline support requires only the advertised subset, initially AVX-512F plus the lower-tier instructions actually used. Do not accidentally use AVX-512BW/DQ/VL without adding those feature requirements to both compilation and dispatch. AVX-512F multiply and add can be separate; FMA is not mandatory policy.

Do not vectorize the normal SDM recurrence across dependent time samples as though each sample were independent. SIMD across state coordinates or independent channels is legitimate; splitting a single stream into independently initialized time lanes is not. A channel-batched kernel is an optional later optimization only if it fits SoX's flow ownership and handles channel counts 1, 2, 5 and 6 without changing arithmetic state.

**FMA specializations:** optional `avx2-fma`/`avx512-fma` descriptors, explicit feature check, explicit contraction policy and their own qualification/benchmarks. Baseline AVX2 and AVX-512 remain available without FMA selection. For SDM, FMA can change the one-bit trajectory; it is not treated as merely a faster instruction spelling.

## 8.3 CPU and operating-system detection

On x86, check CPUID availability/platform support through a small portability layer. SSE2 is leaf 1 EDX bit 26. AVX requires XSAVE, OSXSAVE and AVX from leaf 1 ECX, then XGETBV(0) XCR0 bits 1 and 2 set. Never execute XGETBV before establishing OSXSAVE support. AVX2 additionally requires leaf 7 subleaf 0 EBX bit 5. AVX-512F requires leaf 7 EBX bit 16 and XCR0 mask 0xE6, covering XMM/YMM and opmask/ZMM state. FMA variants additionally check the appropriate FMA capability. Validate that each queried CPUID leaf exists. [S5]

Non-x86 builds select scalar without compiling x86 intrinsics. Older compilers may omit unsupported ISA translation units, but the release build matrix must include compilers capable of building all required tiers. Use per-file flags or well-supported target attributes with equivalent isolation; do not apply `-mavx2`, `-mavx512f` or `-march=native` to the whole executable. Inspect LTO builds for cross-target inlining, and prohibit it at these boundaries if necessary. [S6]

## 8.4 Selection policy and forcing

Availability is not preference. Use a small checked-in policy keyed by CPU vendor/family/model class, kernel family and relevant workload class, with source benchmark identifiers beside each preference. An unknown CPU uses the conservative **SSE2** optimized tier when available, otherwise scalar; higher tiers remain forceable. This favors predictable compatibility over a fabricated universal AVX2/AVX-512 performance ranking. P15 may establish additional conservative defaults only with recorded evidence.

Do not run an unpredictable calibration benchmark on every file open. A separate benchmark tool can produce a proposed policy entry; a reviewer approves it. Prefer a wider kernel only when the response-qualified kernel and end-to-end workload show a stable benefit. AVX-512 may be available but not selected. User overrides are validated, recorded and applied without mutating global state used by another context.

A VM with AVX2/AVX-512 CPUID disabled can validate instruction isolation and AVX1 correctness, but not Sandy Bridge/Ivy Bridge performance. A physical AVX1-only CPU or equivalent instruction-validating environment is a required compatibility check; microarchitecture-specific preference claims require actual representative hardware.

## 8.5 Memory and threading

Allocate internal rings/scratch with 64-byte alignment using a portable allocation/free pair. Pad allocation size to the allocator's requirement; do not assume C11 `aligned_alloc` accepts arbitrary sizes. External pointers may be unaligned. Kernels may not over-read caller tails merely because an unaligned vector load is convenient. Keep bounded halo storage under the context's ownership.

Reuse SoX per-channel flows/OpenMP. Do not create a nested thread pool inside each decoder/modulator. Each channel has independent history and counters; immutable coefficient banks can be shared. Input adapters can parallelize independent channels under the same existing threading setting, but may not oversubscribe an already parallel effect chain. Merge diagnostics in a deterministic channel order after a block/end, not with atomics in every recurrence.

The initial graph still expands native bits to int32. Its per-pass traffic at DSD256 is already material; at DSD1024 six channels would carry about 1.084 GB/s for one int32 payload pass alone. Reads, writes and intermediate copies multiply that traffic. This motivates P16's packed front end, not a rewrite of every SoX effect to accept packed DSD.

## 8.6 Numerical contracts

For FIR kernels, output count, phase and endpoint behavior are identical. Bit equality is desirable but not mandatory. Bound binary64 differences against the scalar implementation by a conservative accumulated-roundoff envelope proportional to machine epsilon, total tap count, the product of stage L1 norms and input peak. Initial acceptance uses `16 * DBL_EPSILON * sum(L_j) * product(sum(abs(h_j))) * max(1,input_peak)` per finite cascade sample, supplemented by the independent high-precision oracle. Graph samples may differ by at most one int32 LSB; no extra clipping is allowed. Final SRC comparisons have their own measured numerical tolerance, not a claimed FIR-only proof.

For SDM, raw bytes need not match. Within one kernel/profile, changing buffer sizes or thread scheduling must not change a channel's bitstream. Across kernels, compare independently reconstructed signal, spectra and stability under section 10. A CPU-wide reproducible-byte mode is not delivered. Forcing scalar helps reproducibility under a pinned build but is not advertised as universal cross-compiler determinism.

# 9. Production diagnostics

## 9.1 Report schema and lifecycle

A report is a versioned JSON object, written outside the audio stream. Minimum fields are `schema_version`, build/source identity, status (`complete`, `failed`, `cancelled`), source and output domains/rates/counts, source representation, channel identities, decode/encode profile IDs, coefficient hashes, FIR/SDM kernel names, requested/effective bandwidths, level mode/gain, latency components, clipping counts, per-channel SDM state extrema, overload event counts/first indices, 28-bit-window extrema/excursions, native/transport completion counts and warnings.

Represent unknown values as JSON null with an explanation, not fabricated zero or nonstandard JSON NaN/Infinity. Large integer counters are serialized as decimal strings where lossless interoperability with common JSON readers matters. Reports distinguish theoretical DSD amplitude, PCM dBFS and SACD-reference dB. Never print an unlabeled 'peak' whose reference changes between modes.

Open a named report destination only after preflight and the normal overwrite policy. `--dsd-report -` may use stdout only when audio does not use stdout; otherwise reject it. Normal diagnostics remain on stderr. Write a final status on error and cancellation when the process can still do so. No new daemon, remote telemetry, database or GUI is part of this work.

Basic counters are retained whenever their profile guarantees require them. Expensive spectral analysis is opt-in and its runtime is measured separately. Profile/kernel IDs and clipping counts must not depend on enabling a full analysis pass.

## 9.2 `dsdstat` and spectral diagnostics

`dsdstat` is a native-bit-preserving analysis effect. Default operation reports bit counts, complete 28-bit windows, maximum run length and source metadata. An optional `-a` analysis mode adds filtered level and band-energy diagnostics. It never sends a reconstructed signal downstream or triggers remodulation merely to inspect input. On PCM input it rejects with a domain-specific error rather than pretending PCM samples are bits.

For native DSD analysis, do not calculate 40–100 kHz energy from the mastering decoder's output: that path intentionally removes much of the requested band. Use an independent analysis path. The first implementation may use binary64 native-rate Butterworth SOS filters: fifth-order low-pass at 50 kHz for the SACD-style level diagnostic, and fifth-order high-pass 40 kHz followed by fifth-order low-pass 100 kHz for the corresponding band diagnostic. Generate digital coefficients from the specified analog prototype using a documented bilinear transform/prewarp, store the method and rate, and verify the digital transfer independently. Use double SOS state, not a high-order direct polynomial.

Label this as **SACD-style software measurement**, not formal player/disc certification. The 28-bit population-count test is an exact bitstream statistic; the software filter's equivalence to a particular analog measurement instrument is a separate metrology issue. Where implementing the manual's exponential averaging convention, use the documented coefficient and retain it in the report rather than substitute an FFT RMS number under the same label. [S4]

Also report conventional integrated band power for 20–40, 40–100, 100–200 kHz and 200 kHz to available Nyquist, with explicit clipped-band endpoints. Output PCM analysis uses the actual output's Nyquist. Record filter warm-up exclusion, integration interval and reference units. A shortened or unrepresentable band is labeled as such. There is no universal promise that all recordings meet one ultrasonic energy number.

# 10. Validation and benchmark contract

## 10.1 Test layers and independent sources

P00 introduces `tests/dsd/` and maintainer targets. Expected failures in the baseline are explicit, narrowly named xfails with a defect ID and reproduced result; do not use a blanket 'DSD tests expected to fail' wrapper. Once the corresponding phase fixes a case it becomes a hard regression. Existing `make check` remains mandatory throughout.

Use four evidence classes: independently constructed container vectors; mathematical transfer/streaming oracles; independent DSD material or an independently implemented encoder/decoder; and performance measurements. Do not call a round trip using the same reader/writer or encoder/decoder independent validation. Retain legacy and new paths as differential controls, not universal correctness oracles.

Fixture manifests include source/license/provenance, SHA-256, native rate, chronological bit hash, logical frames, channel order and expected operation. Tiny fixtures are generated programmatically from hand-derived bytes. Do not require copyrighted recordings in ordinary CI. Larger external reference material is optional/local until redistribution permission is established.

## 10.2 Frozen analysis procedure

Before setting or comparing encoder quality results, generate and commit **analysis-v1**, independent of production coefficients and the SoX rate backend. Its baseband reconstruction is one symmetric binary64 FIR designed at the native DSD rate with passband 20 kHz, stopband 24 kHz, at least 180 dB stop rejection and no more than 0.00001 dB pass error, then exact decimation to 88.2 kHz. Use a high-precision coefficient generator and an independent direct/FFT overlap-add implementation. It may be long; it is an offline oracle, not the production engine.

Freeze the exact coefficient bytes/hashes for all three native rates, delay compensation, window, frequency integration, source amplitudes and trimming. Discard at least the larger of 250 ms or twice the complete analysis impulse-response support from both boundaries for steady-state measurements. Generate sufficient stimulus duration to retain at least one full measured second; a 0.125-second development probe is not this test.

Measure coherent 997 Hz and 1 kHz tones at PCM-source peaks corresponding to -0.1, -6, -20, -60, -90 and -120 dBFS, plus a separately handled full-scale case. After reconstruction, least-squares fit the known fundamental frequency with DC, sine and cosine terms. Report gain/phase error separately from residual. THD+N includes harmonics and residual noise in 20 Hz–20 kHz after removing only the fitted fundamental and DC. Report THD-only and noise-only where separation is valid; do not label a residual with removed harmonics THD+N.

For power P in normalized PCM units, report band dBFS as `10*log10(P/0.5)`, with 0 dBFS defined as a sine of peak one. SNR is the ratio of fitted signal power to residual power; it is not interchangeable with residual dBFS. Decoder preserve mode's approximately -6.02 dBFS reference signal remains at that level unless the measurement explicitly applies gain two. Record whether a result is limited by fixture/analysis precision.

Use rectangular windows only for truly coherent data and aligned cycles; otherwise use a specified four-term Blackman-Harris window with its exact coefficients and equivalent-noise-bandwidth correction. Freeze that choice in each test rather than switching windows to improve a plot. Publish native-rate FFT spectra separately for ultrasonic bands; do not compare spectra truncated by different analysis filters as though they were equivalent.

Use a second independently implemented reconstruction/filter for corroboration on selected cases. The primary pass/fail numbers remain analysis-v1, and any second-filter differences are reported rather than averaged into an invented common result. Saracon is an optional matched comparison, never a presumed oracle or a substitute for this procedure.

## 10.3 Format, streaming, seek and layout tests

For channels 1 through 6, generate chronological pseudorandom bits plus alternating, 0x69, impulse-density and all-one/all-zero storage patterns. Cover logical frame counts 0 through 33, exact block boundaries and their ±1 neighbors, more than one DSF block, and DFF chunks with odd/even audio lengths. The all-one/all-zero cases test storage semantics; they are not claimed valid mastering audio.

Test DSF bps 1 and 8, equivalent chronology across representations, all defined DSF channel types compatible with channel count, DFF standard/context IDs, LSCO handling, following MANF/optional chunks and cross-format conversions. An independent chunk walker verifies both logical sizes and physical spans/pads. Under allocator perturbation or an equivalent deterministic allocator fixture, the first DFF output cluster must match input bits. Byte comparison ignores only explicitly identified timestamp/metadata differences, never audio bytes.

Exercise repeated frame capacities 1..17, mixed irregular capacities and CLI `--buffer 32`, plus zero-capacity API calls. For DFF, test exactly one byte cluster even when total bytes are less than eight. Non-byte-aligned DSD seeks are frame positions not divisible by eight; include mono/stereo/five/six channels. Compare sequential slices with seeked slices, read/rewind/read, seek after previous reads, end seeks and out-of-range failures. Verify both `olength` and private cache/remaining state. Include WAV uncompressed and GSM, raw PCM, and optional-codec seek tests when those dependencies exist.

Test DSF Type 5 remains Type 5; Type 4 remains Type 4; DFF ID order survives; mixed-channel operations clear or deliberately transform identities; and WAV extensible masks and sample order agree. Native transcodes must not instantiate DSP. Nonlinear DSD processing must match an explicit reconstruct-first PCM reference, not the baseline's pulse-domain result. Input volume, replay gain, mix, merge padding and multiple input combinations are separate tests, because they precede user effects.

DoP has hand-derived 1..33-frame vectors, marker continuity across buffers/channels, output-capacity backpressure and drain completion. It is rejected when followed by a gain/rate/dither operation in auto mode. Raw native bits decoded from produced transport payloads must match source bits through the source logical endpoint.

## 10.4 DSD-to-PCM numerical matrix

Every release covers 3 native rates x 9 PCM rates x 2 profiles, including 352.8 and 705.6 kHz explicitly. Run scalar on every cell; run all available ISA tiers on a representative full grid in qualification and a selected smoke matrix in ordinary CI. Channels 1, 2 and 6 cover throughput/channel isolation; 5 channels cover awkward buffering. Test additional channel counts through format-supported limits with small vectors to exercise indexing, without pretending those counts received the same hardware benchmarks.

Required tests: unity DC/normalization; impulse and delayed impulses; high-precision finite convolution; tone sweeps through pass/transition/stop regions; all alias-image families; output count and fractional-rate ratios; zero/tiny streams; startup/drain; channel isolation; level gain; clipping; buffer invariance; and count/phase invariance under threading. Use internal linear-kernel stimuli for transfer-function tests and independent one-bit streams for full API tests. Do not pass a floating sine to an alleged one-bit converter and call it a DSD end-to-end test.

Acceptance is the specified P/S/ripple/alias envelope, correct time alignment and exact count, plus the numerical tolerances in section 8.6. Report native/program noise separately. A known noisy DSD recording need not achieve -160 dB THD+N simply because the filter suppresses aliases by 160 dB. At integer ratios, compare against direct high-precision decimated convolution. At 48 kHz-family ratios, compare the combined stage against an independently implemented high-precision SRC reference as well as the private adapter's own tests.

Regression cases MUST explicitly include master64->705.6 and wide256->705.6. The first proves upsampling cannot restore removed ultrasonics; the second proves the design does not apply a fixed 40 kHz cutoff to all higher-rate DSD.

## 10.5 PCM-to-DSD numerical/stress matrix

Source rates include 44.1, 48, 88.2, 96, 176.4, 192, 352.8, 384 and 705.6 kHz. Test all three native destinations. Compare legacy `clans-4`, the selected `sdm-8`, and diagnostic `sdm-6`/`clans-8` controls with the same frozen analysis; controls are not additional required mastering profiles.

Stimuli include the frozen tones; low-frequency sweeps; DC ±0.5 in the admitted modulator domain; silence and near-silence; repeated starts/stops; impulses; band-limited steps and clipped/limited material; multitone material with known crest factor; band-limited random noise with frozen seeds; near-profile-edge tones; and explicit overloads. Apply the actual profile interpolation before judging input admission. Unfiltered native-rate white noise is a useful kernel stress case but is not a substitute for a valid PCM mastering-input test.

For in-envelope input, there may be no nonfinite state, guard-bound crossing, unreported reset or lost/duplicated sample. DSD64 must meet the selected 28-bit-window guarantee. At higher rates the statistic is diagnostic and quality/state/run-length criteria still apply. Silence and low-level measurements may not introduce a stable baseband spur above -110 dBFS on DSD64 or -120 dBFS on DSD128/256 under analysis-v1; these are explicit project qualification targets, not results already obtained. Also require no spur more than 3 dB worse than the scalar selected-profile control when comparing an optimized kernel. Floor-limited cases are reported as such, not numerically ranked.

Run 60-second sustained cases during profile development, at least 30 minutes per rate on silence/DC/music-like/noise sequences for release qualification, and one-hour mixed-content soak per released profile/ISA family on representative hardware. The harness supports resumable, deterministic segments with saved state for the soak; record continuation state hashes. A model session may deliver the runnable test and accurately report a missing hardware run, but may not mark the corresponding release gate passed.

Overload cases must fail/report according to section 7.2 without a successful output status. Count correctness is checked before container completion and afterward. Buffer size and single-/multi-thread changes must preserve bytes for the same kernel/profile/build. Include both legacy effect `sdm` and composite `pcmdsd` integration tests so new profile routing does not accidentally bypass explicit legacy choices. Verify unity/-3 dB DSD-origin remodulation, decoder-gain compensation, explicit reference overrides, generated PCM and mixed-source reference policy; an unnoticed extra 6.0206 dB loss is a release-blocking failure.

## 10.6 Cross-ISA sigma-delta equivalence

Apply analysis-v1 after latency alignment. Fundamental gain differs from scalar by at most 0.001 dB and phase by at most the measurement's defined sub-sample tolerance. THD+N/residual power may not worsen by more than 1 dB on non-floor-limited cases. Integrated noise in represented ultrasonic bands may not worsen by more than 1 dB, with the same source/profile/filter and a floor-aware comparison. Check new narrowband spurs, run lengths, modulation statistics and state guards separately; integrated noise can conceal a new idle tone.

A decoded difference between two valid noise-shaped trajectories is not expected to be zero. Compare pairwise residual power against the sum of the individually measured residual powers with an additional 3 dB margin, after removing measured gain/phase mismatch. Do not impose an arbitrary universal -120 dB pairwise null test on a modulator whose own baseband noise is higher. Any exemption must state the measurement floor or confidence bound; it cannot waive a visible tone or stability defect.

Keep raw hashes for within-kernel determinism and native repacking. They are not the main cross-ISA SDM quality gate. FMA variants receive the same independent suite and their own result IDs.

## 10.7 Benchmarks and dispatch gates

Define real-time factor as **wall seconds / audio seconds**, so lower is better. Also report its reciprocal, frames/s per channel, aggregate native bits/s, CPU seconds, wall seconds, maximum RSS and, where available, cycles, instructions, cache misses and memory bandwidth. Always state channels, duration, rate/profile, kernel, compiler flags, CPU model/microcode, OS, thread count, affinity, governor/frequency conditions and whether I/O is included.

Benchmark FIR/SDM kernels separately, then end-to-end decode and encode. Matrix: DSD64/128/256; mono/stereo/6-channel; decode outputs 88.2/176.4/352.8/705.6 kHz; encoder outputs all three DSD rates; every available required ISA; FMA separately; single-thread and existing multi-thread mode. Include small-file latency and long-stream throughput. Isolate DSP using memory/tmpfs, then measure representative real file I/O separately.

Compare the new decoder both against the legacy ultra-quality direct path and against a **bandwidth-matched staged legacy control**. A speedup caused only by a narrower bandwidth is not an ISA speedup. Compare encoder kernels at identical coefficients, profile/interpolation and monitoring settings. Report monitor overhead rather than turning off required guards for a headline benchmark.

Use warm-up plus at least 15 timed repetitions for short benchmarks, medians and dispersion/confidence intervals. Reference performance gates: no more than 5% median regression on unchanged native repacking or legacy paths when measurement noise is under 2%; otherwise rerun on a controlled host. A dispatch preference requires at least 10% reliable kernel benefit and no material end-to-end regression on its target workload class. The project target for the main six-channel DSD256 decoder is at least 2x the reviewed direct ultra-quality path on the fixed reference host, with the bandwidth-matched comparison also reported. This is a target to test, not a measured claim in this design; failure requires a documented optimization decision, not weakened quality.

Required hardware evidence: AVX1-only execution or a validated feature-restricted environment for compatibility; an AVX2 machine; Intel AVX-512; and AMD AVX-512 when available. Physical older-AVX performance and vendor-specific dispatch selection require representative physical machines. A skipped run remains a named gap. Never infer all CPU classes from the design-session VM.

# 11. Compatibility, integration budget and release policy

Preserve the public sizes/layouts of existing SoX structs, original entry points, generic PCM `rate` behavior, non-DSD processing behavior, native DSD chronology, DoP framing, 0.5 encode scaling and existing AVX1 eligibility. Export new APIs additively. Apply the repository's normal shared-library version rules for added symbols; do not bump ABI merely because private files were added. If an implementation changes a public struct despite this design, that is a design deviation requiring explicit review, not an invisible integration detail.

Intentional changes are: compliant DFF headers/pads/first bits; correct seek accounting and frame rounding; small-read progress; DSF MSB support; preserved channel identity or explicit rejection of loss; automatic PCM-domain processing of DSD; source-aware decode bandwidth; qualified explicit encoder selection; and visible clipping/stability information. These can change output samples and bytes. Release notes distinguish corrections from policy changes, and identify `--dsd-mode legacy` versus `--dsd-decode legacy` accurately.

Do not promise byte compatibility with allocation-dependent DFF corruption. Do not call two different SDM trajectories a regression without spectral/state evidence. Do not promise old throughput for a new profile with a different bandwidth or monitoring contract without measuring both. All generic tests and representative unrelated PCM conversions remain green in every phase.

The initial correctness phases do not change DSP defaults. New effects/profile APIs arrive opt-in. P15 promotes defaults only after numerical, domain/layout and runtime-ISA qualification. A release blocked on a candidate coefficient or mandatory execution test may ship its independent correctness fixes, but must not claim the full mastering engine complete. This separation prevents a long DSP qualification from delaying simple file corruption fixes.

# 12. DSD512/1024 extension design

## 12.1 Packed input without a packed effects graph

P16 adds an optional native DSD **read-block** interface for recognized handlers, separate from `sox_read`. The returned descriptor specifies packed bytes, channel count/order, chronological bit order, valid bits in the last byte, byte layout/stride and frame count. Storage is borrowed until the next read-block call on that handle. The reader owns the buffer; the DSP consumes or copies before the next call. DSF planar blocks and DFF interleaved byte clusters do not masquerade as the same memory layout.

Only the CLI input adapter or a new packed decoder entry point uses this interface. A handle is in either expanded or packed reading mode until a successful seek/reset; mixing the two without reset is rejected. Both use the same single logical cursor and cache ownership. Do not advance `olength` twice or maintain independent logical positions. This is a new byte-access path, not permission to resurrect the redundant MANF remaining counter.

The packed front end produces exactly the same first-stage floating samples as the expanded reference. A first version can unpack into bounded lane-local signs and immediately perform the first half-band stages, avoiding an int32 graph buffer. A byte-contribution lookup formulation is optional only after its coefficient phase/alignment and exact tail handling are proved. For block-vector variants, test all bit offsets and partial last bytes; never read padding as program audio. Reuse the downstream profile, count and kernel contracts unchanged.

## 12.2 Future reconstruction profiles

Keep two profile concepts, not one inherited DSD64 cutoff. For planned mastering512/1024, retain the conservative P = 40 kHz, S = 80 kHz, R = 176.4 kHz policy unless independent product validation justifies a new version. This deliberately caps conservative mastering bandwidth rather than implying every higher native rate must preserve more ultrasonics. The factor is respectively 128 and 256, with additional half-band stages and regenerated final bank/latency manifests.

For planned wideband512/1024, retain R = native/32, P = 0.4R and S = 0.5R: R = 705.6 kHz / 1.4112 MHz; P = 282.24 / 564.48 kHz; S = 352.8 / 705.6 kHz. These are proposed transfer policies, not qualified source-bandwidth claims. DSD1024's wideband intermediate exceeds the required public PCM ceiling; final 705.6 kHz output narrows the effective passband according to the same adapt/strict rule. Do not claim that a 705.6 kHz output preserves a 564.48 kHz passband.

Regenerate stage counts, delay phases, coherent alias sums and performance/traffic measurements. DSD64/128/256 must not regress when the descriptors are extended. A packed optimization is accepted on measured correctness/throughput, not made mandatory by ideology if another bounded front end meets the target.

## 12.3 Future encoding and containers

No DSD512/1024 writer capability is enabled until an exact-rate modulator profile is designed and qualified. New coefficients or a rigorous normalized-coefficient reuse argument must specify NTF/STF behavior, interpolation, state scaling, admitted input, stability/guard bounds, baseband/ultrasonic spectra and scalar/ISA equivalence. Reusing DSD256 coefficients because `freq <= requested` succeeds is prohibited.

DSF256 and future higher rates are documented ecosystem extensions to the older DSF specification's listed rate set. DFF's general uint32 sample-rate field can structurally represent the rates, but that does not certify every player or the more restrictive Edited Master profile. Do not claim a high-rate generic DFF is automatically a SACD Edited Master. [S1, S2]

DoP transport at 512/1024 requires PCM 1.4112/2.8224 MHz respectively. Conversion, file writing and physical transport are separate capabilities. Initially allow only specifically validated file/transport pairs, require explicit selection, and reject unsupported output negotiation rather than falling back to a lower rate or another framing scheme. A successful software payload test is not a hardware DAC compatibility claim. [S3]

P18 requires independent high-rate reference material, the full format/count/packed matrix, acceptable memory/throughput, and documented device/software interoperability. Where reference material or hardware is unavailable, leave the corresponding capability disabled and record the missing qualification. Do not convert a future phase into a misleading current support checkbox.

# 13. Risks, validation gaps and bounded responses

**R1, parser/state regressions.** Small-read fixes can accidentally advance a cached byte too early or mis-handle the first post-seek bit. Mitigation: independent concatenated small-read/slice oracles, one-cluster/one-block boundaries and first-write allocator tests. Owner: P01–P03.

**R2, cross-format seek churn.** Core bookkeeping exposes private counters or rounded seeks elsewhere. Mitigation: the explicit normalized target contract, the demonstrated WAV fix, a named handler inventory and optional-codec coverage. Do not undertake a general decoder rewrite. Owner: P03.

**R3, domain insertion too late.** Fixing only user-effect order leaves gain/mix corruption before the chain. Mitigation: per-input adapters, effective/native signal separation and pre-header planning tests. Owner: P05/P08.

**R4, metadata overreach.** A global speaker-routing rewrite would exceed the integration budget. Mitigation: opaque DSD provenance/layout plus a WAV bridge, conservative invalidation and explicit loss policy. WSD assignments remain unverified. Owner: P04.

**R5, convincing but incomplete filter tests.** A sampled response misses extrema, a final-stage plot misses aliases, or intermediate rounding shifts endpoints. Mitigation: independent high-precision coefficients, image summation, finite-operator oracles, tiny streams and exact clock arithmetic. Owner: P06/P07/P15.

**R6, unqualified encoder default.** Short sine tests miss idle tones, state growth, interpolation overload or rate-specific behavior. Mitigation: fixed profile candidate plus hard promotion gate, independent analysis-v1, guards, admitted envelope and holdout/soak corpus. The supplied short probe is explicitly insufficient. Owner: P09/P10/P15.

**R7a, reference calibration lost during remodulation.** Ordinary half scaling after preserve-level DSD reconstruction introduces an extra 6.0206 dB loss. Mitigation: explicit private reference tags, resolved encoder scale and unity/gain regression tests, without hidden DSD-to-PCM gain. Owner: P05/P08/P10.

**R7, headroom claims beyond the graph.** Float files may still contain graph-clipped samples. Mitigation: preserve default, explicit gain two, pre-clamp counts and no overrange CLI promise. Owner: P07/P08/P14.

**R8, ISA availability mistaken for speed or correctness.** Wider vectors may lose, or global compiler flags may make AVX1 hosts crash. Mitigation: per-TU isolation, OS-state checks, forceable tiers, hardware execution and end-to-end dispatch gates. Owner: P11–P13/P15.

**R9, benchmark host gaps.** The design host is virtual and not a hardware matrix. Mitigation: retain an evidence ledger, conservative unknown-CPU policy and explicit unrun gates. No fabricated Intel/AVX1 results. Owner: P15.

**R10, future rate overclaim.** Numeric fields allow a rate without valid DSP, files or transport. Mitigation: separate disabled capabilities, packed-path parity, exact-rate profile registry and independent P17/P18 gates.

**Remaining external gaps:** authoritative WSD assignment semantics; complete ancillary metadata preservation; licensed Saracon differential testing; physical player/DAC matrix; independent DSD512/1024 material; controlled listening for subjective claims. These are not all mandatory redesigns. They become release gates only for the particular feature/claim they support. Do not claim Saracon equivalence, subjective superiority or universal hardware compatibility from the available evidence.

# 14. Source and evidence references

Repository references are to the attached baseline, not an unreviewed upstream checkout:

* `src/dsf.c`: DSF representation, bit extraction, seek, layout and writer lengths.
* `src/dsdiff.c`: DFF/WSD headers, byte clusters, seek, accumulator allocation and writer accounting.
* `src/formats.c`, `src/formats_i.c`, `src/wav.c`: core read/seek, offset helpers and WAV private counters.
* `src/sox_ng.c`: input balancing/combination, interactive seek, trim optimization, output opening and effects ordering.
* `src/effects.c`, `src/sox_ng.h`: per-channel cloning, public types, sample representation and effect API.
* `src/rate.c`, `src/rate_half_fir.h`: binary64 backend, stage decomposition, option semantics and scalar half-band work.
* `src/sdm.c`, `src/sdm_x86.h`, `src/sdm.h`, `src/dither.c`: coefficients, recurrence, selection, allocation and automatic one-bit path.
* `src/dop.c`: transport payload, markers, buffering and drain.

External sources were used only for their applicable format, convention or instruction-set contracts. Page numbers below are printed page numbers where available; the online PDFs were inspected, including relevant tables.

**S1. Sony, DSF File Format Specification v1.01.** Format fields, channel types, storage order and original enumerated rates, particularly pages 3–5. URL:

```text
https://dsd-guide.com/sites/default/files/white-papers/DSFFileFormatSpec_E.pdf
```

**S2. Philips, DSDIFF 1.5, 2004-04-27.** General chunks and sections 3.2.1–3.3, plus Edited Master restrictions in section 4. URL:

```text
https://www.sonicstudio.com/pdf/dsd/DSDIFF_1.5_Spec.pdf
```

**S3. DoP Open Standard v1.1.** Payload/marker scheme and transport-rate extension. URL:

```text
https://dsd-guide.com/dop-open-standard
```

**S4. Weiss, Saracon Windows manual, version available on 2026-10-07.** Level/modulator discussion and SACD-reference appendix, including 28-bit population limits and measurement-filter conventions. This source is not proof of sox_ng equivalence. URL:

```text
https://weiss.ch/wp-content/uploads/2023/02/saracon-manual-win.pdf
```

**S5. Intel, Architecture Instruction Set Extensions Programming Reference.** CPUID/XGETBV and extended-state requirements; verify against the actual compiler/intrinsics used. URL:

```text
https://www.intel.com/content/dam/develop/external/us/en/documents/319433-024-697869.pdf
```

**S6. GCC, x86 Function Attributes documentation.** Per-function target isolation is one supported implementation mechanism; separate translation units are the chosen default here. URL:

```text
https://gcc.gnu.org/onlinedocs/gcc-12.5.0/gcc/x86-Function-Attributes.html
```

The supplied handoff's vendor performance numbers are deliberately not promoted into acceptance thresholds. The actual design-session JSON/logs remain the authority for what was run here. Requirements, future tests and proposed profile envelopes are labeled as such throughout.

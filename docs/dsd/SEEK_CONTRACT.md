# P03 seek contract and handler inventory

This document records the P03 implementation of `DSD_DESIGN.md` section 4.3.
It applies to **readers**; it does not introduce `SEEK_CUR` or `SEEK_END`.

## Public API and arithmetic

- `sox_seek(ft, offset, SOX_SEEK_SET)` receives **interleaved samples**.
  With `channels = C > 0`, the core passes `offset - offset % C` to the
  handler and, only on success, assigns that target to `ft->olength`.
  Unaligned offsets round **down**; they do not round up to the next frame.
- A zero channel count is rejected. If `signal.length` is known (neither zero
  nor `SOX_UNKNOWN_LEN`), seeking beyond it fails before invoking the handler.
  An exact-end seek succeeds when the handler supports it. `ft->olength`
  and handler-private state are not modified by core preflight failures.
- `sox_read` clamps requests against a *saturating* known-length remainder:
  it returns zero at or beyond logical EOF, without computing a negative
  unsigned difference. `SOX_UNSPEC` (0) and `SOX_UNKNOWN_LEN` (-1) both
  indicate unknown length in the positions where the format API permits them.
  It never performs an extra operation per decoded sample.
- Byte-position helpers use checked integer arithmetic, including the
  representable range of `off_t`. No double conversion or out-of-range
  floating-to-integer cast occurs on the seek path. Unsupported packed
  (non-whole-byte) raw encodings explicitly reject generic byte seeks.

## Audited handlers

| Handler | Normalized target and state | P03 change |
| --- | --- | --- |
| DSF (`dsf.c`) | Frame = samples / channels; block/byte/bit based on frame. Reset block cursor and retained bit position; logical EOF needs no nonexistent block. | Correct unit conversion, preflight physical offset, invalidate block |
| DFF and WSD (`dsdiff.c`) | Frame = samples / channels; seek channel-interleaved byte clusters; reset `cluster_valid` and bit index. The core bounds nonempty DFF audio before trailing MANF. An explicitly empty DSD payload returns zero without entering metadata. | Correct unit conversion, zero-audio reads, and checked byte/offset bounds |
| WAV PCM, A-law, mu-law (`wav.c`) | Sample offset converted to bytes by the checked helper; remaining private frames derived from the original total, not prior remaining count. | Correct private rewind, checked seek arithmetic |
| WAV49 GSM (`wav.c`) | Predictive decoder history cannot be restored by a byte seek; return unsupported without moving or changing the decoder. | Replace incorrect block rounding/success with explicit rejection |
| WAV MS/IMA ADPCM (`wav.c`) | Unaligned packed encodings cannot honor this generic seek method. | Preserve explicit unsupported result |
| Raw PCM (`raw.c`) | Sample offset directly to checked byte position. | Reject narrowing/overflow, no float arithmetic |
| MSU PCM (`msupcm.c`) | 16-bit interleaved samples: header + 2 × sample offset. | Fix missing factor of two; shared checked helper |
| PRC A-law (`prc.c`) | Encoded 8-bit samples from private data start. | Shared checked helper; other encoding unsupported |
| SMP (`smp.c`) | Linear bytes from sample-data start; remaining samples = original length - sample offset. | Remove upward rounding and header-offset subtraction |
| FLAC (`flac.c`) | Seek pending until next read; discard old leftovers before decoder seek, reset EOF, and signal decoder failure. | Restore EOF after prior full read; diagnostics for deferred failure |
| Vorbis (`vorbis.c`) | Decode-unit frame = samples / channels; old byte buffer and EOF invalidated only on successful seek. | Reset cache and bound signed frame conversion |
| Opus (`opus.c`) | Decode-unit frame = samples / channels; on successful decoder seek, discard previously decoded samples and reset EOF; on failure, keep the cache and EOF state. | Reject signed frame conversion overflow; clear buffered state only after success |
| WavPack (`wavpack.c`) | Decode-unit frame = samples / channels. | Reject unsigned 32-bit seek-index truncation |

No decoder-specific pre-roll or generic random-access redesign was introduced.
The bounded PCM read check is at each `sox_read` invocation, not inside a
per-sample decode loop.

## CLI callers

The interactive `>` / `<` controls maintain `read_wide_samples` in **frames**.
They now multiply by channels with overflow detection, pass interleaved
samples to `sox_seek`, and update their display/read counters only when seek
succeeds. The first-effect `optimize_trim` shortcut already passes an
interleaved sample offset; it updates its count from the committed core
position after success. It remains a native/PCM seek shortcut; later
DSD-reconstruction planning must handle reconstruction pre-roll separately.

## Executable checks

- `tests/dsd/run.py --phase P03` asserts all original P03 cases become hard
  passes while leaving P04's Type 5 channel-identity XFAIL unchanged.
- `tests/dsd/test_seek.py` generates CC0 independent DSF (LSB/MSB), DFF,
  WSD, WAV PCM, raw PCM and MSU PCM fixtures; launches
  `test/dsd_test_seek_contract`, which compares complete read-after-seek
  slices with an independent full sequential decoding pass. P00/P02 separately
  bind the chronological truth of DSD fixture bytes.
- The probe checks aligned/unaligned offsets, positions within and across
  native bytes/blocks, seek-after-read and seek-after-EOF, zero-length audio,
  exact-end and out-of-range requests, private-state reset, `off_t`/sample
  multiplication overflow, zero channels and no movement after rejection.
- WAV49 GSM has an explicit negative test proving that unsupported seeks do
  not move either core or physical position. Optimized WAV trim output is
  byte-compared with both the source's known PCM slice and a sequential path.
- The matrix creates optional FLAC/Vorbis/Opus/WavPack fixtures and tests
  when the configured build supports them, but records missing dependencies
  as *unrun*, not passes.

Full command, host and benchmark qualifications are in `handoffs/P03.md` and
`tests/dsd/results/P03/`. The preexisting P00–P02 evidence remains preserved.

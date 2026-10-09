# P04 DSD channel identity contract

This phase carries **channel identity** as owned metadata, separate from the
chronological audio samples. It does not introduce a signal-processing engine,
a global channel-routing model, or automatic DSD-to-PCM reconstruction.

## Public C API

Include `sox_dsd.h` after or instead of `sox_ng.h`. Existing SoX structs and
entry points have not changed. The new `sox_dsd_layout_t` is opaque and owned:

- `sox_dsd_get_layout(format, &layout)` returns an independent allocation,
  readable after the format is closed. Free it with `sox_dsd_layout_free`.
  `sox_dsd_layout_copy` makes another independent allocation. Channel getters
  copy the role, optional four-byte DFF ID and validity bit into caller memory.
- `sox_dsd_get_stream_info` copies the integer native rate, channel count,
  known-length flag and frames per channel, container, physical DSD bit order,
  original DSF type, original DFF LSCO/presence and opaque WSD assignment.
  Returned records use semantic `version=1` and `size=sizeof(record)`;
  unsupported versions and records shorter than their required prefix are
  rejected. Version 1 accepts a recognized shorter prefix and copies only
  fields within the caller-provided byte count, preserving that count.
- `sox_dsd_layout_new`, `set_role`, `set_dff_id`, `set_dsf_type`, and
  `set_dff_lsco` construct a metadata assignment. Mutating a role invalidates
  an incompatible original DSF type/DFF ID/LSCO. `sox_dsd_layout_map` takes
  *zero-based source indices* for a one-to-one permutation or subset, retaining
  the corresponding identities but clearing order-specific container provenance.
  Repeated indices are not a permutation and are rejected. Use
  `sox_dsd_layout_invalidate` after mixing, synthesis or an unknown mapping.
- `sox_dsd_layout_wav_mask` returns an exact speaker bitmask and, optionally,
  a permutation from original channels to ascending-mask order; it rejects
  unknown or duplicated speaker positions. There is no audio movement in the
  getter. Apply that permutation to samples before writing the WAV header.
- `sox_open_write_dsd` accepts the usual open-write arguments plus an optional
  layout; it clones the layout into the recognized format handler **before**
  `startwrite`. The caller may free its layout immediately. `sox_close` frees
  the format-private copy. Incompatible channel counts and unrepresentable DSF
  assignments are rejected before creating or truncating the output.

All metadata operations are per-file or per-effect-plan; none runs in a DSD
sample-conversion loop. The format-private layout is not shared by pointer with
application code. There is no comment-tag or global-pointer side channel.

## Native container semantics

- **DSF:** types 1–7 are distinct ordered layouts. Type 4 (FL, FR, BL, BR)
  and Type 5 (FL, FR, FC, LFE) both have four channels but are not
  interchangeable. Unknown role lists cannot be represented as a valid DSF
  channel type. Both DSF bit-packing conventions retain their original read
  order when repacked; their bit chronology does not change.
- **DSDIFF/DFF:** CHNL's literal four-byte channel IDs define the order of
  samples. Unknown/context IDs survive unchanged DFF-to-DFF output. Optional
  LSCO is retained verbatim on an unchanged stream, even if reserved; a known
  LSCO value contradicting CHNL causes a warning, not sample reordering or a
  fabricated identity. DFF `LS  `/`RS  ` IDs do not resolve side-versus-back
  angle. A DSF surround-to-DFF conversion uses these conventional DFF IDs;
  the reverse DFF-to-DSF conversion needs an explicit role assignment when the
  distinction is not actually documented by the source.
- **WSD:** `ch_asn` is exposed as an uninterpreted original integer. It is not
  treated as an authoritative named-speaker map.
- **WAVE_FORMAT_EXTENSIBLE:** representable positions yield the exact mask and
  samples ordered by ascending mask bit, including IEEE float output. Type 5
  yields mask `0x0000000f`, while Type 4 yields `0x00000033`. Unnamed layouts
  carry mask 0 instead of a guessed role map. The extension cannot carry an
  assignment in compressed WAV or the explicitly nonextensible `wavpcm` alias.
  On reading a multichannel WAV mask, front-center (0x4) denotes **FC**, not
  a single-channel mono programme; single-channel front-center may be mono.

## CLI and loss behavior

`--dsd-layout FL,FR,FC,LFE` assigns explicit output roles in sample order;
accepted names are `MONO`, `FL`, `FR`, `FC`, `LFE`, `BL`, `BR`, `SL`, `SR`, and
`unknown`. This option is needed for a multichannel output whose source has
no defensible speaker positions, or for an intentional new assignment. It
does **not** transform audio automatically, only names existing output
channels. An existing parsed `remix` that is provably one-to-one moves the
corresponding labels with its audio. An explicit `channels N` with the same
input channel count is a no-op and retains identity; actual reductions,
expansions, mixes and unknown transforms invalidate inherited identity. A
final WAV-specific `remix` is added *only* when required to produce the
physical mask order.

When first encoding ordinary mono/stereo PCM WAV to DSD, the absence of a
speaker mask implies the conventional mono or FL/FR assignment. Explicit
extensible speaker identities take precedence; an unrepresentable **nonzero**
extensible mask is not silently replaced by conventional stereo. Ambiguous
multichannel PCM still requires an explicit assignment for DSF output.
Ordinary PCM-to-PCM behavior does not change.

Loss of known identity to a destination that cannot encode it **fails before
output creation**. `--dsd-layout-loss warn` authorizes an explicit diagnostic
and metadata loss at a generic PCM destination or writes an unspecified WAV
mask; it never authorizes false DSF channel type. The policy applies to DSD
sources or explicit assignments, not to ordinary PCM-to-PCM workflows.

Examples:

```sh
# Explicit side-versus-back assignment for an ambiguous DFF source:
sox_ng in.dff --dsd-layout FL,FR,BL,BR out.dsf
# Allow loss only if intentional:
sox_ng in.dsf --dsd-layout-loss warn -e signed-integer -b 16 out.raw
```

## Evidence and limits

`tests/dsd/test_layout.c` exercises ownership, version checks, original type
and ID preservation, permutation/invalidating behavior and metadata queried
after input close. `tests/dsd/test_layout.py` constructs independent DFF, WSD
and PCM WAV fixtures with distinct per-channel sequences. It checks decoded
WAV data in mask order, exact DFF ID/LSCO round trips, no-op and changing
`channels` effects, PCM-to-DSD mono/stereo assignment, extensible masks and
preflight loss rejection without creating files. Fixture content hashes live
under `tests/dsd/fixtures/p04`.

A P04-only contract does not claim DSD reconstruction quality, encoder quality,
or hardware conformance, which belong to later phases.

# P18 capability/compatibility ledger — 2026-10-21

**Release decision: all DSD512/DSD1024 capabilities disabled.** P17 DSP is a development candidate (`PASS_DEVELOPMENT_TESTS_UNQUALIFIED`), not a qualified production chain. P18 authorization explicitly withholds enablement (`amendments/P18_AUTHORIZATION_2026-10-21.md`). The machine-readable row-level record is `P18_RELEASE_MANIFEST.json`, verified by `tests/dsd/seal_p18_manifest.py`.

## Capability decisions

| Native rate | Endpoint | Operation | Required transport PCM | Decision | Independent qualification |
| --- | --- | --- | --- | --- | --- |
| DSD512 (22,579,200 Hz) | DSF | Read | — | Refuse: P17 unqualified | Unrun external source/cross-reader |
| DSD512 | DSF | Write | — | Refuse: P17 unqualified | Unrun real-media writing/player |
| DSD512 | DSDIFF (general) | Read | — | Refuse: P17 unqualified | Unrun external source/cross-reader |
| DSD512 | DSDIFF (general) | Write | — | Refuse: P17 unqualified | Unrun real-media writing/player |
| DSD512 | DoP | Transport | 1,411,200 Hz | Refuse: P17 unqualified | Unrun device and host transport |
| DSD512 | WSD | Read | — | Refuse: not P18-validated | Unrun; safety coverage only |
| DSD1024 (45,158,400 Hz) | DSF | Read | — | Refuse: P17 unqualified | Unrun external source/cross-reader |
| DSD1024 | DSF | Write | — | Refuse: P17 unqualified | Unrun real-media writing/player |
| DSD1024 | DSDIFF (general) | Read | — | Refuse: P17 unqualified | Unrun external source/cross-reader |
| DSD1024 | DSDIFF (general) | Write | — | Refuse: P17 unqualified | Unrun real-media writing/player |
| DSD1024 | DoP | Transport | 2,822,400 Hz | Refuse: P17 unqualified | Unrun device and host transport |
| DSD1024 | WSD | Read | — | Refuse: not P18-validated | Unrun; safety coverage only |

The per-pair decision is independent of other native rates or of a container's field capacity. The existing DSD64/128/256 registry, coefficient files, and default processing paths are unchanged. High-rate input is not decoded, repacked or accepted through `SOX_DSD_PACKED_INPUT`; high-rate output is rejected in CLI preflight (auto/native modes), at `open_write()` before generic format-rate substitution or destination truncation (default/legacy modes and direct library calls), and at format-writer startup as defense in depth. The requested container is determined from the actual handler, while the planner recognizes case-insensitive `.DFF` and `-t DFF` as DSDIFF. DoP effect startup refuses a high-rate clock even when the output clock equals native/16. WSD, which has no P18 high-rate qualification, also refuses these two native-rate labels. Neither a CLI profile name nor a private P17 candidate enables a gate.

## Format specifications and representation

**DSF:** Sony's *DSF File Format Specification* v1.01 defines a 32-bit sample-frequency field, 64-bit file size and sample count, channel-block data layout and format metadata. Those widths can physically represent 22.5792/45.1584 MHz, but the older documented rate list does not certify these ecosystem extensions or interoperable readers. This implementation uses validated 4096-byte per-channel blocks, LSB/MSB chronology, `ceil(frames/32768) * 4096 * channels` bytes, a physical data-chunk header of 12 bytes, and no additional logical frames for block padding. Integer overflow and missing physical bytes are errors, not wrapped extents.

**DSDIFF:** Philips' *DSDIFF v1.5* defines an FS property with a 32-bit sample-rate value and 64-bit chunk lengths. A general DSDIFF interchange file may structurally store a future rate, but the **SACD Edited Master** is a more restrictive profile. Its section 4.3 requires 2,822,400 Hz and additional marker/channel/time constraints. **A future high-rate general DFF must never be labeled an SACD Edited Master.** Audio is interleaved channel bytes, chronological MSB first. The last incomplete byte is filled with the inherited 0x69 DSD silence pattern and an odd chunk payload has one external zero pad. For `frames` and `channels`, the declared audio bytes are `ceil(frames/8) * channels`, and the chunk physical span is `12 + bytes + (bytes mod 2)`; checked uint64 arithmetic is mandatory. Sparse mathematical tests exercise simulated one-hour/24-hour rates and huge counters without producing forbidden high-rate files.

**DoP:** The *DoP open Standard* v1.1 defines a 24-bit PCM sample containing a 16-bit chronological DSD payload and an eight-bit marker alternating **0x05, 0xFA**. One DoP sample carries 16 DSD frames **per channel**. The ordinary same-channel transport requires exactly `native_hz / 16`; hence DSD512 = **1,411,200 Hz** PCM and DSD1024 = **2,822,400 Hz** PCM. The specification also describes an alternate channel-pair transport for particular links; P18 does **not** implement that alternate scheme. Synthetic vectors assert chronology, marker phase, channel identity and partial-word completion. Rate arithmetic and software bit packing do **not** certify any USB/ASIO/CoreAudio/ALSA destination or DAC at those rates.

Primary sources reviewed:

- Sony, *DSF File Format Specification*, v1.01 (Sony Corporation; referenced in the approved DSD design; public scan: https://pt.scribd.com/document/720070725/DSF-file-format-specification-E)
- Philips, *Direct Stream Digital Interchange File Format*, v1.5 (2004-04-27), sections 2.2, 3.2.1, 3.3 and 4.3: https://www.sonicstudio.com/pdf/dsd/DSDIFF_1.5_Spec.pdf
- *DoP open Standard*, v1.1, sections 2 and 3: https://dsd-guide.com/sites/default/files/white-papers/DoP_openStandard_1v1.pdf

## Evidence versus unrun gates

**Executable/local:** P18 C registry/DoP startup/int overflow tests; independently authored Python reference parser and generator (198 high-rate DSF/DFF structural examples; 36 high-rate DoP byte/marker vectors); real SoX DSF/DFF refusal cases, including packed input; real SoX writer preflight refusals with no target file; default/legacy no-downrate and uppercase DFF diagnostic cases; direct `sox_open_write()` refusal retaining preexisting destination bytes; DSD64 native roundtrips and DSD64/128/256 DSF/DFF writer parity; inherited P16 packed, P17 private candidate tests, P00-P14 regressions. No high-rate file is written by the production path.

**Not independently qualified:** external/licensed/reference DSD512/1024 recordings and cross-decoder readback; other software/player compatibility; real high-rate file writer round trips; real DoP512/1024 transport; physical DAC or driver compatibility; P17 long-duration/numerical/spectral/ISA certificates; high-rate end-to-end throughput, memory and storage traffic. Their result is **UNRUN**, not PASS. A benchmark of lower-rate/experimental private DSP cannot be recast as evidence of file/DoP capability. P15's two standing source-qualification obligations remain OPEN.

## Future enablement contract (not part of this authorization)

Release engineering would need a passed *exact-rate DSP* certificate bound to source and ISA, per-rate/container writer plus external-software roundtrip and volume/length proof, and a separate destination-aware DoP transport qualification. Promotion must be an explicit reviewed policy change with matching manifest updates and tests, not an inference from the numeric field widths. P18 itself promotes nothing.

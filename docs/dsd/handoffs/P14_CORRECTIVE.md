# P14 corrective handoff — 2026-10-12

## Authority and disposition

This narrowly scoped corrective continuation starts from `sox_ng-P14-complete-source-2026-10-12.tar.gz` (SHA-256 `98e9da0f3a9b3576aeafbd6c27e227e2bb2e74c331cb3726814d4e5fef2490ec`). The authorities are `docs/dsd/sows/P14.md` and `docs/dsd/DSD_DESIGN.md` (notably sections 6.4 and 9.1). P00–P13 are already integrated. The supplied source is a `git archive`-style tree with no `.git`. The original `docs/dsd/handoffs/P14.md` and all previous result files remain intact; this handoff *adds* the corrective disposition.

**Scope:** Four independently identified P14 defects corrected through three local changes. There are no changes to FIR/SDM DSP algorithms, filter coefficients, dispatch, automatic ISA policies, public ABI, conversion scheduling, generic PCM processing, or historical benchmark evidence.

1. **Plan-only destination safety.** `src/sox_ng.c` now validates every named plan-report destination before opening it, using the same input-identity and overwrite policy as conversion reports; `--dsd-report -` writes the existing P05 planning JSON to stdout, not to a literal dash-named file. Destination checking no longer implicitly creates a runtime observer. The P05 planning JSON shape is unchanged.
2. **Not-yet-existing output aliases.** Existing named-path and inode checks remain. Immediately after creating the output writer, but **before audio processing**, reporting compares its actual path's file identity with the report destination. Spelling variants such as `out.dsf`, `./out.dsf`, and absolute-versus-relative variants fail with status 2. This guard disables report publication in the alias-failure cleanup path, where writing JSON to the audio stream would repeat the defect; normal cleanup removes any incomplete regular-file output. Successful conversions still close the audio before independently publishing JSON.
3. **Actual source metadata.** `src/dsd_stats.{c,h}` receives read-only pointers to the already-open input handles and adds to v1 `source[]` the actual input `sample_rate_hz` (PCM only), `encoding`, `bits_per_sample`, and file handler `container`. PCM now has `native_hz: null` rather than repurposing the DSD bit-clock field for PCM; a generic WAV stream-info bridge previously filled that field with the PCM sampling frequency. DSD native clock, bit ordering, and channel roles retain their existing fields. New schema fields are *additive* and optional in the existing v1 schema for consumer compatibility.
4. **Decoder latency separation.** The existing actual decoder record now has `latency`, with front-end FIR lookahead in native frames and seconds derived from the selected certified profile and native rate. Identity/bypassed final SRC has exactly zero SRC lookahead; an active multistage SRC does not expose a reliable centered-delay/streaming lookahead via the current rate API, so that field is null with an explicit reason rather than a number invented from taps or phase. FIFO occupancy is schedule-dependent; buffering latency and consequently total latency are likewise null, each with a specific explanation. An available FIFO capacity is **not** presented as measured buffering time. No decoder or SRC state is modified during reporting. This is the authority's explicitly permitted truthful-unknown behavior, not a latency-performance qualification.

## Focused regression cases

`tests/dsd/test_p14.py` now exercises 16 cases (previously 12), adding:

- Destructive plan-only input/report alias; source digest unchanged, nonzero exit, no opened audio; `--no-clobber` refusal; unchanged P05 plan JSON in distinct file and on stdout with `--dsd-report -`; absence of a literal dash file.
- Not-yet-existing `./out.dsf` versus `out.dsf` and absolute-versus-relative alias refusals; nonzero exit, diagnostic, no retained incomplete audio; distinct destinations still produce byte-identical DSD audio and valid JSON.
- Two actual 88.2-kHz signed PCM WAV sources, 16-bit and 32-bit, encoded by the linked P10 candidate path; `wav`, sample rate, encoding and widths all come from their opened source handlers, while native DSD reports keep the DSD clock and bit order.
- Mastering DSD64 to 88.2 kHz (SRC bypass), DSD64 to 44.1 kHz (SRC active) and DSD128 to 176.4 kHz (different FIR delay). Checks verified timebases, exact bypass zero, explicitly qualified nulls, and byte-identical audio with/without reporting.

The existing P14 report failure, cancellation, stdout alias, source hardlink, forced ISA identity, DoP, overload and original-native-bit numerical cases still run unmodified.

## Tests and resulting evidence

Validation executes in a separate throwaway build tree. Original P00–P14 result files in the input archive are not rewritten; *new* corrective results and path-sanitized command logs are under `tests/dsd/results/P14/corrective/`. The generic and DSD test targets use the inherited runner without modified thresholds.

| Gate | Outcome |
|---|---|
| `autoreconf -fi` | PASS, exit 0 |
| `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'` | PASS, exit 0 |
| `make -j2` | PASS, exit 0 |
| `make check` | PASS, exit 0 |
| P14 focused integration | PASS, **16/16** |
| `make check-dsd DSD_PHASE=P14` | PASS, exit 0, inherited phase regressions and P14 independent numerical tests |
| Standalone P14 runner | PASS, 36/36 |
| Standalone P14 measurement runner | PASS, 10/10 independent checks; inherited P10/reference-corpus qualifications still open |
| Standalone P14 benchmark runner | PASS, 36/36 **development-only** cases; no silicon qualification |
| P14 observer-overhead benchmark | PASS, four arms with identical audio hashes; profiling observations are not configuration defaults |
| Supplemental `make distdir` | BLOCKED by absent `tbl`, `nroff`, `pdfroff` tools (exit 2), not claimed as a pass; manually assembled source-only archive independently verified |

`P00_SHA256SUMS.txt` is deliberately regenerated only after final files are present. Its final entry count and verification receipt are in `tests/dsd/results/P14/corrective/validation.json`. Historical original P00–P13 evidence is byte-for-byte unchanged; the P00 manifest itself is self-excluding and is updated for the new source/files.

## Open qualifications and next handoff

- **P13 physical-silicon performance qualification remains OPEN.** No P14 or corrective timing determines an ISA default. Automatic FIR stays SSE2 when available; mastering SDM stays scalar. Neither FMA tier is promoted.
- The Intel Xeon Platinum 8488C comparison is the previous **ten matching 80-bit SHA-256 prefixes** on one specified stimulus, not a general full-hash identity certificate or a performance qualification.
- The original P14 separate physical/sustained-soak/reference-corpus limitations remain as declared in `docs/dsd/handoffs/P14.md`. Decoder active-SRC and scheduling-dependent latency values are explicitly **unquantified**, not zero.
- Next permitted phase remains **P15**, subject to its authority and gates. These P14 corrections do not authorize physical performance claims, coefficient changes or dispatch promotion.

Read `docs/dsd/handoffs/P14_CORRECTIVE_CHECKPOINT.md` to resume, then verify the archived P00 inventory before building. Run `autoreconf -fi` prior to configuration. No `.git`, compilation objects or private machine paths are shipped in the source archive.

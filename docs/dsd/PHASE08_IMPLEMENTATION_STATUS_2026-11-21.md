# Phase 08 binary64 implementation and qualification status

**Baseline:** `595d401a244fd0329fa39229b0a6d1918bcf00ff`
**Implementation date:** 2026-11-21
**Authority:** [owner decisions D1–D16](amendments/PHASE08_OWNER_DECISIONS_2026-11-20.md), retained *byte-for-byte* as signed. The [corrected specification](amendments/PHASE08_CORRECTED_SPEC_2026-11-20.md) is retained byte-for-byte and is read as amended by those decisions. The source design document is historical; its superseded decoder and native-float statements are not current requirements.

## Implemented route

The **default/native DSD decoder** is the unified `mastering` decoder: the
former v1 bank. `wideband` is the only other decoder. `--decode mastering`,
`dsdpcm -p mastering`, and implicit reconstruction choose the same bank.
Canonical decoder IDs are `decode.mastering.dsdNNN` and
`decode.wideband.dsdNNN`. Old `mastering.v1`, `mastering.v2`,
`wideband.v1`, `conservative` and `legacy` decoder selectors are removed.
DSD64 mastering reconstructs through 20/40 kHz at 88.2 kHz intermediate;
DSD128 through 30/60 kHz at 176.4 kHz intermediate. DSD256–1024 keep
the *original* filters and clocks on this binary64 line, not the upstream
1.1.2 changes. The manual's profile/clock and phase claims apply to the
selected frontend and remain subject to bandwidth policy.

**Encoder identity is unchanged:** DSD64/128 use versioned
`encode.mastering.v3.dsd64/128` and their certified resonator with **unity
input gain** by default and the frozen §7.1 v1 front end. DSD256 uses
`encode.mastering.v1.dsd256`; DSD512/1024 use
`encode.mastering.v2.dsd512/1024`. Neither the upstream SDM-8 encoder
migration nor its default 0.9 gain was imported. D3 freezes prefilter
coefficients; the later review/refactoring of the v1 front end is *out of
scope*.

**Levels/overrange:** native binary64 FLOAT32/64 conversion preserves
representable finite overshoots in `--dsd-clip warn`, counts `x >= 1 || x < -1`
and emits one warning on stderr and into `warnings[]` when reporting is
active. Counting and refusal do not depend on `--report`. ERROR rejects
these cases at the same adapter boundary as ordinary SoX after `-v` and
`--dsd-level`, with a failed report when requested. No bytes belonging
to a failed processing block are emitted. Previously completed pipe blocks
cannot be retracted. In tested regular-file conversion, a failed output file
is removed. The default integer SoX path retains its existing documented
saturation at the graph boundary. Default DSD64/128 modulator warn clipping
remains at 0.5 and error remains fail-closed. 0 dB gain uses identity.

## Numerical and release gates

| Owner item | What was checked | Status |
| --- | --- | --- |
| D7 | Unversioned decoder CLI/API plan/actual identity; no v2/conservative/legacy; existing v1 coefficients and clocks at all rates | PASS on finite tested cases |
| D2/D3 | Encoder IDs and source/prefilter/certified coefficients unchanged versus `595d401` | PASS on source identity; existing encoder suites run |
| D9/D10 | Native FLOAT64/FLOAT32 warn/error without report, peak/count, `-v`, `--dsd-level`, pipe prior-block and regular-file failure semantics | PASS on tested physical DSD64 cases |
| D13 | Hashes of historic accepted source/coefficients and v2 fixtures checked against exact git predecessor; deliberate mutation fails | PASS; predecessor never updated |
| D11 P3 | 64 finite, independent long-double full-convolution DSD64/128 mastering/wideband checks plus conditional forward-envelope | FINITE PASS; universal P3 and final SRC bound OPEN |
| D11 P2 | Frozen encoder path and 595d401 coefficient identity, but no universal same-transfer operator/arithmetic derivation yet | OPEN |
| D6 numeric `pow` | Formula and 0 dB identity defined; runtime-specific `pow` error bound unadopted | OPEN |
| D16 | 19 accepted v2 samples preserved unmodified; no owner-approved unified decoder references exist | OPEN, awaiting owner sign-off |
| D12 | Audited harness `dsdqual/analysis.py` retained byte-for-byte, numeric parity against independent `audited_spectrum.py`; analysis-v1 frozen self-test | FINITE PASS |
| D4 spur | Frozen analysis-v1 first measurements of physical v3 DSD64/128, low-level coherent 997 Hz and silence | MEASURED; target reporting only, NOT QUALIFIED |
| D4 other gates | Front-end 185/180 dB and 95% response, gain, nominal 28-bit windows and cross-ISA v3 measurements | EXISTING EVIDENCE; not wholly requalified here |
| D8 | No automatic binary64 routing; no release/version bump | NO ACTION (owner-controlled) |

The mathematical approach, assumptions, remaining proof obligations and
permitted scope are in [the arithmetic proposal](PHASE08_ARITHMETIC_BOUND_PROPOSAL_2026-11-21.md).
A finite corpus cannot establish a bound on **every** accepted input.
The unchanged v2 reference words are forbidden as a unified-decoder oracle
and the `2^-48` allowance is restricted to those 19 historical samples.

## How to reproduce the scoped tests

```sh
# After applying the git bundle/patch on exactly 595d401 and configuring:
make -j8
make check-phase08 PHASE08_RESULTS=/tmp/phase08-evidence
make check-pcm64 PCM64_SUITE=decode PCM64_RESULTS=/tmp/phase08-decoder
make check-pcm64 PCM64_SUITE=encode PCM64_RESULTS=/tmp/phase08-encoder
make check-pcm64 PCM64_SUITE=transcode PCM64_RESULTS=/tmp/phase08-transcode
make check-dsd-cli
```

Additional regression evidence on the Phase 08 patched tree: P05 plan unit
187 assertions and CLI planner 160/160; P06 decoder 93,642 assertions;
P07 integration 66/66; P08 integration 28/28; P16 packed-input
integration quick subset 11/11 and its C DSP matrix 4,320/4,320
(986,880 assertions); P17 unit 32,881 assertions. Historical P05
full runner was interrupted after passing its first components, so it is
not reported as a completed suite. The historical v2 accepted-reference
qualification is not a valid oracle for the unified decoder.

`make check-phase08` intentionally returns zero when **finite** test cases
pass while reporting outstanding owner proof/approval gates as OPEN. It does
*not* signal a certified release. Source/binary correspondence and the full
D11 CPU/OS/format matrix must be established separately before owner sign-off.

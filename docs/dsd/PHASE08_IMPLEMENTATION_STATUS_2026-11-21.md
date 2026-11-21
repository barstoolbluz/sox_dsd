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
| D9/D10 | Physical DSD64 warning/error, pipe/file failure; exact injected adapter +/-1, nextafter neighbors and NaN/Inf on ordinary/native paths, float32/float64/int24, `-v`, `--dsd-level`, report/no-report | PASS for tested Linux/ELF routes |
| D13 | Hashes of historic accepted source/coefficients and v2 fixtures checked against exact git predecessor; deliberate mutation fails | PASS; predecessor never updated |
| D11 P3 | 64 native FIR cases plus 32 independent 96 kHz final-SRC cases with exact source-pinned taps and 2 missing-tail mutants | FINITE PASS; universal FIR/FFT4G/SRC bounds OPEN |
| D11 P2 | Focused 595d401 encoder pins, 8 working-SRC/FIR, 8 source-derived 32x native-SRC and 2 resonator-input headroom witnesses, 4 mutants | FINITE PASS; universal arithmetic/composition OPEN |
| D6 numeric `pow` | 41 runtime `pow` (headroom) and `exp` (ordinary gain) sample comparisons against high-precision oracle | FINITE PASS; supported worst-case libm limit OPEN |
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

## November 21 independent-review corrective (R08-D01/D02)

R08-D02 is addressed by a *qualification-only* ELF interposer placed at the
public decoder return. Both ordinary and native routes execute their actual
adapter/clip code with injected exact +1, -1, nextafter neighbors and
nonfinite values. The existing `float_boundary.py` still verifies physical
warn/error behavior and no partial failed block; it now also checks 26
injected ordinary/native parity scenarios and four physical `--dsd-level`
parity scenarios with and without a report. It tests FLOAT32, FLOAT64, and
signed-integer 24-bit outputs. The injection mechanism is Linux/ELF-specific;
this is a scoped pass, not an assertion about an untested macOS ABI.

R08-D01 has **additional finite qualification evidence**, but has **not
been universally discharged**: the actual 32x encoder native SRC and
96 kHz decoder final SRC are evaluated through the existing source-bound
operator snapshots. The independent decoder oracle includes the additional
finite-tail word that the live SRC consumes before output trimming.
The bound proposal records the actual operator families and remaining
arithmetic gaps. A 41-case `libm` witness distinguishes headroom `pow` from
ordinary gain `exp`. No production DSP source or certified coefficient
was changed. Owner D11 and D6 universal proof/acceptance remain OPEN;
D16 and D4 owner gates are unaffected.

The extended `make check-phase08` target executes these new finite cases
and records their digest-bound results in `phase08-gates.json`. A passing
target is **not** authorization for 2.0.0 release.

## November 21 D11 proof-accounting follow-up

A source-pinned, test-only [D11 arithmetic accounting harness](PHASE08_D11_OWNER_REVIEW_2026-11-21.md)
now computes exact coefficient norms per SRC interpolation phase, the
remaining FIR/polyphase gamma terms and a conditional P2/P3 composition. It
reuses the 64 native decoder cases, 32 final-SRC cases, eight working-SRC
and eight native-SRC cases, 41 libm samples, and six historical negative
controls. It independently rechecks 41 C `strtod` plus dynamic libm calls,
288 sampled SRC rows, and refuses mutated receipts or operator digests.

The target adds `d11-accounting` to `phase08-gates.json`. Its PASS means
only that *conditional numerical accounting and finite checks agree*.
**D11's all-input FFT4G source-to-binary proof and D6's guaranteed libm
maximum remain OPEN**; no owner-approved D11 number, reference replacement,
release or routing authorization is implied. A separate owner decision to
defer, amend or commission those proofs is documented in the review record.
Production DSP and the certified encoder are unchanged.

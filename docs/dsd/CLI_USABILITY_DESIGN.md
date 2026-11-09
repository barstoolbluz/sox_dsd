# SoX DSD CLI redesign: design and verification

Implementation date: November 2, 2026. Authoritative starting revision:
`ddc03469e` (SoX DSD 1.0.4). This file documents the actual
implementation, not a proposed interface.

## Design decisions

1. **Keep SoX grammar.** File and effect parsing still uses the established
   `sox [options] input [output-options] output [effects]` parser. Numeric
   `-r`, `-b`, `-c`, `-t` and PCM-only processing are unchanged.
   Existing SoX option prefixes `--enc`, `--enco`, `--encod` (encoding),
   `--rep` (replay gain), `--pla` (play-rate arg), and `--de` (default
   device) retain their established meaning alongside the new DSD options.
2. **Route from endpoints.** The existing DSD planner activates only when
   the input/output requires DSD, a DSD effect is present, or DSD planning
   or reporting is selected. DSF/DSDIFF input to PCM selects qualified
   reconstruction. PCM input to a native DSF/DSDIFF destination selects
   the qualified encoder. Compatible DSF/DSDIFF changes repack pulses
   with no PCM reconstruction or modulation. PCM-only operations bypass
   the DSD planner.
3. **Remove the opt-in tax.** The previous `--dsd-mode auto` is implicit
   for ordinary DSD conversions. `--dsd-mode native` remains useful to
   reject any conversion that would require PCM. Explicit legacy mode
   is retained as a compatibility selector: DSD endpoints still execute
   the qualified preflight graph, including rate changes, PCM reconstruction,
   and modulation. Only PCM-only commands retain the traditional unplanned
   SoX path. To exercise the historic unqualified modulator deliberately,
   use the low-level `sdm` effect, not an implicit container conversion.
4. **Named output clocks.** `-r dsd64` through `-r dsd1024`, independent of
   case, map to existing qualified DSD clocks. They are allowed only as
   output rates for DSF/DSDIFF. Existing integer and `k`-suffix clocks
   retain their original semantics.
5. **Unify mastering defaults.** Omitting `--decode` and selecting
   `--decode mastering` both select the qualified mastering-v1 bank for
   the actual native input clock; `--decode wideband` is the one
   alternative. (In 1.0.x and 1.1.0 the default was a mastering-v2 bank,
   removed in 1.1.1.) Explicit versioned IDs preserve reproducibility. The
   encoder selects the qualified mastering-v1 modulator at every rate
   (until 2026-11-07, mastering-v2 at DSD512/1024); the v2 encoder remains
   selectable there by its exact ID.
6. **Reuse DoP.** `--dop` appends the existing terminal `dop` effect.
   The planner validates input type, exact carrier clock, signed 24-bit
   lossless output, and effect ordering. DoP is not PCM reconstruction.
7. **Observe, do not alter.** `--plan` invokes the existing preflight
   and writes JSON without audio output. `--report` activates the
   existing runtime report observer, which cannot select a processing
   profile, output rate, or effect. Unused explicit decoder/encoder
   selectors fail before output creation.
8. **No DSP coefficient changes.** The FIR banks, modulators, qualified
   profiles, sample conversion code, SIMD dispatch, and format handler
   implementations are unchanged.

## Migration and placement

See [MIGRATION_P15.md](MIGRATION_P15.md) for the old and new spellings.
The removed DSD-only aliases are not silently accepted. SoX and SoX-NG
options remain in their ordinary positions. A DSD clock name before the
input or with a PCM output produces an error. The user-facing quick guide
is [USING_SOX_DSD.md](USING_SOX_DSD.md).

## Verification

Build with Autotools and run `make check-dsd-cli`; the test suite creates
synthetic input independently of the SoX encoder and checks outputs at the
file/payload level. It covers every DSD rate, output clocks/bit depths,
profile aliases and pinned IDs, native DSF/DSDIFF repacking, DoP marker
chronology, report byte invariance on all major routes, rejected
combinations, and ordinary SoX PCM commands. The independent C gates
and original `make check` remain useful for lower-level regression checks.

Phase-gate runs write their receipts to `.dsd-check-results/P18/` (or the
selected `DSD_PHASE`) under the build directory by default. Set
`DSD_RESULTS=/path/to/results` to select an explicit destination. Previously
committed receipts under `tests/dsd/results/` remain frozen, so an ordinary
`make check-dsd` no longer rewrites historical evidence.

The included delivery validation report records exactly what ran and any
historical phase gates that remain incompatible with the new DSD-only
option spellings. Historical qualification receipts are not revised or
reinterpreted as new numerical qualification.

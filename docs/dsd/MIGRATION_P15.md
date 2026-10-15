# DSD CLI migration: P15 qualification build

This P15 continuation is **not** the full mastering release. It keeps the
established `legacy` default and production mastering encode activation off
pending independent release gates. The new explicit selection grammar is
available now, and a future *qualified* release can switch defaults only after
new certificate/benchmark receipts exist.

## Current behavior

- `sox_ng in.dsf out.dsf` keeps the existing native path. `--dsd-mode legacy`
  keeps the old graph routing for other operations; it does not undo file-format
  correctness repairs in earlier phases. Legacy mode can operate effects on
  unconverted DSD pulses, so it is not equivalent to a PCM-safe mastering
  conversion.
- `--dsd-mode auto` enables the source-aware planner explicitly. PCM effects
  operate after reconstruction. Native-only compatible repacking stays native.
- `--dsd-decode mastering|wideband|legacy` selects the reconstruction profile.
  The normal mastering profile is conservative about *source* bandwidth; a
  705.6-kHz PCM destination does not restore ultrasonic content removed by it.
  `--dsd-decode legacy` selects generic legacy reconstruction *within the new
  planner*, and does not mean `--dsd-mode legacy`.
- `--dsd-decode decode.mastering.v1.dsd64` (and `dsd128`, `dsd256`) selects a
  versioned profile tied to that exact native clock. `decode.wideband.v1.dsd*`
  likewise pins the wideband profile. A mismatched clock fails preflight
  when reconstruction actually selects the pinned profile; native-only repacks
  do not run a decoder.
- `--dsd-encode mastering|legacy|experimental` selects encoder intent;
  `--dsd-encode encode.mastering.v1.dsd64` (or `dsd128`/`dsd256`) pins the
  native clock when the composite encoder is actually selected. Native-only
  repacking does not run an encoder. This is **not** an authorization to emit mastering DSD while
  the profile's production-qualified flags are false. Explicit low-level
  `sdm` remains distinct from mastering.
- `--dsd-level preserve` keeps the native DSD reference at unity on
  reconstruction; `sacd` deliberately applies gain 2 (+6.0206 dB). Neither
  value silently normalizes or limits. PCM-origin mastering encodes at its
  documented 0.5 reference scale; native-DSD-origin remodulation retains its
  source reference according to the planner.
- `SOX_DSD_KERNEL_FIR` and `SOX_DSD_KERNEL_SDM` can still force available
  `scalar`, `sse2`, `avx1`, `avx2` and `avx512` tiers for qualification. The
  current automatic preference remains SSE2 FIR (scalar if unavailable) and
  scalar SDM. Unsupported/FMA-only names fail, not silently fall back.

## Reproducible commands

```sh
# New source-aware reconstruction, mastering bandwidth, unchanged level.
sox_ng --dsd-mode auto --dsd-decode decode.mastering.v1.dsd64 \
  input-dsd64.dsf -r 176400 -b 24 decoded.wav

# Explicit wider source bandwidth on a matching native rate.
sox_ng --dsd-mode auto --dsd-decode decode.wideband.v1.dsd256 \
  input-dsd256.dsf -r 705600 -b 24 wide.wav

# Old graph behavior for comparison, not an equivalent mastering result.
sox_ng --dsd-mode legacy input-dsd64.dsf -r 176400 legacy.wav rate -v

# Ask for the intended modulation route without writing an unqualified master.
sox_ng --dsd-plan --dsd-encode encode.mastering.v1.dsd128 \
  input-96k.wav -r 5644800 candidate.dsf
```

`--dsd-plan` returns intended identities/reference settings and an
`executable` field; a plan that says `executable: false` does not authorize
actual conversion. Output containers for DSD512/1024 remain unavailable.
Generic SoX PCM commands without DSD policy keep their existing semantics.

## P15-R3: additive decoder v2 candidate (2026-10-14)

Before the full P15 release gate closes, `--dsd-decode mastering` continues to
select the original `decode.mastering.v1.dsd64|128|256` bank.
`--dsd-decode conservative` explicitly selects those same original v1 banks;
`--dsd-decode wideband` selects the unchanged wideband v1 banks.
The exact versioned `decode.mastering.v2.dsd64`, `.dsd128` and `.dsd256` IDs
are *candidate-only* explicit selectors for verification, not a qualified
mastering default. `dsdpcm -p` accepts the same selectors. A pinned ID must
match the native input clock; v1 pins never resolve to v2.

Candidate-v2 DSD64/128/256 guaranteed passbands are 25/48/66 kHz, stopbands
40/60/80 kHz, implicit PCM clocks 88.2/176.4/176.4 kHz. DSD128 and DSD256
may explicitly render to lower supported rates with `--dsd-bandwidth adapt`
(reduced effective passband) or to higher supported rates without switching
banks. `--dsd-bandwidth strict` rejects requests that cannot retain the selected
passband. No high-rate output can recreate spectrum removed by its decoder
bank. Legacy remains the unrelated generic processing mode.

Existing encoder mastering v1 policies, coefficients, reporting identities and
soak evidence are unchanged. Do not infer an encoder-v2 policy. This work
**does not activate `auto` by default, qualify v2 or authorize P16**. See
`handoffs/P15_R3_RECONSTRUCTION_POLICY_HANDOFF.md` and `QUALIFICATION.md`.

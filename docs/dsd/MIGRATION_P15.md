# DSD CLI migration: P15 release (October 20, 2026)

**Release-current policy.** The October 20 activation made the mastering-v2
reconstruction banks the default for **unpinned reconstruction** and enabled
`encode.mastering.v1` for native DSD64, DSD128 and DSD256. The earlier release
gates' candidate-only/disabled-encoder language is historical, not shipping
policy. See [the operator's release decision](handoffs/P15_RELEASE_ACTIVATION_2026-10-20.md).

The CLI's unrelated `--dsd-mode` default is still **`legacy`**, not `auto`.
Opt in to the source-aware processing graph with `--dsd-mode auto`. A legacy
graph and a source-aware mastering graph are not interchangeable.

## Current behavior

- `sox in.dsf out.dsf` retains the existing native path. `--dsd-mode legacy`
  preserves old graph routing for other operations; it does not undo file-format
  repairs. Legacy routing can apply effects directly to DSD pulses, which is
  not equivalent to PCM-safe mastering processing.
- `--dsd-mode auto` enables source-aware planning. PCM effects run after DSD
  reconstruction, and compatible native-only repacks stay native.
- Without an explicit decoder selection, reconstruction in the source-aware
  graph now selects `decode.mastering.v2.dsd64`, `.dsd128`, or `.dsd256`
  according to the input native rate. An unpinned `dsdpcm` effect likewise
  defaults to mastering v2. Effective v2 passbands are 25, 48, and 66 kHz;
  corresponding default PCM clocks are 88.2, 176.4, and 176.4 kHz.
- **Explicit** `--dsd-decode mastering` or `conservative` still selects
  the original **v1** mastering banks. Explicit `wideband` selects the v1
  wideband banks; `legacy` selects generic legacy reconstruction *within*
  the source-aware planner (not `--dsd-mode legacy`). `dsdpcm -p mastering`
  likewise explicitly requests v1. These choices are not silently promoted
  to v2.
- Versioned selectors, e.g. `--dsd-decode decode.mastering.v1.dsd64`,
  `--dsd-decode decode.mastering.v2.dsd128`, and
  `--dsd-decode decode.wideband.v1.dsd256`, pin the bank and the native
  clock. A mismatched clock fails when that decoder is actually selected;
  native-only repacks never invoke the decoder. Higher PCM output rates
  cannot recover ultrasonic content already removed by a chosen bank.
- `--dsd-encode mastering` and matching
  `--dsd-encode encode.mastering.v1.dsd64|128|256` are **activated** for
  production native DSD64, DSD128 and DSD256 output. Versioned IDs pin the
  requested native clock; a wrong-clock selection is refused. Mastering v1
  modulator coefficients and guards were not changed by activation. Unsafe
  input, invalid layouts, and numerical overload still fail closed.
  Experimental and legacy encode selections and the low-level `sdm` effect
  retain their distinct semantics. No `encode.mastering.v2` is implied.
- `--dsd-level preserve` uses unity reference for reconstructed native DSD;
  `sacd` intentionally applies gain 2 (+6.0206 dB). Neither normalizes or
  limits. PCM-origin mastering encoding uses its documented 0.5 reference
  scale; native-DSD-origin remodulation retains its planner reference.
- `--dsd-bandwidth adapt` allows reduced effective bandwidth where necessary
  for lower supported PCM rates; `strict` rejects requests unable to retain
  the chosen profile's passband.
- `SOX_DSD_KERNEL_FIR` and `SOX_DSD_KERNEL_SDM` can force available
  `scalar`, `sse2`, `avx1`, `avx2` and `avx512` tiers for qualification.
  The current automatic preference is SSE2 FIR (scalar when unavailable)
  and scalar SDM. Unsupported or FMA-only names are rejected.

## Reproducible commands

```sh
# Unpinned source-aware DSD64 reconstruction: mastering v2, 25 kHz passband.
sox --dsd-mode auto input-dsd64.dsf -r 176400 -b 24 decoded-v2.wav

# Explicit older mastering v1, never silently promoted to v2.
sox --dsd-mode auto --dsd-decode decode.mastering.v1.dsd64 \
  input-dsd64.dsf -r 176400 -b 24 decoded-v1.wav

# Explicit wider source bandwidth for DSD256 (matching native clock).
sox --dsd-mode auto --dsd-decode decode.wideband.v1.dsd256 \
  input-dsd256.dsf -r 705600 -b 24 wide.wav

# Existing legacy graph for comparison, not the same mastering operation.
sox --dsd-mode legacy input-dsd64.dsf -r 176400 legacy.wav rate -v

# Activated mastering-v1 native DSD128 output: the planner checks clock,
# route and safety guards before writing a native DSD output.
sox --dsd-mode auto --dsd-encode encode.mastering.v1.dsd128 \
  input-pcm.wav -r 5644800 mastered-dsd128.dsf

# Side-effect-free preflight of that exact output route.
sox --dsd-mode auto --dsd-plan --dsd-encode encode.mastering.v1.dsd128 \
  input-pcm.wav -r 5644800 planned-dsd128.dsf
```

`--dsd-plan` reports the selected identities, references, and `executable`
state without opening an output. A false `executable` or a subsequent
numerical failure is not an authorization to produce audio. DSD512/1024
output containers are not released. Ordinary PCM commands without explicit
DSD policy keep their established semantics.

## Historical context: P15-R3 decoder candidate (October 14, 2026)

Before the October 20 operator release activation, the v2 DSD64/128/256
coefficient banks were **candidate-only** and required explicit pinned IDs.
At that point `mastering` and the implicit reconstruction default used v1,
and production mastering encode was disabled pending release. Those
historical qualifications were superseded on October 20; they are not
current operator instructions. See
[the P15-R3 handoff](handoffs/P15_R3_RECONSTRUCTION_POLICY_HANDOFF.md) and
[the October 20 activation](handoffs/P15_RELEASE_ACTIVATION_2026-10-20.md).
The v1 and v2 coefficients and their pinned identifiers remain unchanged.

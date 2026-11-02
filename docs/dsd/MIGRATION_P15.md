# SoX DSD CLI migration (November 2, 2026)

This is the current migration reference from the SoX DSD 1.0.4
DSD-specific command options to the simplified interface. Historic P15
qualification and release records under `docs/dsd/handoffs/` have been
retained as evidence, not current user instructions. For actual commands,
see [Using SoX DSD](USING_SOX_DSD.md) and `man sox`.

| SoX DSD 1.0.4 spelling or behavior | New interface | Meaning |
| --- | --- | --- |
| `--dsd-mode auto input.dsf output.wav` | `input.dsf output.wav` | Auto DSD reconstruction selected by input/output formats. |
| `--dsd-mode auto input.wav -r 5644800 output.dsf` | `input.wav -r dsd128 output.dsf` | Qualified encoding for DSD128. Numeric rates remain valid. |
| `--dsd-mode legacy input.wav output.dsf` | `input.wav output.dsf` | Both now use qualified modulation. The legacy flag cannot bypass the planned encoder. Use the explicit `sdm` effect for low-level testing. |
| `--dsd-mode native input.dsf output.dff` | `input.dsf output.dff` | Native bitstream repacking (advanced `--dsd-mode native` is still available). |
| `--dsd-decode mastering` (formerly v1) | `--decode conservative` | Preserve exact older mastering-v1 selection. |
| Unpinned decoding (formerly mastering v2) | Default, or `--decode mastering` | Both use qualified mastering-v2. |
| `--dsd-decode decode.mastering.v1.dsd64` | `--decode decode.mastering.v1.dsd64` | Explicit immutable decoder bank and input clock. |
| `--dsd-encode encode.mastering.v1.dsd128` | `--encode encode.mastering.v1.dsd128` | Explicit qualified encoder identity and output clock. |
| `--dsd-plan input.dsf output.wav` | `--plan input.dsf output.wav` | Non-executing JSON plan. |
| `--dsd-report result.json input.dsf output.wav` | `--report result.json input.dsf output.wav` | Runtime report without changing route/audio. |
| `input.dsf -r 176400 -b 24 out.wav dop` | `--dop input.dsf out.wav` | Native DSD packaging in signed 24-bit PCM carrier at input/16. |

Conventional SoX options (`-r`, `-b`, `-c`, `-t`, `-e`, global `-D`,
`--combine`, the familiar effects grammar, and PCM-only behavior) are not
renamed. Advanced `--dsd-level`, `--dsd-clip`, `--dsd-bandwidth`,
`--dsd-layout`, `--dsd-layout-loss`, and `--sdm-guard` remain available.
The old DSD-specific spellings in the first column are for migrating
scripts; they are not supported compatibility aliases.

The new default refuses to treat DSD pulse samples as PCM when a PCM
output or PCM effect is requested. No DSP coefficients, modulation
filters, qualification records, or native format handlers are altered.

# SoX DSD 1.1.1: release candidate notes

The source version remains **1.1.0** until release. These notes describe
changes to the unpushed 1.1.1 branch and its independent review corrections.

## Changed defaults

- **PCM to DSD:** the eighth-order `encode.mastering.v1` modulator is the
  automatic encoder at DSD512 and DSD1024 (as it already was at DSD64/128/256).
  The seventh-order `encode.mastering.v2` remains qualified for those high
  rates but is accessible only through the private test interface.
- **DSD to PCM:** `decode.mastering.v1` is the automatic decoder at all five
  clocks. Explicit `--decode mastering` still selects the wider v2, while
  `--decode conservative` and the exact v1 IDs select v1.
- **Default PCM-to-DSD level:** normal warning mode applies a fixed 0.9 gain
  (-0.91515 dB) and clips residual interpolated values above 0.45 modulator
  units, with a warning, at all five rates. This is unchanged from 1.1.0.
- **Strict clipping:** `--dsd-clip error` never clips. Without an explicit
  headroom selection it uses gain 1 at DSD64/128/256, but retains 0.9 at
  DSD512/1024 so the high-rate v1 modulator stays at its tested input level.
  A pre-gain interpolated peak up to roughly 1.111 times PCM full scale can
  therefore be accepted by high-rate strict mode (0.5 modulator ceiling),
  whereas a comparable peak is rejected at lower rates. This is not a
  guarantee against separate modulator-state guard failures.
- **Explicit level:** `--headroom DB` replaces any implicit gain, rather
  than adding to it. `--auto-headroom` measures the complete interpolated
  peak and applies no amplification, cutting all channels to at most 0.45
  in a second pass. Both are compatible with strict clipping; the guard
  remains fail-closed. The strict overload diagnostic now gives a *total*
  `--headroom` lower bound inferred from the first failure, not a guaranteed
  cure for later overloads or state-guard failures.

## Incompatible command-line change

In 1.1.0, both `--encode encode.mastering.v2.dsd512` and
`--encode encode.mastering.v2.dsd1024` were accepted. **They now fail**, even
though the v2 profiles remain qualified internally: those exact IDs are no
longer bound for CLI selection. An existing invocation pinned to either
profile must be reviewed and adjusted. There is **no equivalent CLI pin**
for the former high-rate v2 bitstream in this candidate. Do not assume the
new v1 default produces the same bitstream or the same ultrasonic spectrum.

## Qualification limits

The supplied evidence includes 60-second DC checks at both high clocks,
3,600-second nominal soaks and 800 real-track encode-completion runs. These
show bounded behavior under the tested conditions, not mathematical proof of
arbitrary-duration or arbitrary-signal v1 stability. The real-track peak0
runs also include **194/400 input-stage clipping warnings** (up to 3,936
samples per run), independent of the 0.45 modulator clipping. The original
soak's `launcher.log` is empty; individual execution, stdout, stderr and
assessor receipts are available. The reported `/dev/null` tests do not
prove that no output bytes were emitted before a failure.

See [Using SoX DSD](USING_SOX_DSD.md) and
[high-rate v1 evidence](V1_HIGH_RATE_ENCODE_2026-11-07.md).

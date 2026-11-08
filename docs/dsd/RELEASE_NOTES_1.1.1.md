# SoX DSD 1.1.1: release notes

These notes describe the 1.1.1 behavior. The source version bump is performed
at release time, separately from the review changes.

## Defaults and compatible high-rate v2 pins

- **PCM to DSD:** the eighth-order `encode.mastering.v1` modulator is the
  default at all five DSD clocks, including DSD512 and DSD1024. Its high-rate
  qualification evidence used the implicit 0.9 gain and 0.45 clipping ceiling.
- **Optional high-rate v2:** the seventh-order `encode.mastering.v2.dsd512`
  and `encode.mastering.v2.dsd1024` are still qualified and selectable with
  `--encode` or explicit `pcmdsd -p`. These are the same exact IDs accepted in
  1.1.0 and retain the 1.1.0 CLANS-7 algorithm, guards, and bits for the same
  input/settings. `--encode mastering` selects **v1**, not v2.
- **DSD to PCM:** `decode.mastering.v1` is the automatic decoder at all five
  clocks. Explicit `--decode mastering` selects the wider v2, while
  `--decode conservative` and exact v1 IDs select v1. Decoder and encoder
  version numbers are independent.
- **Default PCM-to-DSD level:** warn-and-clip mode applies a fixed 0.9 gain
  (-0.91515 dB) before clipping residual interpolated peaks above 0.45
  modulator units. This is unchanged from 1.1.0, including for v2.
- **Strict encoding:** `--dsd-clip error` never clips. With no explicit
  headroom, it uses unity gain for DSD64/128/256 and for exact high-rate v2;
  the default high-rate v1 retains gain 0.9. For PCM-origin input only,
  high-rate v1 can therefore admit a pre-gain interpolated peak up to about
  1.111 times PCM full scale before the 0.5 modulator envelope is exceeded.
  This is not permission for out-of-range PCM input samples, and it is not
  applicable to DSD-origin re-encoding, which has a different reference scale.
- **Strict decoding:** `--dsd-clip error` also refuses reconstructed PCM
  reaching +1.0 or falling below -1.0 at the PCM graph boundary rather than
  clipping; the negative endpoint -1.0 itself is representable.
- **Explicit headroom:** `--headroom DB` replaces any implicit gain, not the
  numeric overload or state guards. `--auto-headroom` measures the complete
  interpolated signal and applies a non-amplifying, shared multichannel cut to
  at most 0.45 before the modulator. A strict overload diagnostic suggests a
  total replacement `--headroom` lower bound inferred from the first failed
  sample, not a successful-retry guarantee.

## Qualification and evidence limits

The high-rate v1 evidence includes 60-second DC checks at both clocks,
3,600-second nominal soaks and 800 real-track encode-completion runs. These
show bounded behavior under tested conditions, not mathematical proof of
arbitrary-duration or arbitrary-signal stability. Full-scale DC with
`--headroom 0 --dsd-clip error` reproduces v1 state-guard failure at both
high rates. Other cuts below the implicit 0.91515 dB were not systematically
tested and cannot be claimed to fail. The real-track peak0 runs include
**194/400 input-stage clipping warnings** (up to 3,936 samples per run),
independent of modulator clipping. The historical soak's `launcher.log` is
empty; its individual execution and assessor receipts are available. Tests
targeting `/dev/null` do not prove that output was never emitted before a
failure. The documented historical `cli-paths/release-1.1.1.jsonl` records
predate the later headroom-hint correction and are not output from this final
review branch.

See [Using SoX DSD](USING_SOX_DSD.md) and the
[high-rate v1 evidence](V1_HIGH_RATE_ENCODE_2026-11-07.md).

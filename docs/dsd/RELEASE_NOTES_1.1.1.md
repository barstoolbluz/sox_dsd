# SoX DSD 1.1.1: release notes

The DSD decoder has one standard mastering profile at all five native clocks.
The optional high-rate mastering v2 **encoder** remains available by exact ID.

## Defaults and compatible high-rate v2 pins

- **PCM to DSD:** the eighth-order `encode.mastering.v1` modulator is the
  default at all five DSD clocks, including DSD512 and DSD1024. Its high-rate
  qualification evidence used the implicit 0.9 gain and 0.45 clipping ceiling.
- **Optional high-rate v2:** the seventh-order `encode.mastering.v2.dsd512`
  and `encode.mastering.v2.dsd1024` are still qualified and selectable with
  `--encode` or explicit `pcmdsd -p`. These are the same exact IDs accepted in
  1.1.0 and retain the 1.1.0 CLANS-7 algorithm, guards, and bits for the same
  input/settings. `--encode mastering` selects **v1**, not v2.
- **DSD to PCM:** `decode.mastering.v1.dsdNNN` is the standard decoder at all
  five clocks. Explicit `--decode mastering` matches the default and the
  corresponding exact v1 ID. `--decode wideband` selects the only qualified
  alternative. Decoder v2 and the retired `conservative`/`legacy` decoder
  spellings are no longer accepted. Encoder v2 is a separate component.
- **Changed from 1.1.0:** 1.1.0 decoded with mastering v2 by default and for
  `--decode mastering`, so default DSD-to-PCM output differs in 1.1.1. The
  v2 bank extended the passband into the ultrasonic range; v1's rated
  passband is 20 kHz at DSD64, 30 kHz at DSD128 and 40 kHz above.
- **C API:** `sox_dsd_decode_options_init` now selects mastering v1, so
  callers that keep its default get v1 output. `SOX_DSD_DECODE_MASTERING_V2`
  is removed from `sox_dsd.h`: code that names it no longer compiles, and
  `sox_dsd_decoder_create` rejects the value 3 with `SOX_DSD_BAD_ARGUMENT`.
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
predate the later headroom-hint correction and should not be read as
measurements of the present source tree.

See [Using SoX DSD](USING_SOX_DSD.md) and the
[high-rate v1 evidence](V1_HIGH_RATE_ENCODE_2026-11-07.md).

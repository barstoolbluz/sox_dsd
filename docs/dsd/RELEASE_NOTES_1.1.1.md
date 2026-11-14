# SoX DSD 1.1.1: release notes

SoX DSD 1.1.1 has one standard DSD decoder and one PCM-to-DSD encoder, both
called `mastering`, at all five native clocks. Profile IDs carry no version
labels.

**Revised 2026-11-13.** The release first published on 2026-11-09 ran the
eighth-order encoder at DSD512 and DSD1024 with the DSD256 coefficients. At
DSD512 that table later failed a one-hour soak of DC at the level full-scale
PCM reaches in the default warn mode, after 19.4 minutes. The revision gives
both rates their own tables. It also removes the optional seventh-order
CLANS-7 encoder at those rates, keeps the 0.9 gain in strict mode at DSD64 to
DSD256, where the first release used unity gain, and drops the `v1` and `v2`
profile labels. The version number stays 1.1.1.

## Defaults

- **PCM to DSD:** the eighth-order SDM-8 `mastering` encoder is the default at
  all five DSD clocks. DSD512 and DSD1024 use their own coefficient tables,
  which place the noise-shaping zeros for each rate (see the [noise-shaper
  report](NOISE_SHAPER_BENCH_2026-11-07.md), §5). Exact IDs
  `encode.mastering.dsd64` to `encode.mastering.dsd1024` pin it to a clock,
  with `--encode` or `pcmdsd -p`.
- **Legacy encoding:** the original SoX `sdm` effect and its noise shapers
  remain available as `rate -v RATE sdm -f NAME`. `--encode legacy` names that
  route but does not build it; with an explicit `rate … sdm` chain it is
  accepted, where the first release refused the combination. The route gets
  neither the mastering gain nor its guards.
- **DSD to PCM:** `--decode mastering` is the default at all five clocks, and
  `--decode wideband` selects the only alternative. Exact IDs are
  `decode.mastering.dsdNNN` and `decode.wideband.dsdNNN`.
- **Retired:** the CLANS-7 encoder, the `experimental` encoder selection,
  `pcmdsd -p legacy` and `-p experimental`, the `conservative` and `legacy`
  decoder spellings, and every versioned ID (`encode.mastering.v2.dsd512`,
  `decode.mastering.v1.dsd64` and so on) are rejected.
- **Changed from 1.1.0:** 1.1.0 decoded with a different mastering bank by
  default and for `--decode mastering`, so default DSD-to-PCM output differs
  in 1.1.1. That bank extended the passband into the ultrasonic range; the
  current one's rated passband is 20 kHz at DSD64, 30 kHz at DSD128 and 40 kHz
  above. 1.1.0 also encoded DSD512 and DSD1024 with CLANS-7, and its strict
  mode used unity gain at every rate.
- **C API:** `sox_dsd_decode_options_init` selects the mastering decoder, so
  callers that keep its default get different output than with 1.1.0.
  `SOX_DSD_DECODE_MASTERING_V2` is removed from `sox_dsd.h`: code that names
  it no longer compiles, and `sox_dsd_decoder_create` rejects the value 3 with
  `SOX_DSD_BAD_ARGUMENT`.
- **Default PCM-to-DSD level:** the mastering encoder applies a fixed 0.9 gain
  (-0.91515 dB) at every rate, in both `--dsd-clip warn` and `--dsd-clip
  error`. Warn mode then clips residual interpolated peaks above 0.45
  modulator units.
- **Strict encoding:** `--dsd-clip error` never clips; it refuses interpolated
  values above 0.5 modulator units. Because the 0.9 gain stays, PCM-origin
  input can reach a pre-gain interpolated peak of about 1.111 times PCM full
  scale before that limit. This is not permission for out-of-range PCM input
  samples, and it does not apply to DSD-origin re-encoding, which has a
  different reference scale.
- **Strict decoding:** `--dsd-clip error` also refuses reconstructed PCM
  reaching +1.0 or falling below -1.0 at the PCM graph boundary rather than
  clipping; the negative endpoint -1.0 itself is representable.
- **Explicit headroom:** `--headroom DB` and `--auto-headroom` replace the 0.9
  gain, not the numeric overload or state guards. `--auto-headroom` measures
  the complete interpolated signal and applies a non-amplifying, shared
  multichannel cut to at most 0.45 before the modulator, so quiet material
  comes out up to 0.915 dB louder than with the default gain. A strict
  overload diagnostic suggests retrying with `--auto-headroom`. It also gives
  a total replacement `--headroom` lower bound inferred from the first failed
  sample, not a successful-retry guarantee.

## Qualification and evidence limits

The DSD512 and DSD1024 tables passed one-hour soaks of DC at 0.45 modulator
units, where full-scale PCM lands after the 0.9 gain, in both polarities. With
the same 200 tracks encoded at each rate, once as decoded and once raised to a
0 dBFS sample peak (`peak0`), all 800 encodes completed in warn mode; the
modulator ceiling clipped in 248 of the 400 runs at each rate. These show
bounded behavior under tested conditions, not proof of stability for any
duration or signal. In warn mode the 0.45 ceiling holds even with `--headroom
0`. With `--dsd-clip error` and a cut smaller than 0.91515 dB, including
`--headroom 0`, the modulator can see more than 0.45; near-full-scale DC at
that level drove both the new tables and the first release's unstable within
seconds. Other cuts smaller than 0.91515 dB were not systematically tested and
cannot be claimed to fail. No coefficient certificate covers the new tables,
so `--plan` and `--report` give `null` for it at DSD512 and DSD1024.

The `peak0` runs include **194/400 input-stage clipping warnings** (up to
3,936 samples per run), independent of modulator clipping.

See [Using SoX DSD](USING_SOX_DSD.md), the [noise-shaper
report](NOISE_SHAPER_BENCH_2026-11-07.md) and the [first release's high-rate
qualification](V1_HIGH_RATE_ENCODE_2026-11-07.md), which the revised tables
supersede.

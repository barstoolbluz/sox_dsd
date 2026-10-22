# DSD512 v2 operator qualification, 2026-10-22

Prepared host, Threadripper 7970X, dedicated cores. Run overnight against
the P20 candidate delivered the same day.

## The defect is closed

`encode.mastering.v2.dsd512` passes the sustained nominal gate that
`encode.mastering.v1.dsd512` failed.

| | min ones28 | max | longest run | verdict |
|---|---|---|---|---|
| v1, 2026-10-22 | **6** | 22 | 10 | FAIL |
| **v2 nominal** | **7** | 21 | **5** | **PASS_SOAK_INPUT_GATE** |
| v2 stress | 7 | 21 | 5 | UNVERIFIED_EXECUTION, envelope gate |

3,600 seconds uninterrupted, 81,285,120,000 native frames, zero nonfinite
states, zero monitor overloads, all 61 segment snapshots present and
digest-matched, peak guard utilisation 6.0% of the frozen P20 ceilings.

The stress run reached the same population figures before stopping at the
interpolation-envelope gate on the deliberate overload, exactly as the v1
stress run did. That is the gate working.

Every `.state` snapshot is included this time. The P20 handoff noted that
our previous evidence omitted the intermediate snapshots, so their digests
could not be recomputed independently; all 66 are here.

## Supporting evidence, all reproduced locally

- Training 17/17, `VERIFY PASS 17`, holdout **36/36 with zero failures**
- Certificate `P20 PASS_CHECK: experimental only, writer disabled`
- Bitstream oracle PASS: nominal program min28 8, longest run 5
- Cross-ISA PASS, 25 cases over scalar, SSE2, AVX1, AVX2, AVX-512
- `check-dsd DSD_PHASE=P18` 231 PASS 0 FAIL; `make check` and
  `check-rename` pass
- `dsd_test_p10 --unit` 105,489 assertions, 0 failures

The CLI still refuses `encode.mastering.v1.dsd512`,
`encode.mastering.v2.dsd512` and `encode.mastering.v2.dsd1024`. The
candidate is reachable only through the private constructor, and all twelve
P18 high-rate rows remain disabled.

## One result that needed a decision, now answered and corrected

**Our 37.1 dB figure was floor-limited and should not be cited.** The
stimulus here was quantized to signed 32-bit PCM before encoding, which puts
a residual measurement floor near -200.43 dBFS. The v1 number we recorded,
-200.14 dBFS, was therefore measuring that floor rather than the modulator.

Repeated by the design authority with binary64 input, preserving the same
encoder implementations and reconstruction coefficients:

| rate | 8th order | 7th order | penalty |
|---|---|---|---|
| DSD512 | -204.04 dBFS | -163.06 dBFS | 40.99 dB |
| DSD1024 | -238.75 dBFS | -201.26 dBFS | 37.47 dB |

The penalties are comparable once the source-quantization floor is removed,
so the asymmetry we reported does not exist and no defect requires
correction.

Two things from that ruling are worth keeping in view.

-163 dBFS was **not a chosen fidelity target**. The seventh-order candidate
reused historical DSD256 CLANS-7 coefficients and was selected because it
passed the sustained population and stability requirements that the
eighth-order candidates failed. The residual is an observed property, not an
objective.

**99.9686% of that residual power lies between 40 and 88.2 kHz.** Below 40
kHz it is approximately -198 dBFS. So against the mastering profile's 40 kHz
passband the order reduction costs almost nothing; the penalty only matters
if the extended band is actually used.

The original figures below are left unchanged as the record of what we
measured. They are superseded, not deleted.

## Status

This closes the sustained-soak obligation for DSD512 encoding. It does not
qualify the profile: `qualified=0` and `certificate_sha256=NULL` stand, and
independent audio-quality assessment on real programs remains uncollected.
Nothing is enabled.

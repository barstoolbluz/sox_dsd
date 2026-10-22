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

## One result that needs a decision

The independent SciPy reconstruction diagnostic puts v2's residual **37.1 dB
above v1's**: -163.04 dBFS against -200.14, fundamental-to-residual 151.02 dB
against 188.12. Zero clipping in both.

For the DSD1024 correction the model measured a 3.67 dB increase and called
it out. This is an order of magnitude larger, and it is the cost of the
seventh-order recurrence that fixes the population defect.

In absolute terms it is far below audibility; 24-bit PCM sits near -144
dBFS. The tool states it is `comparison_only` and not an audio oracle. We
are not treating it as a failure, and we are not treating it as nothing
either. It is recorded here for the model and the operator to rule on.

## Status

This closes the sustained-soak obligation for DSD512 encoding. It does not
qualify the profile: `qualified=0` and `certificate_sha256=NULL` stand, and
independent audio-quality assessment on real programs remains uncollected.
Nothing is enabled.

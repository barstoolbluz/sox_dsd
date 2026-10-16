# P15 SRC sampled spectral holdouts — 2026-10-16

Local execution of `tests/dsd/test_p15_r3_src_spot.py` against the production
private SRC, probed through the test-only P07 binary64 exporter.

    cd tests/dsd && PYTHONPATH=. python3 test_p15_r3_src_spot.py \
      --probe <build>/test/dsd_test_p07_reference --results <out>

Build: `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'`,
this host (AMD, Linux 6.12.85), /usr/bin/python3. 32768 input frames per tone.

## Result

`SAMPLED_PASS`, exit 0. Four real rate ratios, 38 checks, no failures.

| case | tones | worst passband ripple | images | worst alias |
|---|---|---|---|---|
| 88200 -> 48000, pass 22800 Hz | 7 | 4.686e-09 dB | 2 | -234.0 dB |
| 176400 -> 96000, pass 45600 Hz | 7 | 4.686e-09 dB | 2 | -234.0 dB |
| 176400 -> 88200, pass 41895 Hz | 7 | 3.168e-09 dB | 3 | -237.4 dB |
| 176400 -> 352800, pass 66000 Hz | 7 | 9.330e-10 dB | 3 | -202.2 dB |

Against the section 8.6.1 limits of 0.0001 dB passband and -160 dB alias:
worst ripple clears by 21339x, worst image by 42.2 dB. The 66 kHz case is the
v2 DSD256 passband.

## Scope, and what this does not close

These are finite sampled tones at fixed frequencies. The instrument says so
itself: "not a proof of all extrema/images or of the full native FIR", and the
driver reports `release_status: BLOCKED`.

The open gate is `P15-v1-and-v2-composite-SRC-acceptance`, whose spectral half
is the continuous-frequency extrema and coherent-alias certificate. That is a
separate assignment and is NOT closed by this run. These measurements are
corroborating evidence: at every frequency actually tested, the production SRC
sits four to five orders of magnitude inside the normative limits.

The arithmetic half of that same gate was reported PASS by the R5 adjudication
(`PASS_ALL_72_ARITHMETIC`, 3,808,676 comparisons), proven on the author's pinned
host. It is not reproduced here — see the integration note in the commit
message; the R5 source patch does not apply to this tree.

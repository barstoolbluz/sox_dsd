# P15 matrix metrology R2, and the DSD256 2x target, with verifiable receipts

This round closes the two evidence gaps the closeout adjudication attributed to
us. Both were packaging failures on our side, not measurement failures, and one
carried a methodological error we accept.

**No gate is closed by this directory.** Every cell still reports
`qualified: false` and `release_gate_closed: false`, and the receipt reviewer
returns `OBSERVATION_COVERAGE_COMPLETE_NOT_RELEASE_CERTIFICATE`. Coverage and
integrity are complete; acceptance is not ours to declare.

## Gap 1: the matrix was not independently verifiable

The R1 commit excluded `arrays/*.npz`, so the adjudication's reviewer exited at
the first cell on a missing raw digest. We reproduced that exactly:

```
arrays absent  -> P15 receipt review ERROR: raw evidence digest mismatch: dsd64.mastering.pcm44100
arrays present -> status OBSERVATION_COVERAGE_COMPLETE_NOT_RELEASE_CERTIFICATE
```

Re-run with arrays retained across all five tiers. Verified against the copies
committed here, not merely against the originals:

| observation | count |
|---|---|
| scalar full-duration cells | 54 |
| forced-ISA full-duration jobs | 216 |
| selected detailed ISA jobs | 96 |
| graph full-duration cells | 54 |
| sampled SRC full-duration cells | 54 |
| sessions | 5 |

`p15_matrix_receipt_review.py --require-coverage` exits 0 on this directory.

`src-raw` is excluded and is not needed: the reviewer verifies whatever raw
stream a session *claims*, so the scalar session captures graph raw but not SRC
raw, and coverage still completes. That removed 825 MB. What remains is 349 MB,
which is the cost of a gate that can actually be checked.

## Gap 2: the DSD256 control was not bandwidth-matched

The adjudication's criticism was correct. Our earlier control ran `rate -v`
then `sinc -20000`, and post-filtering cannot undo aliasing produced during the
earlier decimation, so it was not the staged bandwidth-matched legacy control
section 10.7 requires.

Our first replacement was also wrong, and worth recording: we wrote
`-r 88200 ... rate -v sinc -20000 rate -v 352800`, where `-r` fixes the output
rate so the trailing `rate` never applied. The file came out at 88200 while our
bandwidth check assumed 352800, which made a reassuring "0.0000% above 20 kHz"
an artifact of measuring at the wrong rate.

The construction used here sets the output rate once and stages inside the
effect chain: `-r <out> ... rate -v 88200 sinc -20000 rate -v`. Verified by
measurement rather than asserted, at the correct rate:

| arm | energy above 20 kHz | total energy | RMS |
|---|---|---|---|
| legacy direct | 0.0034% | 2.917e+07 | 0.07071 |
| legacy staged matched | 0.0000% | 2.917e+07 | 0.07071 |
| decoder | 0.0000% | 2.917e+07 | 0.07071 |

Identical total energy and RMS, so the control differs from the direct path in
bandwidth alone and not in level.

### Result

| output | vs legacy direct | vs staged bandwidth-matched |
|---|---|---|
| 352800 Hz | 3.76x [3.76, 3.76] | 3.80x [3.78, 3.80] |
| 176400 Hz | 3.87x [3.87, 3.89] | 3.92x [3.92, 3.92] |

All four clear the 2.00x target at the confidence-interval lower bound. The
matched control costs about 1% more than the direct path, which is the point
section 10.7 asks about: the speedup is not explained by a narrower bandwidth.

`dsd256-2x.json` carries every one of the 15 repetitions per arm, the exact
argv, host CPU/microcode/governor/boost/affinity, fixture and executable
SHA-256 bindings, per-arm clock samples, and the bootstrap method, iteration
count and seed, so the intervals are recomputable from the saved samples
without rerunning anything.

## Still not ours

The SRC acceptance envelope does not exist, and the instrument's authors
declined to let section 8.6's FIR roundoff limit serve as one. Until a
predeclared, independently justified envelope exists we do not think the matrix
gate can be adjudicated either way, and we are not proposing one. Full spectral
extrema and coherent-alias certification, and independent review, likewise
remain outside what we can supply.

Figures are from one host and are not a property of the code alone.

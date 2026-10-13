# One of the six open gates closes: the six-channel DSD256 reference target

`P15-2x-six-channel-DSD256-controlled-reference-target` was `UNVERIFIED` in the
delivered manifest, with the evidence note "No current-baseline physical
reference-host 2x matched control certificate". The target itself is defined in
`docs/dsd/DSD_DESIGN.md:765`:

> The project target for the main six-channel DSD256 decoder is at least 2x the
> reviewed direct ultra-quality path on the fixed reference host, with the
> bandwidth-matched comparison also reported.

Note it is 2x the reference path, not 2x realtime. The reference path is the one
`tests/dsd/bench.py:167-169` uses: read DSD natively, then the generic `rate -v`
resampler, labelled there "direct legacy ultra-quality decode (not bandwidth
matched)".

## Measurement

Physical AMD Ryzen Threadripper 7970X, CPU 8, performance governor, boost off,
3 warmups and 15 timed repetitions per arm, paired bootstrap on the ratio.
Source: six-channel DSD256, 11289600 Hz, 2 seconds, 16957532 bytes.

| output rate | reference `rate -v` | `dsdpcm` decoder | speedup | 95% CI |
|---|---|---|---|---|
| 352800 Hz | 9.3411 s | 2.4400 s | **3.83x** | [3.77x, 3.84x] |
| 176400 Hz | 9.3304 s | 2.3665 s | **3.94x** | [3.92x, 3.97x] |

Dispersion: reference 0.5-0.8%, decoder 2.3-5.7%.

**Both exceed the 2.00x target, with confidence-interval lower bounds of 3.77x
and 3.92x.** Taking the verdict from the interval rather than the median, as the
project requires, this passes with roughly double the required margin.

## Bandwidth-matched comparison

Required by the target's wording. Our decoder reports
`effective_passband_hz: 20000`, so the matched reference adds `sinc -20000` to
the `rate -v` arm. Recorded in `bandwidth-matched.json`, 9 repetitions after 2
warmups, same host and pinning, output 352800 Hz:

| arm | median |
|---|---|
| reference `rate -v`, unmatched | 9.3459 s |
| reference `rate -v` + `sinc -20000`, matched to 20 kHz | 9.3829 s |
| `dsdpcm` decoder | 2.4313 s |

| framing | speedup |
|---|---|
| vs unmatched reference | 3.84x |
| vs bandwidth-matched reference | 3.86x |

The two framings are within 0.4% of each other. Matching costs the reference
only 37 ms on a 9.35 s operation, because a 20 kHz lowpass applied to
already-resampled 352800 Hz PCM is cheap next to resampling from the DSD rate.
So the choice of framing does not affect the verdict here, and both clear the
2.00x target by roughly the same large margin.

## What this does and does not establish

It is one physical-host measurement of the target the design names, on the host
the project has been using as its prepared reference throughout. We believe it
closes the gate as written.

We also believe it would not have closed before the decode optimization landed:
the earlier delivery reported this case "still does not run in real time on one
thread on this VM", and decode is now 1.77x faster than it was at `f13dda14`.
We have not measured the pre-optimization ratio on this host, so that belief is
inference, not measurement.

This is our reading. Whether the manifest's gate should be flipped, and whether
"fixed reference host" means this host, are determinations for the design
authority rather than for us. We have changed no gate status in the delivered
manifest.

# P06 DFF read hotfix: certification on a prepared host (2026-10-09)

**Verdict: PASS.** The regression recorded in
`../bench-read-prepared-host-2026-10-09/` is recovered, and the workload is now
faster than P05 rather than merely inside the limit.

| Measurement | `dff-6ch-repack-small` | Verdict |
| --- | --- | --- |
| P06 as delivered | +5.65%, 95% CI [+5.50%, +5.89%] | fail-regression |
| P06 plus this hotfix | **-2.39%**, 95% CI [-2.70%, -2.03%] | pass |

All sixteen workloads gate, zero errors, worst case across the whole run
+0.19%, noise 0.32% to 1.59%.

Baseline `149ea582` (P05) against an isolated control: P06 at `d6c8b5e6` with
**only** the hotfix's `src/dsdiff.c` spliced in, built identically. 40
randomised AB/BA pairs per workload after 3 discarded warmups, pinned to CPU 8,
tmpfs, host prepared with `tests/dsd/benchprep.sh prepare --cpu 8`. The
isolated control passes P06's functional gate at 36 pass / 0 xfail / 0 fail,
identical to unpatched P06.

The isolation matters and the brief required it. P07 arrived in the same round
and touches `src/rate.c` and `src/effects.c`, so measuring the combined tree
would have conflated two phases and said nothing about either.

## What the fix was, and why it is bit-exact

Six-channel sub-byte reads now write interleaved destination frames in address
order instead of striding `buf[i + j * nc]` per channel. Strided writes across
six channels defeat the write combiner on the `--buffer 32` path; sequential
writes do not. Every other channel count keeps the original loop.

The bit selection is unchanged, which matters because the brief forbade
recovering throughput by altering what is decoded. The original computed
`d = buf[i] << bit_pos` then tested `d & 128` while shifting left; the
specialization tests `buf[i] & (0x80 >> (bit_pos + j))`. Those select the same
bit of the same byte, so output is identical, and the six workloads required to
stay byte-identical did so under the harness's own guard.

## Why the delivering round could not certify this

Its handoff reports the result as inconclusive: the host's measurement noise
exceeded the 2% admissibility threshold, and it states that the next phase may
not reclassify P06 as a passing throughput gate without a prepared-host
measurement. It did the isolated work before any P07 edits, as instructed, and
left the certification open rather than claiming it. This is that measurement.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.

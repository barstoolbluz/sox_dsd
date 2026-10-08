# P01 DFF throughput, rerun on a prepared host (2026-10-08)

P01 reported this gate inconclusive because run-to-run spread was 12-20% on an
unprepared host, against the design's 2% noise precondition. This is the same
comparison rerun after `tests/dsd/benchprep.sh prepare`, which fixed the
governor and energy preference to performance, disabled boost, and offlined the
bench core's SMT sibling. The bench core then held a flat 3969 MHz under load.

Both arms were built from this repository with identical flags and differ only
in `src/dsdiff.c`: baseline `f636d65a` (P00a, pre-repair) against candidate
`99bc3366` (P01). Output bytes were verified correct in every run.

| Channels | short runs | long runs | noise (long) |
| --- | --- | --- | --- |
| 1 | +0.17% faster | +0.07% | 0.61% |
| 2 | +0.31% | +0.90% | 0.31% |
| 6 | +3.32% | **+4.42%** | 0.54% |

`short-runs/` used 50331648 frames, giving 0.20-0.59 s per run.
`long-runs/` used 503316480 frames, giving 1.96-11.37 s per run, which is the
5-10 s range `tests/dsd/BENCHMARKING.md` recommends.

## Verdict

**Pass, with a recorded cost.** Measurement noise was 0.31-0.61%, well under
the 2% precondition, so the comparison is admissible. The worst case, six
channels, regresses 4.42% with a paired bootstrap 95% interval of
[+4.01%, +4.82%]. That is inside the design's 5% limit but not comfortably:
the interval's upper bound sits 0.18 points below the gate.

The cost is real, not noise - at six channels the interval excludes zero by
roughly eight times the measurement spread - and it scales with channel count:
nothing at one channel, 0.9% at two, 4.4% at six. It also grew with run length
at six channels, 3.32% short against 4.42% long, so it is a per-sample cost in
the write path rather than per-file overhead amortised over a short run.

## What the cause is not

`dff_write_bits`, the bit-packing inner loop, is byte-identical between the two
arms, so the regression is not in the packing arithmetic. The hot-path changes
are an overflow check and the `data_size` increment moving into
`dff_write_buf`, plus a reordering in `dff_write` that calls the buffer write
before advancing the pointer and length. Per cluster that added work is
constant, so it should amortise *better* at six channels, not worse, which the
measurement contradicts. The cause is therefore unattributed; settling it needs
profiling, not reading. Recorded here so a later phase can pick it up rather
than rediscover it.

Do not treat these figures as a property of the code alone. They are one
prepared workstation, an AMD Ryzen Threadripper 7970X.

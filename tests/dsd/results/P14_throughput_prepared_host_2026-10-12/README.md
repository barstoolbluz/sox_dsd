# P14 read/repack throughput gate, prepared host (2026-10-12)

**Verdict: PASS.** All 16 workloads gate with 0 errors against the 5% limit.
Worst regression `dsf-6ch-null-small` at +1.30% [+1.14%, +1.64%]; the backlog
canary `dff-6ch-repack-small` measures -0.03% [-0.32%, +0.16%] at 0.53% noise.
Worst noise across the matrix 1.43%, inside the 2% admissibility limit.

Baseline is `d940cc93` against the P14 corrective tree, both built from their own
sources with `-O2 -g`, 40 randomised AB/BA pairs after 3 warmups, pinned to
CPU 8, working directory `/dev/shm`.

## Disclosure: the host was not idle

A `cargo`/`rustc` build belonging to another workload ran on other cores during
part of this measurement. Worst-case noise is correspondingly higher than the
P13 run's 0.76%, at 1.43%. Every workload still measures inside the 2% noise
limit, so the results are admissible under `tests/dsd/BENCHMARKING.md`, and the
verdict is taken from the intervals rather than the medians. A re-run on a
genuinely idle host would be stronger evidence and we did not obtain one.

## The canary is clean; three other workloads moved

`dff-6ch-repack-small` is flat at -0.03%. That is the first phase since P12
where the canary did not need explaining.

Three 6-channel small-buffer workloads did move, and their intervals exclude
zero, so this is signal rather than noise:

| workload | median | 95% interval | noise |
|---|---|---|---|
| `dsf-6ch-null-small` | +1.30% | [+1.14%, +1.64%] | 0.47% |
| `dff-6ch-null-small` | +1.26% | [+0.99%, +1.52%] | 0.52% |
| `dsf-6ch-repack-small` | +1.07% | [+0.75%, +1.36%] | 0.66% |

All are four times inside the gate, so nothing here blocks the phase.

## An unverified hypothesis about why

Text grew 23,920 bytes. Every hot function moved. The three functions carrying
the P12 4096-byte alignment attribute moved by exactly 0x4000 and so kept their
page alignment: `sox_flow_effects` 0x3b000 to 0x3f000, `dff_read` 0x72000 to
0x76000, `dff_read_fragment` 0x71000 to 0x75000. That is the remedy working.

`lsx_readbuf` and `lsx_read_b_buf` carry no such attribute and moved by 0xd00,
changing their offset within a page. Those two are what the 6-channel
small-buffer partial-cluster path exercises most heavily, which makes their
displacement a candidate explanation for exactly the three workloads that moved.

**This is a hypothesis we have not tested.** We did not run the dead-padding
experiment that would confirm or refute it, and we have no profile of these
three workloads. This project has advanced and then refuted three such
mechanisms before, so it should be treated as a direction to investigate rather
than a finding. Deferred to `docs/dsd/OPTIMIZATION_BACKLOG.md`.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.

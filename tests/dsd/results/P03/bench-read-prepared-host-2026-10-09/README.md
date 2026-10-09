# P03 read/repack throughput gate, prepared host (2026-10-09)

**Verdict: PASS.** All sixteen workloads are comparable and all sit within
±2.26%, against the design's 5% median regression limit, on a host meeting the
2% noise precondition.

Baseline `cce14f44` (P02) against candidate `21ac0e78` (P03), built
identically, 15 randomised AB/BA pairs per workload after 2 discarded warmups,
every run pinned to one CPU with sources and outputs on tmpfs, on a host
prepared with `tests/dsd/benchprep.sh prepare --cpu 8` whose probe reported
0.0% spread. 544 commands, zero errors.

| Range | Workloads |
| --- | --- |
| Fastest | `dff-2ch-null-large` at -1.86% |
| Slowest | `dsf-6ch-null-large` at +2.26% |
| Noise | 0.23% to 1.21%, every workload under the 2% limit |

Every one of the sixteen workloads gates: unlike the P02 comparison, P03's seek
unification left decoded output byte-identical in both arms everywhere, so
nothing is excluded as not comparable. That is itself worth recording, since it
confirms the phase changed seek bookkeeping without disturbing what the readers
decode.

This closes the gate P03's handoff left open. That handoff reported a 27.1%
probe spread on an unprepared host and declined to claim a verdict, which was
the correct call at the time; it also predates the harness fix described in
`../../P02/bench-read-prepared-host-2026-10-09/README.md`.

Figures are from one AMD Ryzen Threadripper 7970X and are not a property of the
code alone.

# Benchmarking the DSD paths

The design's throughput gates reject a repeatable regression beyond **2%** on
an unchanged path. A result only counts against that rule if the host can
resolve an effect that small. This document records how to get there, and how
to report an honest verdict when you cannot.

## Why P01's gate came back inconclusive

P01's paired DFF throughput comparison produced median deltas of **-0.67%**
(1 channel), **-2.02%** (2 channels) and **-0.69%** (6 channels). Run-to-run
spread on a *single* binary was **12-20%**. The measurement error was roughly
ten times the effect under test, so the data could support neither "no
regression" nor "regression". It was reported as inconclusive, which is the
only defensible reading. See `tests/dsd/results/P01/bench-dff-matched-tmpfs/`.

Writing that up as "no regression detected" would have been technically true
and materially misleading. Do not do it. An unresolvable gate is an open gate.

## The dominant noise source is clock variation

On a developer workstation, frequency scaling swamps everything else. A
Threadripper 7970X at idle, sampled across threads, showed 2034, 2188, 2505,
2587, 3098 and 4373 MHz simultaneously, against a 545-5673 MHz range. A
benchmark that lands on a core at 2.0 GHz and then one at 4.4 GHz has nothing
to say about a 1% code change.

In descending order of impact:

| Source | Why it hurts | Fix |
| --- | --- | --- |
| Governor / EPP | 10x frequency window under `powersave` | `performance` governor and EPP |
| Opportunistic boost | Clock depends on thermals and active-core count | `boost = 0`, so the clock is flat rather than merely high |
| SMT sibling | A thread on the same physical core takes half its resources | Offline the bench core's sibling |
| Scheduler interference | Other work migrates onto the bench core | `taskset`, plus `isolcpus` for a real result |
| Cross-CCD placement | Separate L3 instances (4 on a 7970X) vary | Keep the pinned core inside one CCD |
| Filesystem | Page cache and writeback dominate short runs | Write to `/dev/shm` |

## Preparing a host

`tests/dsd/benchprep.sh` applies and reverts the machine-level settings. It
needs root, saves the previous values, and restores exactly what it saved.

```sh
sudo tests/dsd/benchprep.sh prepare --cpu 8   # fix clocks, offline cpu 8's sibling
tests/dsd/benchprep.sh status                 # confirm before trusting a run
tests/dsd/benchprep.sh noise --cpu 8          # measure the host's own spread
# ... run the benchmark ...
sudo tests/dsd/benchprep.sh restore           # put the machine back
```

Run `noise` first and believe its verdict. If the host cannot hold its own
spread under 2% on a fixed workload, it cannot adjudicate a 2% gate, and the
right output is an inconclusive gate rather than a number.

The `performance` governor with boost disabled leaves the machine hotter and
idling higher than normal. Always `restore` when finished.

For a result you intend to put in a release record, dedicate a core at boot
so nothing can share it:

```
isolcpus=8 nohz_full=8 rcu_nocbs=8
```

## Harness practice

Machine preparation is necessary but not sufficient. These matter as much:

- **Pair and alternate.** Run baseline and candidate interleaved in randomised
  order within one session, never one binary's batch followed by the other's.
  Drift in temperature or background load then affects both arms equally.
  `bench_dff.py` already does this; keep it.
- **Make each run 5-10 seconds.** P01's runs were ~1.23 s. Process startup and
  timer granularity are a fixed cost that shrinks as a share of a longer run.
- **Record CPU time as well as wall time.** P01 recorded wall only
  (`process_time` was null). For a single-threaded writer, CPU time ignores
  preemption and is substantially steadier.
- **Pin and fix the environment.** `taskset` to one core, `OMP_NUM_THREADS=1`,
  `LC_ALL=C`, output to `/dev/shm`. Consider `chrt -f` to reduce preemption.
- **Discard a warmup run** per arm before recording.
- **Verify correctness every run.** Hash the output. A faster binary that
  writes different bytes is not faster. P01 checked this in all 90 runs.

## Reporting a verdict

Decide from an interval, not a point estimate. Compute per-pair ratios, then a
Hodges-Lehmann estimate with a confidence interval, and compare the interval's
bound to the 2% rule:

- CI entirely within ±2% → the gate **passes**, and say at what confidence.
- CI excludes -2% on the slow side → the gate **fails**.
- CI spans the threshold → **inconclusive**. Name the host, the observed
  spread, and what would be needed to close it.

This is what makes a quiet host worth the trouble: it narrows the interval
until it falls on one side of the rule. Reporting a bare median invites a
reader to treat noise as signal.

State the host in every benchmark record: CPU model, governor, boost and SMT
state, isolation flags, and whether the run was pinned. Numbers from one
machine are not a property of the code, and the design says so explicitly.

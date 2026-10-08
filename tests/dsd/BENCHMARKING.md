# Benchmarking the DSD paths

`DSD_DESIGN.md` section 10 states the rule precisely: **no more than 5%
median regression** on unchanged native repacking or legacy paths, **valid
only when measurement noise is under 2%**, otherwise rerun on a controlled
host. Two different numbers doing two different jobs:

- **5%** is the regression gate - how much slower the candidate may be.
- **2%** is the admissibility precondition - how steady the measurement must
  be before the 5% comparison means anything.

Do not collapse them into a single "2% tolerance". A 3% regression measured at
0.5% noise passes; a 1% regression measured at 15% noise is inconclusive, not
a pass. `bench_dff.py` implements exactly this, with `regression_limit=.05`
and `noise_limit=.02`.

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
| The measuring tool | An interpreted probe has more variance than the effect | Compile the probe; see below |
| Governor / EPP | 10x frequency window under `powersave` | `performance` governor and EPP |
| Opportunistic boost | Clock depends on thermals and active-core count | `boost = 0`, so the clock is flat rather than merely high |
| SMT sibling | A thread on the same physical core takes half its resources | Offline the bench core's sibling |
| Scheduler interference | Other work migrates onto the bench core | `taskset`, plus `isolcpus` if `noise` says you need it |
| Cross-CCD placement | Separate L3 instances (4 on a 7970X) vary | Keep the pinned core inside one CCD |
| Filesystem | Page cache and writeback dominate short runs | Write to `/dev/shm` |

Verify a fix rather than assuming it. Comparing frequencies across cores is
not a check: idle cores are *supposed* to clock down, so a busy-versus-idle
spread looks alarming and means nothing. Sample the bench core under load,
which `benchprep.sh status` does.

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
spread under 2% on a fixed workload, the design's precondition is unmet and
the right output is an inconclusive gate rather than a number.

A prepared workstation does better than the P01 result suggests. On a
Threadripper 7970X with the governor fixed, boost off and the bench core's SMT
sibling offlined, the bench core holds a flat 3969 MHz under load and `noise`
reports **0.02%** spread over nine runs, against a 2% noise precondition. An
ordinary desktop is therefore adequate once prepared; P01's 12-20% was an
unprepared host, not an inherent limit.

The `performance` governor with boost disabled leaves the machine hotter and
idling higher than normal. Always `restore` when finished.

### Measure the host with a compiled probe, never an interpreted one

An interpreted probe measures its own runtime rather than the machine. The
first version of `noise` used a Python accumulator loop and reported 11.5%
spread on a host where a compiled probe reported 0.02%: the accumulator
outgrew 64 bits, so CPython switched to arbitrary-precision integers and
allocated on every iteration. Masking it to 32 bits still left 4.71%, from
ordinary interpreter allocation. The lesson generalises beyond this script -
a measurement tool with more variance than the effect under test produces
confident nonsense.

### What does not help

- **`nice`.** Renicing changes priority *among competing runnable tasks*. A
  pinned benchmark on an otherwise idle core has nothing to compete with, so
  there is nothing for `nice` to arbitrate, and negative values need root
  anyway. At 0.02% spread there is no headroom left for it to recover.
- **`chrt -f`.** Real-time priority does preempt a normal task that wanders
  onto the bench core, which makes it cheap insurance for a long unattended
  run. It is not a fix for a noisy host, and it cannot stop interrupts or
  kernel work, which ignore scheduling priority entirely.
- **`isolcpus`,** on this evidence, is worth less than expected. It removes
  timer ticks and stray kernel work from the core and is still the right
  answer for a release-record measurement, but a prepared core already
  measures at 0.02%. Reach for it when `noise` says you need it, not
  reflexively:

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

Decide from an interval, not a point estimate, and check the two conditions in
order. `bench_dff.py` already reports `measurement_noise`, `regression_percent`
and a paired bootstrap 95% interval per channel count.

1. **Is the measurement admissible?** If noise is at or above 2%, the result is
   `inconclusive-noise` whatever the median says. Name the host and the
   observed spread, and stop.
2. **Does it clear the gate?** With noise under 2%, compare the regression
   against 5%: interval entirely under 5% slower → **pass**; interval entirely
   above → **fail**; interval straddling 5% → inconclusive, and gather more
   pairs or a quieter host.

This is what makes a quiet host worth the trouble: it narrows the interval
until it falls on one side of the rule. Reporting a bare median invites a
reader to treat noise as signal.

State the host in every benchmark record: CPU model, governor, boost and SMT
state, isolation flags, and whether the run was pinned. Numbers from one
machine are not a property of the code, and the design says so explicitly.

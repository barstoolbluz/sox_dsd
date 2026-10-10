# P10 one-hour mixed-content soak, SSE2 family, prepared host (2026-10-10)

**What ran: one 3600-second mixed-content soak per mastering profile, three of
three, on this hardware.** Every substantive admission check passes at every
rate. This directory is evidence for design 10.5's
`representative_hardware_1hour_per_profile_isa` gate; it does not mark that gate
passed. See "What this does not claim" below.

| Profile | Native Hz | Native frames | 28-bit excursions | ones range | nonfinite | worst bound use | CPU s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `encode.mastering.v1.dsd64` | 2822400 | 10160640000 | 0 | 7-21 | 0 | 6.05% | 291 |
| `encode.mastering.v1.dsd128` | 5644800 | 20321280000 | 0 | 6-22 | 0 | 6.37% | 584 |
| `encode.mastering.v1.dsd256` | 11289600 | 40642560000 | 0 | 6-22 | 0 | 6.21% | 1131 |

Totals: **71,124,480,000 native frames** encoded, **71,124,479,919** complete 28-bit
windows with **0** excursions, **0** nonfinite states, **0** monitor overloads,
worst integrator-state utilisation **6.37%** of the frozen bounds in
`tests/dsd/reference/p10_guards.json`, 2006 CPU seconds total.

Frame accounting is exact at every rate: input frames equal 3600 times the
source rate and committed native frames equal processed native frames equal 3600
times the native rate, so no sample was lost or duplicated. Each rate recorded
61 continuation snapshots with sha256 hashes, as 10.5 requires, and
`state_bound_crossed` is false throughout.

## Method

Fixture `p10-soak-nominal-v2`, 3600 audio seconds per rate, 60-second segments,
one uninterrupted encoder instance per rate. Driven by
`tests/dsd/soak_p10.py --seconds 3600 --segment-seconds 60 --fixture nominal-v2`,
pinned to CPU 8 with `taskset`, on an AMD Ryzen Threadripper 7970X with the
bench preparation from `tests/dsd/benchprep.sh` still active. The unit binary
was built from this tree with `-O2 -g`; its sha256 and the source generator's
are recorded in each `-execution.json`. The mixed-content sequence is six
one-minute segments (silence, DC +0.7, DC -0.7, four-tone multitone,
index-seeded uniform noise at peak 0.45, 1000 Hz sine at peak 0.8), so one hour
is ten full cycles.

ISA family: this build selects kernels at compile time in `src/sdm_x86.h`
(`#ifdef __AVX__` / `#elif __SSE2__`) with no runtime dispatch, and a `-O2`
build with no `-march` defines only `__SSE2__`. There is therefore exactly one
ISA family at P10 and the gate's per-family multiplier is one. P11 introduces
runtime kernels and reopens this gate for each family it adds.

## Checks

Passing at all three rates: `admitted_peak`, `clean_terminal_status`, `complete_snapshots`, `complete_window_monitor`, `dsd64_28bit_population`, `exact_native_duration`, `observed_half_guard`, `original_configuration`, `reproducible_binary`, `source_and_native_identity`, `stable_state`.

`release_sequence` is **false** at all three rates, and is the only false check.
It is defined in `tests/dsd/soak_p10.py` as `seconds == 1800 and segment == 60`,
so it asserts that a run *is the 30-minute release sequence*. A 3600-second run
is not, by construction. The harness has no one-hour flag, which is why its
summary reports `status: FAIL` while every substantive check passes. That FAIL
is a labelling artifact of an inapplicable assertion, not an observed defect.

## What this does not claim

The qualification collector hardcodes this gate to `UNRUN` at
`tests/dsd/qualify_p10_corrective.py:180` and inspects no evidence path, and
`soak.json` likewise carries `representative_hardware_hour_per_profile_isa:
UNRUN`. Nothing here was edited to change that. Design 10.5 states that a model
session "may deliver the runnable test and accurately report a missing hardware
run, but may not mark the corresponding release gate passed", and defining the
acceptance check for a gate while also executing it would be self-certification.
So this records the hardware run and its measurements; a round that owns the
acceptance criterion should decide whether these traces discharge the gate and
fold the result in.

A deterministic resume replay over these snapshots was not run. The second
mandatory gate, an independently sourced real-world mastering corpus, remains
unrun and cannot be satisfied by generated stimuli.

P10 remains INCOMPLETE with all three profiles unqualified and promotion
blocked. Figures are from one host and are not a property of the code alone.

# P05 interruption checkpoint

Source input: `sox_ng-P05-32d4b29e.tar.gz`, SHA-256
`c26f94ad65375e81658936b94cd92829aa8214b4d3991b15cba074f42fefef4e`.
No upstream `.git` was supplied. A local Git checkpoint exists only in the
working directory; release archives exclude Git and generated build files.

## Implemented and verified before final packaging

The private exact-rate descriptor, DSD/PCM/DoP domain planner, command-line
preflight, effects syntax and reports are implemented. Opt-in plans insert
per-input reconstruction before gain/parallel combination and block
unimplemented composite DSP before opening the output. Defaults are unchanged.
Both manpages and the `make check-dsd` target include P05 behavior.

The inherited DSD runner produced 36 PASS / 0 XFAIL / 0 FAIL / 0 SKIP. Generic
`make check` and extended `make check-dsd` passed on a clean build. The P05
independent CLI matrix produced 81 PASS / 0 FAIL and the C unit suite 131 PASS /
0 FAIL after adding mixed-native-clock cases. The P05 microbenchmark has 11/11
successful repetitions at each of 1, 4, 16 and 64 inputs. The development
benchmark produced 36/36 results. These are not a qualified throughput result:
`tests/dsd/benchprep.sh status --cpu 0` reports an unprepared host.

## Resumption instructions

The full verification handoff is `docs/dsd/handoffs/P05.md` once written.
If this checkout is interrupted, run `git status`, then rerun `make check`,
`make check-dsd`, `python3 tests/dsd/run.py --phase P05 --results
 tests/dsd/results/P05` and P05-specific tests. Regenerate the P00 manifest
when source bytes change. Package only tracked source/evidence, with no
compiled outputs, `.git`, `__pycache__` or machine-path substitutions.
Do not claim that P06/P07/P08 reconstruction or P09/P10 modulation executes.

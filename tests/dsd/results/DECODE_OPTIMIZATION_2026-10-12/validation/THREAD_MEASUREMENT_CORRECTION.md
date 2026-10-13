# Thread setting correction

The initial `measurements/dsd256-six-channel-two-threads/paired.json` inherited
bench_p11_e2e.py's assumption that omitting --single-threaded enables threads.
It does not: src/libsox_ng.c initializes sox_globals.use_threads to sox_false.
That arm had affinity CPUs 1,2 and OMP_NUM_THREADS=2 but **single-threaded SoX**.
Its immutable raw commands are retained. Do not classify it as parallel evidence.

The new benchmark now supplies --multi-threaded explicitly for --threads 2.
`measurements/dsd256-six-channel-explicit-two-threads/paired.json` is the
replacement parallel-setting comparison. Its command and build OpenMP setting,
not its directory name alone, define the tested configuration. The revised
harness also compares baseline first regardless of argument order, rejects empty
actual-decoder diagnostics, and records invocation metadata before errors.

The originally executed script is retained as tools/bench_decode_optimization.executed.py.
One-thread results are unaffected: their commands already explicitly used
--single-threaded. No production code changed for this measurement correction.

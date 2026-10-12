# P12 canary correction validation (2026-10-11)

The original qualified-host evidence is preserved in the pre-existing
`P12_throughput_prepared_host_2026-10-11` and
`P12_perf_diagnosis_2026-10-11` directories.

`local-benchmark-summary.json` is a derived, path-free summary of a new
paired repack comparison on an unprepared virtualized AMD EPYC host. The
unqualified VM's noise exceeded the design's 2% admissibility threshold;
the reported nominal speedup on the DFF six-channel small-buffer canary is
not represented as a passing release gate. Every tested output remained
byte-identical. See `docs/dsd/handoffs/P12_CANARY.md` for command parameters,
raw qualified-host references, code change and executed test results.

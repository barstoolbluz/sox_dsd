# P06 interrupted-session recovery

Input: sox_ng-P06-d8295118.tar.gz, SHA-256 cfe56558046ce8faa130faaaa41f5b5259d3eb3485009e5140d2cf16038e75f0.
Working tree: extracted source; no build performed at checkpoint.
P06 scope: private coefficient banks and scalar finite reconstruction; preserve P05 opt-in planner and CLI nonactivation.
Acceptance: four certified banks, six native profiles, independent extrema/alias/high-precision finite operator oracle; inherited 36 runner pass is baseline.
Check logs and status updates under tests/dsd/results/P06. Regenerate distribution manifest only at final packaging.
Source files to create: src/dsd_coeffs.h, src/dsd_decode.c, src/dsd_kernels_scalar.c, src/dsd_kernels.h, tests/dsd/generate_coeffs.py, tests/dsd/certify_filters.py, tests/dsd/test_decode.c, tests/dsd/test_decode.py, tests/dsd/bench_decode.py.

Implemented and compiled: four binary64 banks (57/117/153/257), private scalar 1/2-phase FIR cascade, mirrored per-channel halos, 6 descriptors, C unit + independent high-precision oracle, frequency/alias certificate, benchmark instrumentation.
Verified by executable tests: 93640 C unit assertions, 1056 vectors, 58408 scalar sample comparisons, 5656 75-digit checks, all six profiles pass stop and alias envelope; measure.py P06 7/0.
Pending: make check, make check-dsd P06, bench.py, sanitizer, source-only packaging and manifests/handoff. Prior P00-P05 evidence must not be rewritten.

# P01 native DFF throughput qualification: OPEN

As of October 8, 2026, the functional P01 writer gates pass, but the native
throughput acceptance gate remains unqualified. The before/after benchmark
completed all 45 timed pairs, validated 90 native DFF outputs, and exited **2**
(noisy measurements). Candidate median changes for 1/2/6 channels were
-1.60%, -1.57%, +1.99%; robust noise was 4.80%, 4.85%, 17.63%, respectively.
None meets the original strict <2% timing-noise threshold. No production code,
benchmark, or acceptance threshold was modified in this follow-up. Re-run the
existing benchmark on a controlled host and retain raw qualification evidence.

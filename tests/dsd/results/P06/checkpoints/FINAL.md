# P06 source handoff recovery

Source of truth: attached SHA256 cfe56558046ce8faa130faaaa41f5b5259d3eb3485009e5140d2cf16038e75f0 plus the P06 modified source files enumerated in docs/dsd/handoffs/P06.md.
Final archive: sox_ng-P06-certified-source.tar.gz; root directory sox_ng; no .git, generated build products, or configured binaries.
Reproduce: autoreconf -fi; ./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'; make -j2; make check; make check-dsd; python3 tests/dsd/measure.py --phase P06 --results tests/dsd/results/P06/numeric.
Numerical acceptance: 4/4 bank certificates, 6/6 composite, 1056 independent scalar vectors, 58408 output sample comparisons, 5656 high-precision checks. Legacy runner 36/0. Controlled-host 5% throughput gate is inconclusive (9.5% repeatability spread versus 2% admissibility).
Open limitations: later P09 audio-corpus qualification, P07 integration; no current P06 functional defects found.
Fresh-source replay: autoreconf, configure, make -j2, make check, make check-dsd, P06 runner, P06 measure, and coefficient --check each exited 0; see replay/*.exit.

# P01 recovery checkpoint

Date: October 8, 2026. Status: localized implementation and correctness
tests pass; final qualification and packaging remain in progress.

Input: `sox_ng-P01-f636d65a.tar.gz`, SHA-256
`018451049d2355ba62bbe60ea60a23bcae576e33eff288bdf3e4ce4893d9aeef`.
The input contains no Git metadata. `docs/dsd/sows/P01.md`, design sections
1.2 and 4.1, and the P01 implementation-plan entry are authoritative.

Objective: repair only the DFF writer in `src/dsdiff.c`. Six P01 defect
tests must pass; thirteen P02-P04 defects stay expected. Add independently
derived vectors for empty/even/odd and multichannel files, all residual bit
counts 1..7, allocator perturbation, chronology and write/seek failure
propagation. Preserve the P00 raw evidence. Regenerate the distribution
manifest after changed files are final.

Recovery: extract this complete source tree into a fresh directory. Install
Autoconf, Automake, Libtool and ordinary C build prerequisites if absent.
Build a second unmodified copy from the original uploaded archive for the
before/after generic suite and native DFF benchmark. Use the same flags:
`autoreconf -fi`, `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'`,
`make -j2`. Store new command/exit/log evidence under `tests/dsd/results/P01/`.
Never overwrite P00 observations. `make check-dsd DSD_PHASE=P01` selects
the repaired phase; plain `make check-dsd` currently defaults to P00 and
would reject the intended repairs as XPASS. Resolve that default at handoff.

Remaining work: baseline build/gates, localized patch and regression vectors,
same-host paired 1/2/6-channel DFF throughput tests (15 timed repetitions,
warmups; 5% regression gate only if measured noise is below 2%), final gates,
P01 handoff, complete bundle and archive-integrity verification.

The first checkpoint contains unchanged production. The second contains the
localized repair and recorded baseline/fixed correctness runs. The baseline
P01 result is 17 PASS / 13 XFAIL / 6 FAIL; the corrected result is 23 PASS /
13 XFAIL / 0 FAIL / 0 XPASS / 0 skips, including 508 independent vectors.
The actual C unit executable passes 954 assertions over arithmetic, 42
channel/tail cases and ten I/O-error cases. Native numerical checks pass 5/5,
including nine DSF-DFF-DSF chronology/count cases. Default `make check-dsd`
now selects P01; explicit P00 against repaired production would give XPASS.

Remaining verification: same-host generic-suite reconciliation, the 36-case
development benchmark, repeated paired DFF throughput, final documentation,
updated hashes and a clean-archive rebuild. A checkpoint is a recovery
artifact, not the authoritative qualified delivery. Check `tests/dsd/results/P01/`
for newly completed gate exits before repeating work. The original input
and command-recording helper accompany checkpoint 02 under `resume/`.

Long performance command (change only result directory/frames if noisy):
`python3 tests/dsd/bench_dff.py --baseline-sox PATH/TO/UNMODIFIED/src/sox_ng
--results tests/dsd/results/P01/bench-dff --frames 67108864`.
It atomically saves every baseline/candidate sample; use `--resume` only
with the same binary, host, source bytes and configuration.

Checkpoint 03 / current continuation: the writer correctness suite passes
23/13 with 960 C assertions and eleven error cases. Generic coverage matches
73 OK / 8 VOID / seven skipped groups on byte-identical build configurations.
Both repeated throughput runs are recorded as inconclusive (exit 2), including
matched tmpfs timing; noise is 3.90%..5.98%, above the 2% gate. No production
change is justified by those timings. Re-run only performance on a controlled
host; preserve the 5%/2% limits. The next production phase is P02 after that
open gate closes. A clean-archive replay is the remaining local delivery step.

Local delivery checks are now complete: clean extraction verified 1,041
entries and all eight build/test/development commands exited zero. The final
bundle adds these replay records and a refreshed distribution manifest.
Only the controlled-host native throughput gate remains to qualify P01.

## Qualification continuation (October 8, 2026)

Independent validation retained the repaired writer unchanged and added
`tests/dsd/results/P01/qualification-2026-10-08/` with a matched-build P00
comparison, raw functional tests and native DFF throughput records.
`make check`, `make check-dsd`, five numerical tests and 36 development
benchmark cases all passed, with only the original six DFF writer expected
failures changing to passes. The paired native benchmark completed all
45 pairs (15 per channel count), validated every native output, but exited 2:
all three channel configurations exceeded the strictly below 2% noise ceiling.
This is not performance acceptance. The only P01 continuation task is a
controlled-host rerun of the existing `tests/dsd/bench_dff.py` with the
original thresholds. The new full archive is the authoritative continuation
source; this checkpoint is a status note, not authorization to start P02.

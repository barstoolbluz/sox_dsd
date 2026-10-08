# P01 performance follow-up: 2026-10-08

This folder records an independent follow-up to the P01 native DFF throughput qualification. **Do not call P01 performance accepted unless the recorded benchmark returns 0 with all three channel counts meeting the original limit.** Functional P01 correctness is already established by the original P01 handoff; the only audited open requirement is stable timing evidence.

## Before/after equivalence

- The exact unmodified P00 writer source is checked into the supplied bundle at `tests/dsd/results/P01/baseline/dsdiff.c` (SHA-256 `27b0c38214e76b821fa98d07d5ed94e5402513a9b79b4bcc280f600e994b99c1`). It was copied into a separate full build tree, replacing only `src/dsdiff.c`.
- All other production `.c`/`.h` source bytes match between the comparison and candidate trees. Both were built with `autoreconf -fi`, `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'`, and `make -j2`. Their generated `src/soxconfig.h` files are byte-identical. The separate build trees were created only for validation and are not packaged as replacement production sources.
- `source-comparison.json`, `binary-sha256.txt` and `build/*` record source, binary and command provenance.

## Method and decision

Run the supplied `tests/dsd/bench_dff.py` unmodified. It records two warmups and at least 15 randomized paired baseline/candidate writes each for 1, 2 and 6 channels, CPU affinity, actual elapsed/CPU times, hashes and structural/payload validation. It writes results atomically; a nonzero status is not a pass.

Acceptance is a maximum 5% median wall-time regression at less than 2% observed timing noise for **each** channel count. A >2% noise reading requires repetition on a controlled host, regardless of the direction of the measured median. This is an environmental qualification requirement, not permission to change the writer or benchmark thresholds.

## Evidence files

- `native-dff-134m/bench-dff.json`: complete raw paired-run results and decisions (when complete).
- `build/native-dff-134m.*`: exact executed command, raw log and exit status.
- `host-environment.json`: CPU, cgroup, memory and storage configuration.
- `build/*`: independent new build, generic and phase verification commands and exits.

## Remaining work

The controlled-host performance gate remains open unless the actual result JSON states `pass` and its process exit is zero. In that case, update the authoritative P01 handoff to declare completion and proceed to P02. Otherwise retain P01 as functionally complete but performance-unqualified; rerun on an isolated host with known frequency policy and low external contention. Do not alter production source in response to inconclusive measurements.

## Executed October 8 comparison

Built the baseline (exact supplied P00 writer) and candidate with matching
`autoreconf -fi`, `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'`
and `make -j2`, all exit zero. Generated `src/soxconfig.h` files match byte for
byte. The exact executed benchmark command (paths point to temporary separate
build trees, not to included binaries) was:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 LC_ALL=C \
python3 tests/dsd/bench_dff.py \
  --baseline-sox /mnt/data/p01_work/p00_baseline/src/sox_ng \
  --sox /mnt/data/p01_work/p01_candidate_build/src/sox_ng \
  --results /mnt/data/p01_work/sox_ng/tests/dsd/results/P01/qualification-2026-10-08/native-dff-134m \
  --frames 134217728 --repetitions 15 --warmups 2 \
  --cpu 4 --working-directory /dev/shm
```

This command returned exit **2**, not an accepted result. Its output files
contain 45 complete paired timing records (90 valid native DFF writes) with
median changes of -1.60%, -1.57%, +1.99% and noise of 4.80%, 4.85%, 17.63%
for mono/stereo/six channels. `verification-summary.json` gives case-by-case
functional changes, original generic-suite classifications, and the strict
performance outcome. `build/` contains source build and validation exit codes,
commands and logs; `host-environment.json` captures host limitations.

## Reproduction on a controlled host

Extract this complete source archive. Build two separate trees with the same
configuration and optimization flags. Restore only
`tests/dsd/results/P01/baseline/dsdiff.c` to `src/dsdiff.c` in the P00
comparison tree; keep the candidate tree unchanged. Check that both
`src/soxconfig.h` headers are identical and that the writer baseline hash
matches the P00 fingerprint above. Then run the same bundled
`tests/dsd/bench_dff.py`, replacing the temporary binary paths and result
path to match the controlled host. Retain 1-, 2- and 6-channel results, at
least 15 timed pairs per configuration, and both original acceptance limits.
Do not classify the result as a pass unless each noise reading is **<2%**,
each median candidate/baseline ratio is **<=1.05**, all audio output checks
pass and the program returns **0**. A repeatable slowdown greater than 5%
under qualified noise would justify localized profiling, not a speculative
production rewrite.

## Archive delta

`delivery-provenance.md` records the exact original archive SHA-256 and the
byte-comparison result: only the two P01 handoff documents and regenerated distribution manifest changed; new files
contain evidence only. The original corrected implementation and benchmarks
are byte-identical to the submitted candidate.

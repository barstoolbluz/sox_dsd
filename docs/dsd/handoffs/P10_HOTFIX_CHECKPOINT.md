# P10 hotfix continuation checkpoint (2026-10-10)

## Source identity and state

- Input archive: `sox_ng-P10hotfix-e2501084.tar.gz`.
- Input SHA-256: `be542972b131ea9ad783ede2112fe86b3f78e9900b78ed452e5006e365537890`.
- Working source tree: unpacked copy of this archive; prior committed evidence must not be changed.
- Current gate baseline: P10 INCOMPLETE, promotion BLOCKED; one-hour hardware PASS; real-world corpus PARTIAL; observed DFF throughput interval fails.

## Recovery procedure

1. Extract the original archive to recover the untouched input snapshot.
2. Apply the modifications recorded in the final hotfix handoff (same tree); do not overwrite historical results.
3. Rebuild via autoreconf/configure/make, rerun smoke/regression tests, then prepare a source-only tarball with an updated P00 source manifest.
4. Do not claim the PCM external gate or 5% hardware throughput gate PASS without new measurements from the prepared hardware and actual recordings.

## Design decision pending tests

- Remove avoidable 192-byte stack formatting from the failure-only diagnostic while preserving explicit first-overload **lower bound** semantics.
- Add a separately runnable PCM_AUDIO corpus driver that validates inventory and clock-family coverage, stages remote FLAC just once, executes the unchanged test candidate composite and analyses observed outputs.
- Preserve every pre-existing results file byte for byte.

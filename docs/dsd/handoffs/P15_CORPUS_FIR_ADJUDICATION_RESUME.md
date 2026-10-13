# P10–P15 corpus FIR adjudication: continuation

**October 13, 2026. Decision: NO NEW DEFECT / NO NEW P15 GATE.** All three input archive hashes match `tests/dsd/results/P15_corpus_fir_adjudication_2026-10-13/source-archives.json`.

This is the **full pristine P15 `git archive` source plus additive tests and evidence**, not a small patch and not a new P15 release certificate. No production DSP or original P10–P15 result/handoff has been changed **except** the self-excluding P00 global SHA-256 inventory, which is regenerated last per the P15 continuation rules.

Read `docs/dsd/handoffs/P15_CORPUS_FIR_ADJUDICATION_2026-10-13.md` for the verdict, source trace, additional changed channel statistics, and exact limitations. P15 release defaults **remain blocked** by existing gates listed in `docs/dsd/handoffs/P15_CHECKPOINT.md`.

## Resume and rerun

Run in this tree; all new tests require only Python 3. The baseline and current corpus manifest JSON files are already bundled, but commercial audio is not.

```sh
python3 tests/dsd/adjudicate_p10_p15_corpus.py \
  --results /tmp/sox-ng-corpus-adjudication
python3 tests/dsd/test_adjudicate_p10_p15_corpus.py
```

The audit exit is 0 (`PASS-BOUNDED-DRIFT`) if and only if the recorded corpus meets all of the compared numerical, identity, admission and bounded-extrema checks. It is deterministic across runs and writes a single atomic `comparison.json`. Mutation suite has twelve cases, expected exit 0.

After optional build (same steps as source P15 checkpoint), reproduce the raw double probe:

```sh
autoreconf -fi
./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'
make -j2
./libtool --mode=link cc -O2 -I./src \
  tests/dsd/probe_p15_fir_roundoff.c ./src/libsox_ng.la -lm \
  -o /tmp/sox-ng-p15-fir-roundoff-probe
/tmp/sox-ng-p15-fir-roundoff-probe
```

The SSE2 probe requires an x86 SSE2-capable build. Existing supported tiers and default selection remain unchanged.

**Caution:** The P10 source-revision checker must **not** be expected to pass on P15; use P10's original bytes for P10 historical certificate verification. Do not modify the four source hashes or old result directories to force qualification. Do not use this work package to authorize P15/P16 or enable new defaults.

## Additional evidence

- `tests/dsd/results/P15_corpus_fir_adjudication_2026-10-13/comparison.json`: machine-readable old/new field and trial-scope comparison.
- `pregraph-fir-roundoff.jsonl`: six standalone rate/profile measurements.
- `synthetic-lineage.json`: source tree comparison for one deterministic generated fixture.
- `audit-mutations.log`: 12 tests PASS.
- `kernel-unit-p11-p12.log`: available compiled tier-unit suites PASS.
- `historical-p10-certification.log` / `current-p15-certification-expected-failure.log`: immutable P10 verifier PASS on P10, expected source hash mismatch on P15.
- `sha256-of-new-files.txt`: integrity ledger for additive files (self-excluding).

To continue later, start from the source in this package and from `docs/dsd/handoffs/P15_CHECKPOINT.md`; do not replace the original archives or historical recorded evidence. Tests and this adjudication are already complete.

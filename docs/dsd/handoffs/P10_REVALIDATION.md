# P10 revalidation: harness corrections; DSP results corroborated

**Revalidation: PASS after correction. P10 release: INCOMPLETE. All three
mastering profiles remain unqualified and unpromoted.**

Reviewed input: `sox_ng-P10-corrective-unpromoted-2026-10-10.tar.gz`, SHA-256
`4b182e38fd94ace650faa6a18494cc40c8013151bd9bd621d9915553183fe0b8`.
This review used the delivered bytes, `P10corrective_brief.md`, the P10 SOW,
and the approved design. It does not replace a missing release gate with a
review verdict or move the project to P11.

## Findings and corrections

### 1. The nominal-soak runner generated receipts its own inspector rejected

`tests/dsd/soak_p10.py` required `execution.fixture == 'nominal-v2'` when
inspecting nominal results, but its `run()` function never wrote `fixture`.
Successful encoder runs therefore failed the `reproducible_binary` check.
The inspector also hashed the default executable even when `--unit` selected
a different executable. The archived passing receipts contained the fixture
field; the delivered runner could not recreate those receipts as written.
This is a reproducibility defect in the harness, not evidence that the stored
DSP run failed.

Before correction, actual one-second nominal runs at all three native rates
completed with encoder exit 0/status 3, but each receipt omitted `fixture` and
each inspector identity check was false. Those negative observations remain in
`tests/dsd/results/P10_revalidation/pre-fix/nominal-smoke/`. A one-second run is
also too short for release qualification; that independent duration failure
has not been relabeled a pass.

Correction: write the selected fixture in the execution receipt and pass the
selected executable to every inspection. Four live tests exercise default and
alternate executable selection, receipt identity, result retention and
idempotency. They also verify that short runs cannot claim release-duration
success. A fresh full-duration DSD64 run verifies a positive runner/inspector
roundtrip without hand-editing the receipt.

### 2. The collector accepted incomplete rate coverage and stale summaries

`tests/dsd/qualify_p10_corrective.py` checked the number of profile entries but
not that those entries covered three distinct native rates. Repeating the
DSD64 entry three times passed the nominal gate; the original-overload replay
gate had the same omission. The stage gate trusted `classification.json`
without rechecking the underlying measurements. The soak gate trusted cached
admission booleans without binding all inspected measurements to the current
raw report. In a direct reproduction, a raw state maximum changed to 1e100
still passed that nominal gate while its old summary remained unchanged.

The corrected collector requires the expected distinct rate set, recomputes
stage classification without modifying historical files, checks the expected
probe set and histogram counts, and binds soak reports, configurations,
execution identities and snapshots to the audited summary. It also checks the
actual state maxima against the already frozen bounds. No bound changed.

The stage classifier now has a read-only `classify()` entry point; the command
that intentionally writes a classification report remains separate. The
original-overload comparison ignores only `cpu_seconds`, rather than trusting
an `identical_fields` flag for the remaining reported signal/state fields.
The adverse tests grew from seven to sixteen. Red/green evidence shows the
old collector accepting four defective evidence combinations and the corrected
collector rejecting each one.

The delivered historical records themselves passed these corrected checks.
The findings concern reproducibility and future evidence accounting, not a
retroactive discovery of failed nominal audio.

### 3. The previous handoff overstated source-sample identity

The earlier statement that direct nominal generation and explicit attenuation
of the original source produce the same admitted sample stream was too strong.
The two operations have the same intended level, but the latter quantizes an
already quantized source again. The actual unchanged C generator measured
430,930 differing samples out of 2,646,000 at 88.2 kHz, and 860,468 out of
5,292,000 at 176.4 kHz, over the 30-second noise probe. The maximum difference
was one int32 quantization step. Floating normalized sample differences and
the explicit integer-step count are recorded together.

`test_p10_fixture_rounding.c` exercises the original generator without changing
the hash-pinned `test_p10.c`. The handoff now distinguishes equivalent intended
level from bit-identical source samples. Neither fixture nor attenuation changed.
Both observed paths still pass admission and state checks. No assertion of
identical resulting DSD trajectories follows from their nearly equal levels.

## Independent executions in this review

A fresh extraction passed Autotools configuration, compilation, `make check`,
and `make check-dsd`. Compilation emitted no compiler warnings. The inherited
runner reported 36 pass, 0 fail, 0 skip. The P10 core reported 105,474 assertions
with no failures; the candidate CLI reported 63 pass, 0 fail; fourteen original
qualification-accounting tests and three replay-contract tests passed.

All 183 inherited numerical render/control observations were rerun. Every
native-bit hash and every compared significant frame/state field matched.
This corroborates the unchanged numerical evidence; it is not a new independent
analysis-v1 reconstruction or a new real-world corpus.

All 18 stage probes were rerun: nine DC paths and original/nominal/explicitly
attenuated noise at each of three native rates. Every raw observation JSON was
byte-identical to its archived counterpart. The corrected classifier passed.
This directly corroborates the stage gains, once-only 0.5 reference scaling,
measured distributions and the original overload classification.

A fresh continuous DSD64 nominal-v2 soak completed 1,800 audio seconds and
5,080,320,000 native frames. The corrected runner produced its own valid receipt.
All admission checks passed, all 31 continuation/final snapshot files matched
the archived snapshots byte-for-byte, and every reported signal/state field
matched except the deliberately excluded execution-time field. There was no
overload, guard crossing, nonfinite state or 28-bit-window excursion.

This new full-duration runner test intentionally selects DSD64 only. It does
not claim that DSD128/256 were rerun for 30 minutes in this review. Their
previous complete results, raw reports, execution records, bounds and snapshot
hashes were revalidated in place with the corrected collector. All historical
P10 and corrective evidence remains byte-identical.

## Assessment and release scope

The human reviewer's central determination remains supported: the original
0.7-peak noise is an expected-overload stimulus under the approved envelope,
not a demonstrated gain or modulation defect. The nominal fixture remains a
separate, measured passing case. The design's admission policy was not relaxed.

No file under `src/` changed in this revalidation. The composite pipeline,
coefficients, NTF identities, guard bounds, original failure cases, fixtures,
reference scale and production activation policy are unchanged. The nine
analysis-v1 resources and both historical negative profile manifests remain
unchanged. Their generator's `--check` still passes.

P10 release qualification remains **INCOMPLETE**: the representative-hardware
one-hour per-profile/ISA runs and independent real-world corpus are unrun.
The inherited controlled-host native read/repack gate is still historical
evidence; no new controlled-host timing or encoder speedup is claimed here.
No profile was qualified, promoted or made a default.

## Reproduction and evidence

Commands are relative to a clean source extraction. Use new result directories;
do not overwrite P00-P10 or the original corrective receipts.

```sh
autoreconf -fi
./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'
make -j3
make -j3 check
make -j3 check-dsd DSD_RESULTS="$PWD/revalidation-local/regression"
test/dsd_test_p10 --unit
python3 tests/dsd/test_p10.py --sox src/sox_ng --candidate test/sox_p10_candidate --results revalidation-local/cli
python3 tests/dsd/test_p10_qualification.py
python3 tests/dsd/soak_p10.py --test-replay --results revalidation-local/replay
python3 tests/dsd/test_p10_corrective_qualification.py
python3 tests/dsd/test_p10_soak_receipts.py --full-dsd64 --results revalidation-local/receipts
python3 tests/dsd/verify_p10_corrective.py --results revalidation-local/stages
python3 tests/dsd/replay_p10_numeric_bits.py --results revalidation-local/bits
python3 tests/dsd/generate_p10_corrective_profiles.py --check
```

The evidence collector still reports exit 2 (`INCOMPLETE`); a review pass does
not change that contract. The profile check reads the archived evidence and
does not claim a fresh executable has the old executable's SHA-256. New builds
must use new result directories, as above, for binary-pinned receipts.

The optional rounding audit builds without changing the hash-pinned generator:

```sh
./libtool --mode=link gcc -DHAVE_CONFIG_H -Isrc -I. -O2 tests/dsd/test_p10_fixture_rounding.c src/libsox_ng.la -o revalidation-local/fixture-rounding
revalidation-local/fixture-rounding
```

New results and sanitized execution logs are under
`tests/dsd/results/P10_revalidation/`. `review.json` separates current execution
from historical reinspection. `preservation.json` records the immutable input
archive, changed source paths and historical-evidence audit. The P00 SHA-256
index covers the complete source-only continuation. No copy of the corrective
brief or compiled executable is included in the delivered tree.

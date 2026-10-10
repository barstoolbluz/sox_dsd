# P10 independent closeout / release-gate adjudication (2026-10-10)

**Decision: INCOMPLETE; all mastering profiles remain UNQUALIFIED; promotion
BLOCKED.** This is the verdict for the input snapshot identified in
`P10_RATIFICATION_WORKLOG.md`, NOT a new profile certificate. Original
measurements, negative certificates, source audio provenance and historical
collector remain unchanged. A separate versioned evidence collector and
criteria manifest record this ruling without recertifying the engineer's runs
by writing their own acceptance standard.

## Authority and acceptance criteria

`docs/dsd/DSD_DESIGN.md` sections 7.2, 10.1, 10.2 and 10.5 and
`docs/dsd/sows/P10.md` govern; the executable criterion is
`tests/dsd/reference/p10_ratification_criteria.json`. The numerical test
matrix, 30-minute synthetic soak, analysis-v1 and prepared-host performance
receipts remain independent *inherited* gates. Do not let this ratification
replace or weaken them.

### 1. One hour per released mastering profile and kernel/ISA family

- Execute one continuous, stateful, deterministic mixed-content **3600-second**
  stream on representative physical hardware for each DSD64, DSD128 and DSD256
  profile and each currently implemented mastering-kernel family. Record host,
  executable/source hashes, profile/segment configuration, all continuation
  states and their hashes. The current P10 guarded mastering recurrence is a
  **scalar** kernel (`src/sdm.c:sdm_normal_step_impl`). Its x86-64 baseline build
  can define SSE2 while running that scalar recurrence; this does **not**
  establish qualification of an optimized SSE2 mastering implementation.
  Future P11 kernel/ISA variants require their own qualification.
- Require exactly 3600 seconds worth of source and native frames, corresponding
  complete bit-window counts, completed output, no fatal status, no nonfinite
  values, no nominal 0.5-envelope crossing or frozen integrator guard breach.
  For **DSD64 only**, every complete 28-bit window must contain 4 through 24
  ones. Retain state extrema and window/run data at DSD128/256 as diagnostics,
  without misapplying the DSD64 population limit.
- Verify each rate's 60 intermediate and final continuation records against
  their digests, counters and frozen bounds. The 1800-second 30-minute gate
  remains separately enforced; a 3600-second run is not required to report
  literally the old `release_sequence` field's obsolete 1800-second equality.

**Ruling: PASS for the existing scalar P10 family.** The three archived runs
cover 3600 audio seconds each, all three rates, 71,124,480,000 native frames,
71,124,479,919 complete 28-bit windows, 183 hashed continuation snapshots,
zero observed DSD64 window excursions, zero nominal-envelope crossings, zero
nonfinite states, no observed guard crossings and exact final frame counts.
The reported physical host is an AMD Threadripper 7970X; the evidence has
operator-supplied machine provenance, not an independent hardware attestation.
Every material check in the original receipts succeeds. Original `soak.json`
still says FAIL because the earlier `release_sequence` equality accepts exactly
1800 rather than 3600 seconds. The new collector checks the underlying records
instead of rewriting historical measurements. `soak_p10.py` now treats complete
60-second sequences of at least 1800 seconds as release-length sequences.

### 2. Independent real-world mastering-source corpus

The design requires independent DSD material and source-aware PCM/DSD encoder
qualification; SOW P10 and the earlier P10 corrective handoff explicitly call
out independent **PCM and DSD mastering sources**. A generated synthetic soak
cannot discharge this obligation. The criterion samples each of the 3 target
rates and **both source domains** (`DSD_NATIVE` preserve-reference
remodulation; `PCM_AUDIO` with ordinary 0.5 PCM input scaling). To avoid
accepting a single nonrepresentative excerpt as a corpus, require at least two
independently sourced recordings for each rate/domain, at least 60 seconds per
excerpt, two musical genres per domain, and both PCM 44.1-kHz and 48-kHz source
clock families in the PCM arm. These last cardinality and duration choices are
conservative operational minima, **not numeric thresholds stated in the
design**; future broader claims need broader material.

For each sample retain source/release/provenance metadata and the SHA-256 of
its exact excerpt; source clock, channel layout and target rate; deterministic
CLI graph and exit status; admitted/failed report; and an independent DSF bit
reader/oracle check. Require exact admitted native frames per channel, checked
window counts and DSD64 population; reject overload with nonzero process exit
rather than clipping or silently applying gain. Explicit attenuated retries
may be recorded for rejected files. Compare source and reconstructed output
levels with **source-appropriate reference normalization**: preservation for
DSD-origin, SACD reconstruction for ordinary PCM-origin, no extra 6.0206 dB
loss. The 0.25 dB RMS and 0.5 dB peak comparison tolerances accommodate
independent reconstruction and measurement rather than assert bit equality
between separate encoders. The earlier analysis-v1 spectral targets remain
inherited; unmeasured corpus spectra or state extrema must not be claimed.

**Ruling: PARTIAL.** `DSD_NATIVE` **PASS** on the retained measurements: 18
distinct sourced excerpts (six per rate), 120 seconds each, 12 genres, 14
unattenuated admissions with level preserved and 4 correct overload rejections
followed by successful explicit attenuation. The recorded independent DSF
reader matches the inherited bit-oracle fixture. The evidence describes the
recordings as commercial releases, but their actual media are not included,
so this reviewer cannot independently re-create the reads or verify every
commercial release's provenance. Some manifest rows have generic release
labels; do not infer eighteen distinct retail *releases* from the count of
source-name identity fields. Count **distinct recordings/excerpts**, not
unverified release titles.

`PCM_AUDIO` **UNRUN**: there are no external ordinary PCM source receipts.
Hence the combined `independent_realworld_corpus` gate is **PARTIAL**, not PASS.
No extra PCM harness or actual third-party PCM audio is fabricated in this
round. If legitimate audio becomes available outside the source archive,
record `pcm-sources.json`, `pcm-unity.json` and (if needed) `pcm-ladder.json`
using the named fields in `ratify_p10_gates.py:validate_domain` and
`check_complete`. The collector accepts those records when their provenance,
rates, reference scaling, bit windows, frames and retry evidence meet the
criterion. Do not distribute unlicensed source recordings or infer compliance
from schema-only fixtures.

## Level, interpolation and attenuation conclusions

The encoder admits a post-interpolation, post-reference-scale amplitude of at
most approximately 0.5; it does not decide based solely on input-file sample
maxima. The current eighteen preserve-reference DSD excerpts happen to split
into unattenuated admissions and overload rejections at that source peak,
but this is an observation, not a universal admission test. The four rejected
source peak levels alone imply a need for attenuation inside their observed
coarse gain-ladder brackets. **That is consistent with zero interpolation
overshoot; it does not measure or prove zero overshoot.** Neither successful
post-interpolation peaks nor full-stream peak maxima were captured, so do not
report an interpolation contribution or claim it was disproved.

`src/pcmdsd.c` previously logged `minimum explicit attenuation` computed from
the **first** offending interpolated sample and stopped. A later peak can
require substantially more gain reduction (as `Bone Machine` demonstrates), so
treating this number as the entire file's sufficient correction is incorrect.
Design section 7.2 deliberately specifies failure on the first observed
breach; we retain fail-fast processing, native-frame/channel diagnostics,
partial-block discard and no automatic gain change. The CLI diagnostic now
explicitly calls the figure a **lower bound from the first overloaded sample**
and warns that later peaks may require more. Non-overload failures report no
attenuation estimate. The private struct field is documented accordingly;
this is a semantic reporting correction, not a new full-file measurement or a
second DSP pass. `test_p10.py` now tests the message and failure semantics.

## Versioning, collector and promotion

Run from the repository root:

```sh
python3 tests/dsd/test_p10_ratification.py
python3 tests/dsd/qualify_p10_ratification.py \
  --output tests/dsd/results/P10_ratification_2026-10-10/qualification.json
python3 tests/dsd/qualify_p10_ratification.py --check \
  --output tests/dsd/results/P10_ratification_2026-10-10/qualification.json
```

The latter two commands exit **2** while qualification is INCOMPLETE;
this exit code is intentional and must not be converted into a PASS.
`tests/dsd/results/P10_ratification_2026-10-10/qualification.json`
records all ten gates: the newly measured one-hour hardware gate PASS, the
real-world corpus PARTIAL, and all eight inherited gates PASS, for overall
INCOMPLETE. The existing `qualify_p10_corrective.py` and its historical
negative certificate still contain their original UNRUN labels and bytes;
for current P10 disposition, use this versioned ratification collector.
A PASS of both evidence gates in the future is necessary but does not
silently activate a mastering profile or change P15 release defaults; that
requires an explicit positive certificate and the applicable release process.

## Executed validation on the delivered changes

- `autoreconf -fi`: **PASS (0)**.
- `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'`: **PASS (0)**.
- `make -j2`: **PASS (0)**, source-level diagnostic compiled.
- `make check`: **PASS (0)**.
- `test/dsd_test_p10 --unit`: **PASS (0)**, 105,474 assertions, 0 failures.
- `python3 tests/dsd/test_p10.py --sox src/sox_ng --candidate test/sox_p10_candidate --results <out-of-tree-dir>`:
  **PASS (0)**, 63/63 CLI cases, including nonzero exit on interpolation
  overload, explicit lower-bound label, output rejection and retry.
- `python3 tests/dsd/test_p10_corrective_qualification.py`: **PASS (0)**,
  16 inherited adversarial tests.
- `python3 tests/dsd/test_p10_ratification.py`: **PASS (0)**, 18 new
  adversarial source/receipt integrity cases. Its synthetic positive PCM
  record tests only the receipt schema, not independently sourced PCM audio.
- `python3 tests/dsd/test_p10_soak_receipts.py --unit test/dsd_test_p10 --results <out-of-tree-dir>`:
  **PASS (0)**, 4 idempotency and source/binary receipt cases; the short
  fixtures do not qualify a sustained soak.
- `make check-dsd DSD_PHASE=P10 DSD_RESULTS=<out-of-tree-dir>`:
  **PASS (0)** on the complete inherited DSD suite, including P07, P08 and
  P09 executable/numerical regressions. The first attempt expired during P07;
  the clean independent rerun subsequently completed with exit 0. See the
  separate versioned verification receipt for commands and results.

The recorded controlled-host composite throughput gate and read/repack
remeasurement were independently passed in the incoming corrective evidence;
this task did not rerun prepared-host benchmarks or substitute development
numbers for their acceptance criterion. No new corpus audio, one-hour hardware
run, or analysis-v1 spectral measurement was performed here.

## Changed files and continuation

- `Makefile.am`, regenerated `Makefile.in`: distribution metadata for the
  reviewer collector, tests, criteria and handoff.
- `src/pcmdsd.c`, `src/pcmdsd.h`: diagnostic lower-bound semantics only.
- `tests/dsd/soak_p10.py`: accept duration-aligned release-length sequences;
  **do not rewrite the committed one-hour historic result**.
- `tests/dsd/test_p10.py`: CLI diagnostic regression.
- `tests/dsd/reference/p10_ratification_criteria.json`: acceptance standard.
- `tests/dsd/ratify_p10_gates.py`, `qualify_p10_ratification.py`,
  `test_p10_ratification.py`: source-independent receipt auditor, versioned
  collector and adversarial tests.
- `tests/dsd/results/P10_ratification_2026-10-10/`: separately versioned
  adjudication, verification manifest and delivery SHA checksums.
- `docs/dsd/handoffs/P10_RATIFICATION.md`, `P10_RATIFICATION_WORKLOG.md`:
  decision record and interruption-resumption checkpoint.

Existing P00-P10 evidence is preserved bit-for-bit. **Do not alter
`tests/dsd/test_p10.c`**: the original hardware artifacts hash that source
byte-for-byte. No current P10 profile is promoted. Next work needed for a full
P10 closeout: externally sourced PCM material, actual candidate graphs and
independent per-rate measurements meeting the manifest; review and issue a new
versioned disposition, with release activation still reserved for P15. A new
P11 mastering kernel family must satisfy its own 3600-second hardware gate.

The bundle contains only the source continuation tree and retained evidence;
no built binaries or redistributed commercial recordings. A new
`DELIVERY_SHA256SUMS.txt` inventories the source tree. Older historical
checksum files remain unchanged and reflect earlier snapshots, not the newly
ratified tree.

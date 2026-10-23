**CORRECTIVE R2 NOTICE (2026-10-23):** The independent adversarial audit
identified failures of ordinary full-scale native nonlinear inputs in 15 of
the historical 23 research-improvement candidates. The R1 shortlist and
its recommendation to advance unscaled SDM-8 and CLANS-8 are withdrawn.
This R1 report and its receipts are preserved for historical verification.
Read `R2_REPORT_2026-10-23.md`, `R2_CHECKPOINT.json`, and run
`verify_r2.py` for the corrected stability-gated evidence. Production
CLANS-7 and all frozen authority remain unchanged.

# DSD1024 NTF independent source-bound research — 2026-10-23

**Status: EXPLORATORY. No production change, coefficient promotion, capability enablement, or gate relaxation.**

This addition answers `BRIEF_2026-10-23.md` without modifying any of the
3,056 files in the source archive `sox_dsd-a5e77be5d-working-set.tar.zst`.
All 55 experimental native profiles are generated **only in a disposable
independent clone**, never in this source bundle. No new profile is reachable
through a production CLI or the production mastering encoder.

## Index

- `REPORT_2026-10-23.md`: observations, rankings, confidence, decisions, limitations.
- `model.py`: source-bound exact binary64 historical 10-family + DSD512 seed design bank;
  55 designs including unchanged frozen CLANS-7 incumbent. Preserves resonator
  coefficients as exact hexadecimal binary64 words.
- `designs.json`: deterministic design catalogue; do **not** edit after generating receipts.
- `study.py`: isolated scratch creation, non-production C registry instrumentation,
  reproducible stimulus synthesis, native bitstream screening, sample-aligned
  spectral reconstruction, and evidence-bound comparison. Atomic receipt publication
  refuses conflicting resumes.
- `requalify.py`: separate isolated **P19** host requalification from an explicit
  positive pre-freeze placeholder, with guarded recompile, original frozen maxima
  and bound comparison, `verify`, and all 36 holdout judgments. This rebuilds
  **the incumbent only**, not the 54 experimental candidates.
- `verify_evidence.py`: independently validates the supplied study receipts and
  hash relationships without claiming absent bitstreams or missing gates.
- `test_study.py`: 12 negative/positive source, guard, transfer, and failure checks.
- `evidence/`: input hashes, experimental registry, 220 native short-screen
  receipts, 55 primary native render receipts and spectra, 20 finalist renders,
  10 secondary spectra, 4 alternative FIR spectra, comparison record,
  and 17+36 independent P19 requalification receipts and logs.
- `provenance/`: original source file inclusion and omission lists, origin checksums.
- `CHECKPOINT.json` and `REPLAY.md`: durable current status and exact replay steps.
- `STUDY_SHA256SUMS.txt`: checksums for every added study file, except itself.

## Quick offline validation

Run from this directory (requires Python 3 and NumPy/SciPy):

```sh
sha256sum -c STUDY_SHA256SUMS.txt
python3 -B -m unittest -v test_study.py
python3 -B verify_evidence.py
```

For the unmodified **incumbent**, the supplied full host requalification
was run separately in a disposable clone and its independent outputs are
included under `evidence/requalification/`.

**Research ranking is not qualification.** Experimental designs were screened
through a private unbounded native binary. All 55 passed four short input
cases and all five finalists completed a 32-second continuous composite.
Those are meaningful nonlinear diagnostics but cannot replace the original
P19 3,600-second soak, candidate-specific frozen guards, verified holds,
regression tests, or independent audio/media qualification.

## Reproduce native work in a disposable tree

All commands below are from this new study directory inside a complete
checkout of **this same working set**. Use an empty external scratch path.
Do not point these operations at the source tree.

```sh
mkdir -p /tmp/dsd1024-study
python3 -B study.py prepare --checkout /tmp/dsd1024-study/native
python3 -B study.py instrument --checkout /tmp/dsd1024-study/native \
  --registry /tmp/dsd1024-study/experimental-registry.json
(
 cd /tmp/dsd1024-study/native
 autoreconf -fi
 ./configure --disable-shared
 make -j4
 make -C test dsd_test_p10
 ./test/dsd_test_p10 --unit
)
python3 -B study.py stimuli --directory /tmp/dsd1024-study/input --stress32
python3 -B study.py render --checkout /tmp/dsd1024-study/native \
  --registry /tmp/dsd1024-study/experimental-registry.json \
  --binary /tmp/dsd1024-study/native/test/dsd_test_p10 \
  --input /tmp/dsd1024-study/input/hot-997.f64le \
  --receipts /tmp/dsd1024-study/receipts/hot-997 \
  --packed /tmp/dsd1024-study/packed/hot-997 --jobs 4
```

Repeat the render command with `noise-safe`, `dc-step`, `silence`, and
`primary` inputs (corresponding new output directories). Experimental
receipt hashes will bind both the exact native binary and coefficient
registry, preventing accidental conflation of different executables.
Then, for example:

```sh
python3 -B study.py spectrum \
  --packed /tmp/dsd1024-study/packed/primary/sdm-8.packed \
  --receipt /tmp/dsd1024-study/receipts/primary/sdm-8.json \
  --output /tmp/dsd1024-study/spectra/sdm-8.json
```

To repeat the study's full evidence, use the input/candidate map in
`REPLAY.md`. You can omit the large packed outputs **after** retaining
render receipts; subsequent reruns reproduce and hash-verify the exact
bitstream before opening the previous record. No recorded evidence is
silently rewritten, including on timeout or stale/mismatched source.

## Host requalification of the existing P19 CLANS-7 incumbent

Separate scratch copy; no historical receipts or guards in the distributed
source are erased or rewritten:

```sh
python3 -B requalify.py prepare --scratch /tmp/dsd1024-p19-private
python3 -B requalify.py run --scratch /tmp/dsd1024-p19-private \
  --evidence-dir /tmp/dsd1024-p19-outputs --jobs 3
```

Requalification is **not** a qualifier for a new SDM-8 candidate. New
candidate-specific guard definition, training, freezing, `verify`, 36-case
holdout, sustained stress and cross-ISA work remain separate release gates.

## Required caveats

- This archive is a **working set**, not the entire repository. The supplied
  `OMITTED_FILES.txt` enumerates 49,964 absent files plus 1,351 `.npz`
  artifacts; P15 historic proof validators cannot be claimed passing here.
- The P20 residual checksum manifest supplied with the source archive has
  exactly one pre-existing mismatch for
  `tests/dsd/results/P20_OPERATOR_QUALIFICATION_2026-10-22/README.md`:
  manifest expects `4e73674f...`, actual archived README is `5f5d9a8e...`.
  This is **not** fixed by editing the evidence or its manifest. All entries
  in the separate `P20_BUNDLE_SHA256SUMS.txt` checked successfully.
- All measurements use 176,400-Hz binary64 input; the 61-tap upstream
  prefilter makes the 100–150-kHz region noise-only. Reconstructed bands
  do not establish fidelity for unsupported source bandwidth or real media.
- The study does not admit self-generated DSD1024 media as independent
  DSD1024 **read** qualification. An internally generated write/read loop
  is useful functional testing, but external independently generated
  media/evidence remains outstanding.
- Frozen continuum-extrema waiver retained without modification.

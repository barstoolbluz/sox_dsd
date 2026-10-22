# P17 qualification: reproducibility, resume and evidence manifest

This packet is a **complete, source-based qualification handoff**, not a production release or a detached collection of numeric claims. The source snapshot was provided as `sox_dsd-qual-2bda0491-working-set.tar.zst` (SHA-256 `8a0f2ccbbdb3534b101880c5eebc25c5690259347513933ac67a49b8cc6ea377`) with 2,086 files; 49,662 otherwise tracked paths and 1,351 `.npz` are intentionally omitted. The incoming `.git` directory was absent; the `2bda0491` revision is source metadata, not an independently authenticated Git HEAD. Input inclusion/omission lists and original SHA-256 are retained under `input-manifests/` in the outer bundle.

**Important execution interruption:** An initial container restarted during the first holdout. All unbundled state was lost. A recoverable source/test checkpoint `sox_dsd-p17-qualification-checkpoint-2026-10-21.tar.zst` was then created; the source, guard training (all 34 cases), holdout, fixtures and integration tests have since been reproduced from that checkpoint and the original upload. Earlier incomplete log entries must not be treated as completed evidence. The original P10-method training executable is archived *byte-for-byte* under `tests/dsd/results/P17_qualification_2026-10-21/guard-tools/dsd_test_p10_training`; its SHA-256 is `0fea717b312cde26005e0fb580cb07cc7b247fbba4fc802b895edc7e315b9d3b` and matches the frozen training derivation. The fixed post-guard executable is separately archived as `.../guard-tools/dsd_test_p10` for the 72-case holdout. These are Linux build-test artifacts, not production binaries.

## Current decision

- DSD512 guard derivation: **17/17 admitted; 36/36 holdout accounted for, 34 pass and two observed 0-dBFS fullscale separately**. Encoder still **unqualified**: prepared-host sustained soak, independent real material and complete writer interoperability are not proven.
- DSD1024 guard derivation: **15/17 admitted; two DC training cases fail nonfinite**. Holdout: **three failures** (positive/negative DC state-bound and deliberate-overload wrong rejection class), plus two separately handled fullscale observations. Encoder **blocked** for release, irrespective of source-specific safe ceilings.
- Four private reconstruction profiles: **84 synthetic DSF fixtures and four multi-megabyte streaming fixtures PASS; existing sampled/finite P17 oracles PASS**; **licensed whole-file and independent PCM comparison UNRUN**. No DSD1024 independently sourced media available.
- Four one-second soak/replay tests (DSD512/DSD1024 × original-v1/nominal-v2): **PASS_SHORT_SMOKE_ONLY**, neither one-hour nor prepared-host evidence.
- New candidate certificate registry: six separately versioned SHA-256 records; **all `qualified=false`, all capability bits disabled**. P18 remains `P18_COMPLETE_FAIL_CLOSED` with 12 explicitly disabled endpoint rows. The P10 low-rate certificate unchanged.

### Supplemental short stress and clean-room replay

Two further **three-second** exact-envelope DSD512 positive/negative DC cases both completed normally with guarded state checks; their input/output SHA-256 and per-coordinate maxima are in `guards/extended-dc/`. This observation is not part of the frozen holdout and cannot substitute for a continuous one-hour or real-program test.

The source was subsequently extracted from the independently checksummed package into a **new empty build directory**. `autoreconf`, `configure`, complete rebuild, `make check`, P17 unit/encode/matrix, P18 native/CLI refusal, all 84 synthetic fixtures, all four multi-megabyte streaming fixtures, unchanged P10 guard verification, candidate certificate generator, profile generator and P18 manifest seal checks **all exited 0**. The replay's raw logs and individual exit codes are retained under `build/clean-archive-replay/`. This fresh replay did not import objects from the development workspace.

## Rebuild and verify

From the extracted `sox_dsd/` source root on Linux with C build dependencies, Python 3 and NumPy installed:

```sh
autoreconf -fi
./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'
make -j6
make -C test dsd_test_p10 dsd_test_p17 dsd_test_p18 dsd_test_p17_dsf
make check
test/dsd_test_p17 unit
test/dsd_test_p17 encode
test/dsd_test_p17 matrix
test/dsd_test_p10 --unit
test/dsd_test_p18
python3 tests/dsd/test_p18.py --sox src/sox --results /tmp/p17-p18-recheck
python3 tests/dsd/generate_p17_profiles.py --check
python3 tests/dsd/p17_qualify_guards.py verify
python3 tests/dsd/test_p17_dsf_probe.py --results /tmp/p17-probe-recheck
python3 tests/dsd/test_p17_long_dsf_stream.py --results /tmp/p17-stream-recheck
python3 tests/dsd/generate_p17_qualification_certificates.py --check
python3 tests/dsd/test_p17_qualification_registry.py
python3 tests/dsd/seal_p18_manifest.py --check
```

The `--results /tmp` examples avoid rewriting the source-bound initial evidence. `p17_qualify_guards.py train` is intentionally refused once `p17_guards.json` is frozen; **do not rerun training to get a more favorable bound**. To re-adjudicate the *same* frozen holdout receipts, run:

```sh
python3 tests/dsd/p17_qualify_guards.py holdout \
  --unit tests/dsd/results/P17_qualification_2026-10-21/guard-tools/dsd_test_p10
```

**Expected exit: `1`**, not `0`: the DSD1024 failures are preserved, while the rate-specific DSD512 result is `PASS`. An exit of 1 with the recorded `HOLDOUT FAIL 72` is a *correct test outcome*, not a failed packaging operation. Check its source-bound `rate_results` and `case_receipt_sha256` to distinguish execution integrity from qualification acceptance.

## Results and source/checksum locations

The qualification receipts, test logs, command exits and original frozen case records are at `tests/dsd/results/P17_qualification_2026-10-21/`. The material gates remain absent by design; `media/commercial-decode-evidence.json` records zero supplied licensed tracks and explicit UNRUN qualification. The reproducible candidate registry and low-rate/guard checks are `tests/dsd/reference/p17_qualification_certificates.json`, `tests/dsd/reference/p17_guards.json`, `src/dsd_p17_certificates.h` and `src/pcmdsd_guards.h`.

For full licensed-media decoder assessment and prepared-host one-hour input/SDM assessment, follow `P17_QUALIFICATION_2026-10-21.md`. Never modify historical P00/P15 source admission tools or the permanent spectral-proof waiver. No short synthetic test is permission to open a high-rate read or writer capability.

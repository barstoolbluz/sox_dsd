# P17 recorded continuation checkpoint (2026-10-21)

Input: sox_dsd-p17-998b08dc-working-set.tar.zst; SHA256 c1a04671deeec895e53529ec76c506ad7784383ab80568532599970ffb3ef151; working set not entire historical tree. No Git metadata in upload. Baseline revision declared 998b08dc.

Scope: DSD512/1024 experimental private mastering and wideband decimation, explicit private SDM candidates; no writer/DoP enablement; source original 64/128/256 profiles remain qualified by accepted prior operator records. P15's two standing proof obligations remain OPEN.

Current evidence at this checkpoint:
- `make check`: exit 0, `build/make-check.exit` and `build/make-check.log`.
- `make check-rename`: exit 0, `build/make-check-rename.exit`.
- `make check-dsd DSD_PHASE=P17`: exit 0, `build/make-check-dsd-after-testfix.exit`, `build/make-check-dsd-after-testfix.log` (includes P16 219/219, P17 numerical development).
- `python3 tests/dsd/run.py --phase P17 --results tests/dsd/results/P17`: exit 0, 41 PASS, 0 FAIL in `run.json` and `build/run-p17-final.exit`.
- `python3 tests/dsd/measure.py --phase P17 --results tests/dsd/results/P17/numeric`: exit 0; 11 PASS, 0 FAIL, high-rate qualification UNQUALIFIED, `numeric/measure.json`.
- Private P17 matrix: 8,640 PASS, 406,080 assertions, `build/p17-matrix.log`.
- Independent spectral sampled grid, finite-frame FIR and SDM synthetic diagnostics: development PASS, `numeric-p17/qualification.json`.
- P16 inherited physical reader/packed matrix: 4,695,450 blocks/183,833,677 assertions; 6480 cases/1,480,320 assertions; `build/p16-*.log`.
- Generic source tests P05 plan corrected for explicit high-rate experimental edge while capability bits remain zero, and P06 private decode corrected for P17; P10 historical qualification assertion updated to current P15 qualified state. Their direct gates pass.

Do not confuse earlier interrupted attempts (`build/make-check-dsd.log`, `build/make-check-dsd-final.log`, `build/run-p17.log`, `build/measure-p17.log`) or the earlier real P05 old-assumption failure (`build/make-check-dsd-complete.log`) with the final successful receipts named above. All remain as raw debugging evidence.

Completed after initial checkpoint: paired 0.08-second private high-rate benchmark (12 decoded configurations / 2 encoder candidates, exit 0, `build/bench-p17-refined.exit`), inherited 36/36 development benchmarks (exit 0, `build/bench-p17-last.exit`), independent numerical final replay (exit 0, `build/numeric-p17-final.exit`), final P17 handoff and source/evidence hash manifests. Packaging/reassembly verification is tracked in the outer multipart delivery README, not a numerical gate. Missing independent DSD512/1024 media, physical device interoperability, controlled Intel/AMD hardware, long holdouts, continuous-frequency interval proof; no versioned full-rate release certificate is claimed.

Final update (2026-10-21): the formerly pending benchmarking, handoff and source hashing have completed.
- `./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'`: exit 0, `build/configure-final.exit`, `build/configure-final.log`.
- `make -j4`: exit 0, `build/make-final.exit`, `build/make-final.log`.
- `python3 tests/dsd/bench.py --phase P17 --results tests/dsd/results/P17/bench`: exit 0, `build/bench-p17-last.exit`, `build/bench-p17-last.log`. **36/36** inherited benchmarks completed. The P17 internal paired benchmark, at `bench/highrate-internal/paired.json`, reports all twelve private decode pairs and both encoder candidates PASS_DEVELOPMENT_TESTS_UNQUALIFIED; latest paired run uses 0.08 source-audio seconds by default (not a physical sustained-throughput claim). Earlier full benchmark exit was also 0.
- The definitive phase handoff is `docs/dsd/handoffs/P17.md` and the source-only manifest is `P17_SOURCE_SHA256SUMS.txt` (verify with `sha256sum -c P17_SOURCE_SHA256SUMS.txt`). The distributed tree is reconstructed from the unchanged P17 input working set plus exactly the changed and new source, handoff and P17 receipt files.
- Outstanding external/high-rate certification gates remain unrun. The P17 rate-specific qualification decision is **UNQUALIFIED**, with 512/1024 writer/DoP output still disabled.

Resume procedure: extract/reassemble the delivered archive, read docs/dsd/handoffs/P17.md, verify P17_SOURCE_SHA256SUMS.txt, run autoreconf/configure/make, then `make check`, `make check-rename`, `make check-dsd DSD_PHASE=P17`, `python3 tests/dsd/measure.py --phase P17 --results tests/dsd/results/P17/numeric` and `python3 tests/dsd/bench.py --phase P17 --results tests/dsd/results/P17/bench`; avoid rerunning historic P15 closeout against intentionally omitted evidence. New physical corpus/proof work is needed before any production certification.

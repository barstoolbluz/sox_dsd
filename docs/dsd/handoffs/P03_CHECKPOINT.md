# P03 continuation checkpoint (completed 2026-10-08)

This is a self-contained recovery marker for the authoritative P03 continuation
tree. It supersedes the earlier in-progress checkpoint notes; the complete
engineering record and unresolved qualification items are in `P03.md`.

## Source and state

- Input archive: `sox_ng-P03-cce14f44.tar.gz`, SHA-256
  `2c3dadba95ec966baca30ba6a72e6e4f6415867291e2e0b0e1ff424a1ed0d6c1`.
- Governing source: `docs/dsd/sows/P03.md`, `DSD_DESIGN.md` section 4.3,
  `IMPLEMENTATION_PLAN.md` P03, P00-P02 handoffs and the attached P03 brief.
- The complete source, test inputs/generators, contract inventory, final
  reports and raw P03 evidence are in this tree. No `.git` is required.
- Frozen earlier checkpoint archive (created before the final test pass):
  `sox_ng-P03-implementation-checkpoint.tar.gz`, SHA-256
  `4369597f022e79309c98e28bcf1e94d5af3941362d160dafc177309636f66486`.
  It is superseded by the current complete source archive.

## Verified implementation state

- P03 phase runner: **35 PASS / 1 P04 XFAIL / 0 FAIL / 0 SKIP**.
- P03 seek-contract matrix: **50 PASS / 0 FAIL**, including independent SMP
  and PRC fixtures and GSM WAV unsupported-seek behavior.
- `make check` and `make check-dsd`: exit 0; generic test classes are 73 OK,
  8 preexisting VOID. Numerical 5/5; development benchmark 36/36 cases.
- Paired P02-to-P03 DSD read/repack smoke: 120 commands, zero errors and
  matching repacked output checksums. The unprepared host's 27.1% repeatability
  spread exceeds the 2% admissibility limit, so performance is **inconclusive**.
- FLAC, Vorbis, Opus and WavPack dev dependencies unavailable: executable
  seek coverage for those codecs is **unrun**, not passed.

## Recovery / handoff

Extract the complete archive; from its `sox_ng/` directory run:

```sh
sha256sum -c tests/dsd/results/P00/P00_SHA256SUMS.txt
autoreconf -fi
./configure --disable-shared --without-libltdl CFLAGS='-O2 -g'
make -j4
make check
make check-dsd
python3 tests/dsd/run.py --phase P03 --results tests/dsd/results/P03
```

Verify the cumulative SHA-256 manifest **before** running commands that
regenerate P03 evidence; the manifest intentionally inventories the delivered
result files as well as source. Re-running tests changes those result files.
No code changes remain outstanding for P03's functional gate. Comparative
performance qualification and optional-codec execution are explicitly open;
read `P03.md` rather than inferring success. The next permitted phase is P04.

## 2026-10-08 P03 corrective continuation

The inherited P03 complete archive (`sox_ng-P03-complete.tar.gz`, SHA-256
`99b38a9bcc5ad066d259d4b6310846f16fd3fa907b5f05bbd94ed18b410e696a`)
was audited and two bounded fixes were requested:

1. `dff_read()` must return zero for a declared empty DSD payload, even if a
   following MANF metadata chunk has physical bytes available.
2. `opus.c` must invalidate decoded-sample leftovers and EOF only **after**
   a successful `op_pcm_seek()`.

The source and seek-contract test patches are applied. Rebuild and execution
results, manifest updates and any unrun optional-codec gates are recorded in
`P03.md`. The source archive is authoritative for resuming this correction.

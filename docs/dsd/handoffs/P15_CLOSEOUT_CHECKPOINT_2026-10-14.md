# P15 closeout resumable checkpoint — 2026-10-14

## Input and protected history

The input is `sox_ng-P15-closeout-f5b961c1.tar.gz`, an archive snapshot
of reported revision `f5b961c1` (SHA-256
`6e7739527e3b976ead736db91cebd578c7908a02a00c49f348fabdb22863726c`).
The original source had 5,552 regular files, including the self-excluding
5,551-entry P00 SHA manifest. This closeout leaves preexisting P15 results,
older receipts, certificates and handoffs byte-identical. The original
covering `P15-closeout.md` belongs outside this source tree.

## Finished work and authoritative decision

**BLOCKED: no P15 release, no mastering default/qualification activation,
no new ISA preference and no P16.** Six gates reviewed:

1. Full 54-cell numerical matrix **OPEN**, no archived raw waveform arrays
   and no full composite SRC proof; 54/54 alleged full-binary64 ISA
   identities are contradicted by the preserved per-tier hashes.
2. Physical Intel AVX-512 performance **UNRUN**.
3. Physical older AVX1-only kernel receipt **PASS-SCOPED**.
4. Six-channel DSD256 twofold timing **UNVERIFIED** without individual
   timed samples and proven matched staged control.
5. 15 current-revision hour-long encoder soaks **PARTIAL**, missing 61
   continuation state receipts/run and 15 executable identity receipts.
6. Independent DSD/PCM material **PASS-SCOPED** for software-only
   operation, not physical player/DAC or transport support.

Details and SRC acceptance logic are in
`docs/dsd/handoffs/P15_CLOSEOUT_ADJUDICATION_2026-10-14.md`.
The new independent, fail-closed assessment is
`tests/dsd/p15_closeout_review.py`, with immutable-lookback JSON at
`tests/dsd/results/P15_closeout_adjudication_2026-10-14/review.json`.
The P15 historical `release-manifest.json` was deliberately not rewired.

## Verification and transport

- `autoreconf -fi`, configure, `make -j2`, `make check`: all exit 0 in a
  separate build copy, not in this source tree.
- P15-specific CLI suite: 134 PASS, 0 FAIL, exit 0.
- New closeout audit unit tests: 4 PASS, exit 0, including corruption
  rejection and deterministic exit 2 when qualification is required.
- Complete `make check-dsd`: NOT FINISHED within 180-second execution
  limit; P09 frozen analysis verification was in progress. No complete
  DSD regression claim is made.
- Original matrix independent reviewer: exits 1 on missing raw `.npz`.
  Physical AVX1 admissibility and source-material comparison: PASS-SCOPED.
- The SHA inventory is regenerated only after source and record changes;
  a byte-for-byte historical evidence comparison is written to
  `tests/dsd/results/P15_closeout_adjudication_2026-10-14/preservation.json`.
  Check the inventory independently with `sha256sum -c` from the root.

## Resume instructions

To re-audit existing bytes, run from the extracted `sox_ng/` root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/dsd -p test_p15_closeout_review.py -v
PYTHONDONTWRITEBYTECODE=1 python3 tests/dsd/p15_closeout_review.py --output /tmp/p15-closeout.json --require-qualified
sha256sum -c tests/dsd/results/P00/P00_SHA256SUMS.txt
```

The second command intentionally returns 2 while four gates are open;
the corresponding `release_status` in its output is `BLOCKED`. Inspect
`preservation.json` for independently calculated original archive-byte
comparison. For a complete DSD suite, run `make check-dsd` on a capable
host without the 180-second constraint, and do not equate its success
with the missing hardware, soak or composite SRC qualification.

Next permitted task: collect original missing matrix/soak/benchmark
receipts and physical Intel AVX-512 evidence, or formally amend the
advertised scope before re-adjudicating P15. **Do not proceed to P16.**

# P11 final condition: independent review (2026-10-11)

**Ruling: P11 COMPLETE; P12 AUTHORIZED.** This note is a record of the independent
adjudication of the previously open AVX1-without-AVX2 SDM qualification; it does
not replace the original operator receipts or assert a new QEMU execution.

The input source archive `sox_ng-P11replay-911837ae.tar.gz` matched SHA-256
`5652d3226ea0adfc8f8a94441e5377064957fb12a5deb76e1f3549f56f49527e`.
The replay qualifier's SHA-256 is
`1d126f9dc791a85845afe9799b4308fbd3d97818f7a962a7bbd31511ffb9182b`,
byte-identical to the script created during the immediately prior adjudication.

- `receipt-verification.json` was written by:
  `python3 tests/dsd/verify_p11_replay_receipts.py --output tests/dsd/results/P11_replay_adjudication_2026-10-11/receipt-verification.json`
  (exit 0). The script checks the raw replay JSON, the executable commands,
  return codes, reported ISA traps, actual-unit output markers, six
  emulator/native digest pairs, and all 549 delivered state snapshot digests.
  All checks passed; no extra or missing `.state` files.
- `native-hash-corroboration.json` records the six deterministic PCM/DSD
  conversions re-executed with the independently built P11 binaries retained
  from the previous adjudication. All 3 SDM and 3 FIR output hashes match the
  replay JSON byte-for-byte (exit 0). This reuses the previous independent
  native build; it is **not** a fresh rebuild or a new emulator execution.
- `tests/dsd/results/P11_avx1_no_avx2_replay_2026-10-11/` records 21/21
  operator-executed checks under QEMU 10.0.13 TCG. The AVX probe returns 0,
  both AVX2 and FMA probes return -SIGILL, the SandyBridge unit suite directly
  invokes AVX1 FIR and normal SDM blocks and passes, and six native/emulated
  output pairs match. On Nehalem, the unit suite runs scalar/SSE2 without AVX,
  both unsupported AVX1 forces return exit 2 with family-specific diagnostics,
  and the baseline CLI starts on Nehalem and core2duo.
- All nine groups of one-hour soak receipts now include 61 saved states each
  (60 intermediate and one final); all 549 match the original per-profile
  SHA-256 entries. Each final state has the correct 3,600-second native/input
  counters. Prior independent first-minute replay and performance gates remain
  as recorded in the preceding adjudication.

**Limitations:** QEMU is not installed on the adjudication host, and the
operator-executed emulator binaries and temporary outputs are not delivered.
The check independently verifies the recorded execution artifacts and
reproduces the native output hashes; it does not authenticate the operator's
execution by rerunning QEMU. Section 8.4 explicitly permits an
instruction-validating emulated AVX-only environment for this compatibility
gate. No claim about physical Sandy Bridge/Ivy Bridge performance follows.

**Source change scope:** No production source, runtime dispatch, kernel,
compiler setting, coefficient or numerical acceptance criterion was changed.
Only this evidence/additive read-only receipt audit, the final P11 handoff and
normal source delivery checksum inventory are updated.

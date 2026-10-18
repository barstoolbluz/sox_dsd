# P15 high-rate certification — checkpoint 01

Assignment date: October 18, 2026. Status: work in progress; P15 BLOCKED.

## Verified starting point

- Input: `sox_ng_P15_prover_third_pass_FULL_SOURCE_2026-10-18.tar.gz`.
- SHA-256: `d0bd8a65a149f4267a4d33bb8763aa56faa937ae78009a9796a9b31bcd2e04c4` (verified).
- Frozen extracted baseline: `/workspace/scratch/47ef0cb747fa/baseline/sox_ng`.
- Working copy: `/workspace/scratch/47ef0cb747fa/work/sox_ng`.
- Required numerical package installed at `/workspace/scratch/47ef0cb747fa/deps`: mpmath 1.3.0. Use `PYTHONPATH=/workspace/scratch/47ef0cb747fa/deps:tests/dsd OPENBLAS_NUM_THREADS=1`.
- All inherited 16,711 pinned source/evidence files verified unchanged. The original sorted inventory digest is reproduced: `c9856e34443f81ec390a5c934718deac46ce6bee4aa733cf04e7d01f0f16c059`.
- A broader audit verified 33,487 inherited production, authority, historical-evidence and other pinned files.

## Completed evidence

New evidence root: `tests/dsd/results/P15_high_rate_2026-10-18/`.

The `census/` directory contains the reproducible census for every one of the 11,516 canonical intervals and a 163-job diverse corpus. The original campaign remains 6,835 local PASS / 4,681 OPEN. All 2,151 historical OPEN at 384 kHz are timeouts. DSD256 mastering → 384 kHz has 40 passband +192 native-stop-source jobs, all originally OPEN; this is the preferred complete-cell target.

`baseline_initial/` has unchanged-third-pass receipts for three difficult local PASS results on this host: mastering256 →384 kHz pass 39–40 kHz (16.394 seconds), stop 191–192 kHz (16.780 seconds), and wide256 →384 kHz pass 140–141 kHz (15.305 seconds). Initial processes overlapped; these are exploratory baseline timings, not final matched performance claims. An initial wrong-R mastering256 invocation failed before proving anything and generated no receipt; the correct mastering256 intermediate rate is 176,400 Hz.

`authority/` contains the source-integrity manifest and secondary-obligation review. October 16 physical P/S-matched DSD256 measurements exist: eight reported comparisons exceed 2×; they remain unadjudicated. Source-only transport omits measured audio/binaries needed for full replay. Do not say the physical measurements are absent. Existing v2 records cover 27 scalar /108 forced /48 detailed cells; payload/release qualifications remain separate.

## Current implementation in progress

The proposed improvement uses the exact complementary native-halfband identity. For exact centered `H(x)=1/2+Q(x)`, with symmetric odd-index noncentral taps, `H(x+1/2)=1/2-Q(x)` and the pair magnitude sum is `max(1,2|Q(x)|)`. A directed continuous global enclosure of Q can cap complete unexpanded native subtrees far more tightly than path-count times independent FIR L1 gains.

The numerical-audit worker is implementing `p15_src_halfband_majorant.py`; root has begun integrating guarded subtree caps in `p15_src_branch_bound.py` and adding counters in `p15_src_stagewise_continuum.py`. This intermediate code is NOT yet validated and must not be used to publish new candidate PASS receipts until the module and independent tests are complete.

Guard requirements: each trie node has at most M children; recognized halfband pairs differ by Fin/2 modulo Fin; duplicated complete paths disable the new cap; the original conservative bound remains the fallback. Full source-alias populations, including collisions, remain included.

## Next actions

1. Finish and independently test complementary-halfband global proof and subtree induction.
2. Profile matched baseline/candidate high-rate jobs in separate fresh processes, with source/module path assertions and code hashes.
3. If useful, run all 232 canonical mastering256 →384 kHz intervals plus the diverse selected high-rate corpus. Keep new receipts in new directories, never overwrite historical results.
4. Replay selected proofs and exhaustively verify canonical coverage before claiming any complete cell.
5. Reverify inherited files; package full source, compact patch and evidence, methods, reports and final continuation checkpoint.

No production filters, audio processing, acceptance bands, source pins, default promotion or release policies are to change. Ideal-coefficient local certificates do not discharge arbitrary-input FFT4G execution-roundoff obligations.

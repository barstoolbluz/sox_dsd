# P15 R8 QA and adjudication

Verified against original `cc399928` with the independently distributed R6+R7 overlay. All production source unchanged.

## Tests executed

- Independent production passband derivation: 10 contiguous closed rational segments, [0,100], ... [900,1000] Hz, accepted in exact arithmetic; 9408 complete alias paths on each segment. Source-captured taps and current exact source/method fingerprints validated.
- Independent clean-process verifier reran the ten FIR/composite calculations and reported `status: PASS`, `replayed_intervals: 10`, and full canonical [0,1000] Hz coverage. Separate replay from new process, not producer's acceptance.
- `PYTHONPATH=tests/dsd python3 -m unittest -v test_p15_r8_dyadic`: 4/4 test methods PASS, exercising signed outward rounding, negative numbers, tiny rationals, forbidden types and 4 deliberate certificate mutations. Four schema/state/source-hash/endpoint corruptions refused.
- SHA fingerprints for two R8 mathematical source modules, R6/R7 dependent modules, source-binding files and exact snapshot recorded in the delivered JSON; out-of-version code cannot replay it as certified.

## New exact theorem

If original exact stage enclosure `[l,u]` contains each nonnegative gain and R8 returns `[max(0, floor(l 2^192)/2^192), ceil(u 2^192)/2^192]`, the returned interval contains the original one intersected with `[0,+infinity)`. It follows from ordinary order properties of floor, ceil and nonnegative products. No statistical or approximate numerical premise is involved.

## Complete gate status

- Historical canonical inventory: PASS 11516/11516 recorded.
- Newly independent mathematical proofs across R7 and R8: 88/11516.
- Independent global ideal-operator spectral mathematics: CONDITIONAL, not PASS.
- 11428 other canonical jobs: no new independent mathematical proof in this handoff.
- FFT4G and release-image correspondence: not addressed here.

No claim of complete P15 mathematical closure is made. An alternate valid closure would be a fully justified source-level proof of the *actual historical* interval library, every composite shortcut and exact generating-prover correspondence, which this archive does not claim.

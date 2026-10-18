# Terminal upper saturation and exact coefficient cache identity

## Measured obstruction

Canonical job 596 is DSD64 mastering to 384 kHz, the complete guaranteed-passband interval 19,000–20,000 Hz. The frozen first high-rate candidate returned OPEN with a 60-second budget. A 180-second run passed in 119.957889143 seconds: 15 proof nodes, three exact routing splits, four ordinary subdivisions, and eight certified closed subintervals. The alias bound was 9.998018426093185e-9. This is a proof-method cost obstruction; the completed pass establishes that this interval satisfies the ideal-coefficient obligations.

The instrumented 19,000–19,200 Hz diagnostic located the cost. A coarse segment returned a complete alias upper of 2.6924517427255564e-8 after evaluating all 4,703 unwanted paths. An already fully evaluated single-path upper was 2.5198099933317692e-8. The dominant factor was the first 2x SRC FIR upper, 2.9450001176408057e-8 on its routed high-rate interval. Both 100 Hz children passed, with alias uppers below 9.983e-9 and approximately 230 FIR evaluations each. Refining unrelated leaves on the coarse segment could not improve that already fixed path upper. The finite-difference upper shortcut was not identified as the obstruction; no arithmetic kernel or finite-difference rule was changed.

## Construction and argument

At every population-tree frontier, each entry represents a disjoint selected subset of complete paths and contributes a valid nonnegative upper endpoint. Fully evaluated terminal entries represent their complete path multiplicity and have no remaining refinement inside this call. The existing outward interval `total` contains the sum of all current frontier upper endpoints plus the upper endpoints of terminals already removed from the heap. Removing an old endpoint and adding its replacements uses directed interval arithmetic. The returned `total.b` therefore bounds the complete applicable population at every step.

The change maintains a separate outward interval sum F of the immutable terminal upper endpoints. When `F.a >= limit.b`, the exact sum of these particular fixed upper endpoints is at least the comparison limit. Further refinement of other nonnegative frontier entries cannot make the sum of those fixed endpoints disappear. The algorithm returns the current complete `total.b` immediately, allowing the unchanged caller to subdivide the frequency interval.

F is a sum of UPPER bounds. Its lower endpoint is a lower enclosure for the SUM OF THOSE COMPUTED UPPER ENDPOINTS, not a lower bound on actual transfer amplitudes. This test cannot establish a spectral violation, and no FAIL or VIOLATION status is introduced. All remaining frontier entries stay included in `total` when it returns. The returned bound may be loose; the caller retains its existing OPEN/subdivision behavior until every required inequality is enclosed.

The criterion uses the directed lower endpoint of F and directed upper endpoint of the limit. It does not use binary64 approximate sums, heap priorities, or the potentially cancellation-widened lower endpoint of `total`. Accumulation is monotone in exact mathematics; directed rounding can only delay an otherwise valid early return. A `use_terminal_saturation=False` option retains the previous complete-expansion reference behavior.

## Scope and assumptions

This modification changes allocation of computational effort. It introduces no coefficient identities, no frequency sampling, no alias pruning, no phase cancellation, no acceptance-band changes, and no new transcendental arithmetic. Its validity requires the same valid nonnegative stage upper enclosures and complete selected path population as the existing bound. It inherits the existing outward-rounding assumptions of mpmath interval arithmetic and the exact source/operator bindings. It can return a looser upper earlier; this is safe and is useful when frequency subdivision is necessary. Equality at the internal limit is sufficient to return because returning the full upper is always mathematically valid, independently of the caller's strictness at a boundary.

## Adversarial tests

The dedicated four-test module checks retention of all unevaluated contributions, a loose coarse enclosure followed by successful continuous child enclosures, exact dyadic accumulation immediately below and at the threshold despite large subtraction cancellation in `total`, and accumulation of multiple individually subthreshold terminal upper endpoints. Tests compare the disabled-optimization reference and independent exact transfer bounds where appropriate.

The real job 596 v2a run additionally preserved exactly the same 15 nodes, four subdivisions, eight safe subintervals, wanted lower, total upper, and alias upper as the 180-second first-candidate pass. It passed at 60 seconds in 57.588118955 seconds, with FIR evaluations reduced from 39,576 to 2,624 and population frontier expansions from 77,990 to 3,466. Four terminal saturation returns removed the unnecessary coarse-population work. These are measurements of this case, not a claim of universal full-prover speedup.

## Exact-word cache correction

Independent review found that the halfband module's tuple-of-floats cache key conflated +0.0 and -0.0 even though coefficient provenance hashes distinguish their hexadecimal words. Python also regards some non-float numbers as equal to floats, so a cache hit could bypass the exact binary64 type precondition. The saved pre-fix reproducer establishes both cases.

The corrected public entry validates coefficient indices, exact float types, finiteness, uniqueness, center, and symmetry before any cache lookup. The normalized key is the sorted tuple of `(integer index, coefficient.hex())` pairs plus interval precision. Cache misses reconstruct floats with `float.fromhex` and replay the same complete normalized-frequency proof. Signed-zero inputs retain distinct metadata; mathematically identical tap order permutations share a proof; equal-valued non-float inputs are refused even after a float proof is cached. Two additional adversarial tests cover these requirements.

The actual 57-tap native halfband contains 28 zero coefficients. Current captured source stages consistently used the same exact words and types, so the defect did not alter their polynomial or previously measured bounds. The fix restores the promised exact-word cache identity for adversarial inputs. It changes no captured source coefficient and invalidates no mathematical source binding, but it does change proof-code identity; v2a and v2b receipts therefore retain separate code hashes and snapshots.

## Reproduction and evidence

`FOCUSED_TESTS.log` records all 41 focused tests passing. `CACHE_IDENTITY_REPRODUCER_PRE_FIX.json` records the original defect and source zero count. `CANDIDATE2_V2B.patch`, `SOURCE_IDENTITIES.json`, and `files/` retain exact integration changes relative to the frozen first high-rate candidate. The adjacent `terminal_saturation_candidate/` directory preserves the earlier v2a receipt and its exact branch, stagewise, and halfband module files. The separately retained import-map snapshot is authoritative for replaying v2b receipts.

All spectral results concern the local stationary ideal-coefficient operator. They do not discharge arbitrary-input FFT4G execution-roundoff proof, physical release adjudication, or P15 release authorization.

## Final frozen v2b replay

The exact-word cache correction passed the same 41-test focused suite. The final v2b job 596 replay passed in 54.872388825 wall seconds and 54.845857086 CPU seconds, with 212,640 KiB peak RSS. It used the same 2,624 FIR evaluations, 624 inexpensive difference majorants, 3,466 frontier expansions, and four terminal early returns as v2a. `JOB596_COMPARISON.json` mechanically checks that all three passes have identical source binding, snapshot identity, final numerical enclosures, node counts, routing splits, ordinary subdivisions, and numbers of certified subintervals. The 54.87 versus 57.59 second difference is single-run timing variability and is not credited to the cache fix.

The final experiment used the unchanged `p15_high_rate_experiment.py` harness, whose hash is retained in the receipt, with these arguments:

```text
--source-root /workspace/scratch/47ef0cb747fa/candidate2/sox_ng
--job-index 596
--label terminal_saturation_candidate_v2b
--output <new immutable receipt directory>
--seconds 60 --max-nodes 128 --max-paths 20000 --cpu 7
```

The process was wrapped with GNU `timeout --kill-after=5s 85s`, with `OPENBLAS_NUM_THREADS=1`. Python's repeated SIGALRM deadline is not claimed to be a strict external termination guarantee. The proof import map was checked after completion and all 15 named files were copied into `../../reference_high_rate_v2_code/` with `IDENTITY.json`; that immutable snapshot records the receipt hash and the actual isolated source root. Work-source proof modules were never modified by this experiment.

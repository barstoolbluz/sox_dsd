# Independent review: exact halfband alias-pair subtree caps

Date: 2026-10-18. Reviewed modules: `p15_src_halfband_majorant.py` and the
`_complete_subtree_caps`/`bound_population` integration in
`p15_src_branch_bound.py`. Production FIR taps and stage mappings are unchanged.

**Finding:** the complete-subtree cap is mathematically valid with the
implemented exact coefficient and trie checks. No unsound phase cancellation,
alias removal, or weakening of the spectral limits was found.

## Exact stage identity

For the admitted stage, L=1, M=2, Fout=Fin/2; h[0]=1/2 exactly. Every other
nonzero coefficient has an odd integer index, and h[−k]=h[k] exactly. Therefore
the centered frequency response is real:

H(x) = 1/2 + Q(x), where Q(x) = 2 sum over positive odd k of h[k] cos(2πkx).

Odd k gives Q(x+1/2)=−Q(x). Thus the two branch magnitudes obey the exact identity

|H(x)| + |H(x+1/2)| = max(1, 2|Q(x)|).

This is a bound on the sum of two nonnegative magnitudes. It makes no claim
that physical paths cancel coherently. It does not need a relative phase
origin beyond the exact admitted centered polynomial representation.

Q is even and antiperiodic under a half-cycle shift. Its absolute value is
half-cycle periodic and symmetric around one quarter cycle. A closed cover
of [0,1/4] therefore suffices for a global bound over every real frequency.
The implementation obtains this cover with the existing directed Taylor
evaluator. It returns no bound unless every pending interval is discharged
within the node budget. A changed central coefficient, a nonzero even tap,
asymmetry, a wrong rate relation, duplicates, or inadequate proof budget cannot
receive the shortcut. The target 0.50000001 is an internal cost guard; no
spectral acceptance threshold is derived from accepting that target.

## Subtree induction

Let a_r,b(f) be the nonnegative magnitude of immediate branch b at stage r.
Let g_r uniformly bound the sum over all allowed immediate children, at every
frequency. If every child's upstream subtree is bounded by the product of
the remaining g values, then

sum_b a_r,b(f) subtree_b(f) <= g_r product_{s>r} g_s.

The leaf bound is one. This proves the product cap by induction. For an
unrecognized stage, at most M children each have magnitude at most exact
L1/L, giving g=M·L1/L. Distinct branch frequencies are not needed for that
fallback: repeated frequencies still contribute at most one L1/L per child.

For a recognized halfband node, one child is bounded by its full pair. Two
children are eligible only if their exact shifts differ by Fin/2 modulo Fin.
That test establishes the required complementary pair. The implementation
checks every node, including deep subtrees, rather than only the root.

The selected population may omit branches because all terms are nonnegative.
It must not duplicate a complete path: that would make a terminal leaf's
contribution exceed the assumed leaf factor one. The implemented
`node.count == 1` leaf check rejects this case and falls back to the previous
count-times-L1 bound. Excessive branching similarly disables the shortcut.
Different full paths with the same native-frequency label are retained.

At a ready frontier node, the stored prefix already bounds every evaluated
factor. At an unevaluated node, one additional per-stage L1/L factor precedes
the remaining subtree cap. This agrees with the implemented depth indexing.
Taking the smaller of two valid nonnegative upper bounds is valid. A later
refinement can increase the frontier total because independent child bounds
lose correlations; correctness does not require monotonic tightening.

## Independent adversarial tests

`test_p15_high_rate_population.py` uses direct all-tap complex interval sums
and the separate point branch enumerator. It does not reuse the new halfband
identity to compute its numerical reference. Eight tests cover:

1. A complete two-stage, four-path population and a selected subset.
2. Repeated identical full paths, preserving their multiplicity.
3. Two noncomplementary halfband siblings whose actual sum exceeds 1.4,
   so an erroneous unit cap would be detected.
4. A valid root with an invalid deep pair, plus a node exceeding M children.
5. An asymmetric non-halfband stage using the general M·L1/L fallback.
6. Complete expansion against explicit continuous complex enclosures, and
   collided native labels on distinct paths.
7. A rational 3/2 stage composed with a halfband, its exact crossover at 6 Hz,
   both adjoining closed intervals, and the exact boundary point.
8. All 64 reverse paths of the source-pinned DSD256 native cascade.

Result: **8 tests passed in 3.352 seconds**. Command:

```sh
PYTHONPATH=tests/dsd OPENBLAS_NUM_THREADS=1 \
python -m unittest -v test_p15_high_rate_population
```

This environment additionally used the mpmath dependency directory at
`/workspace/scratch/47ef0cb747fa/deps` and ran with `nice -n 15`.
The exact test output is retained in `POPULATION_TESTS.txt`.

The mathematical justification is the exact pair identity, directed complete
cover, and subtree induction. The tests independently challenge indexing,
rounding, multiplicity, and fallbacks; sampled assertions are not substituted
for any continuous-frequency proof. Full local certificates still require
the source-bound complete path enumeration and their applicable inequalities.
These changes do not supply arbitrary-input FFT4G execution-roundoff bounds.

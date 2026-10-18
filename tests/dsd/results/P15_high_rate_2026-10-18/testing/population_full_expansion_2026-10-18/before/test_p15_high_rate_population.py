#!/usr/bin/env python3
"""Independent adversarial tests of complete-subtree alias caps.

The mathematical argument is an induction over complete branch populations.
These tests independently enumerate small populations, directly enclose all
complex tap sums, and attack admission with repeated/noncomplementary paths.
They do not turn point tests into a continuous-frequency spectral certificate.
"""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mpmath import iv

from p15_src_branch_bound import bound_population
from p15_src_continuum_bounds import scalar
from p15_src_halfband_majorant import halfband_alias_sum_upper
from p15_src_stagewise_alias_proof import FIRStage, branches, make_native_stages
from p15_src_stagewise_continuum import AliasPath, BranchBoundary, complete_paths


def halfband(clock):
    return FIRStage("synthetic-halfband", clock, Fraction(clock, 2), 1, 2,
                    ((-1, 0.125), (0, 0.5), (1, 0.125)))


def independent_paths(stages, frequency):
    """Use the separate point branch enumerator, not complete_paths' tree."""
    frequency = Fraction(frequency)
    states = [(frequency, ())]
    for stage in reversed(stages):
        states = [(upstream, terms + ((stage, high - frequency),))
                  for previous, terms in states
                  for high, upstream in branches(stage, previous)]
    return tuple(AliasPath(upstream - frequency, terms, False)
                 for upstream, terms in states)


def direct_complex_magnitude(stage, lo, hi):
    """All taps, retained time origin, directed interval complex arithmetic."""
    rate = stage.L * stage.input_hz
    frequency = iv.mpf([scalar(Fraction(lo) / rate).a,
                        scalar(Fraction(hi) / rate).b])
    real, imaginary = iv.mpf(0), iv.mpf(0)
    for index, coefficient in stage.taps:
        angle = 2 * iv.pi * frequency * index
        real += iv.mpf(coefficient) * iv.cos(angle)
        imaginary += iv.mpf(coefficient) * iv.sin(angle)
    return iv.sqrt(real**2 + imaginary**2) / stage.L


def explicit_population(paths, lo, hi):
    """Brute product/sum of independent complex enclosures, no subtree cap."""
    cache = {}
    total = iv.mpf(0)
    for path in paths:
        product = iv.mpf(1)
        for stage, shift in path.terms:
            key = stage, shift
            if key not in cache:
                cache[key] = direct_complex_magnitude(stage, lo + shift, hi + shift)
            product *= cache[key]
        total += product
    return total


def population_bound(paths, lo, hi, *, cap=True, limit="1000000", include=lambda path: True):
    stats = {}
    def evaluate(term, left, right):
        stage, shift = term
        return direct_complex_magnitude(stage, left + shift, right + shift).b
    upper, evaluations = bound_population(paths, lo, hi, include=include,
        limit=limit, evaluate=evaluate, stats=stats, use_subtree_caps=cap)
    return upper, evaluations, stats


class HighRatePopulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        iv.dps = 75

    def test_complete_and_selected_two_level_populations(self):
        paths = independent_paths((halfband(96), halfband(48)), Fraction(1, 2))
        self.assertEqual(len(paths), 4)
        lo, hi = Fraction(0), Fraction(1)
        upper, calls, stats = population_bound(paths, lo, hi)
        old, old_calls, _ = population_bound(paths, lo, hi, cap=False)
        self.assertEqual(upper, iv.mpf(1))
        self.assertEqual(old, iv.mpf("2.25"))
        self.assertEqual((calls, old_calls), (0, 0))
        self.assertGreater(stats["subtree_caps_used"], 0)
        # Both complete pair sums are exactly one in this synthetic example.
        # Direct complex point enclosures must overlap that analytic upper.
        for frequency in (lo, Fraction(1, 7), Fraction(1, 2), hi):
            self.assertTrue(bool(explicit_population(paths, frequency, frequency).a <= upper))
        selected = paths[::2]
        subset, _, _ = population_bound(paths, lo, hi, include=lambda path: path in selected)
        for frequency in (lo, Fraction(2, 7), hi):
            self.assertTrue(bool(explicit_population(selected, frequency, frequency).a <= subset))

    def test_repeated_complete_paths_retain_every_contribution(self):
        paths = independent_paths((halfband(96), halfband(48)), Fraction(1, 2))
        for population in (paths + (paths[0],), (paths[0],) * 4):
            upper, calls, stats = population_bound(population, Fraction(0), Fraction(1))
            old, old_calls, _ = population_bound(population, Fraction(0), Fraction(1), cap=False)
            self.assertEqual(upper, old)
            self.assertEqual(calls, old_calls)
            self.assertEqual(stats["subtree_caps_used"], 0)
            self.assertTrue(bool(explicit_population(population, Fraction(0), Fraction(0)).a <= upper))

    def test_noncomplementary_halfband_siblings_cannot_use_pair_cap(self):
        stage = halfband(48)
        paths = tuple(AliasPath(shift, ((stage, shift),), False)
                      for shift in (Fraction(0), Fraction(1)))
        upper, _, stats = population_bound(paths, Fraction(0), Fraction(1))
        old, _, _ = population_bound(paths, Fraction(0), Fraction(1), cap=False)
        self.assertEqual(upper, old)
        self.assertEqual(stats["subtree_caps_used"], 0)
        actual = explicit_population(paths, Fraction(0), Fraction(0))
        self.assertTrue(bool(actual.a > iv.mpf("1.4")))
        self.assertTrue(bool(upper >= actual.a))

    def test_deep_malformed_pair_and_overfull_node_fall_back(self):
        outer, inner = halfband(48), halfband(96)
        valid = independent_paths((inner, outer), Fraction(1, 2))
        # A valid root is insufficient: one upstream sibling pair is wrong.
        one = valid[0]
        other = replace(one, terms=one.terms[:-1] + ((inner, one.terms[-1][1] + 1),))
        malformed = (one, other) + valid[2:]
        overfull = tuple(AliasPath(shift, ((outer, shift),), False)
                         for shift in (Fraction(-16), Fraction(0), Fraction(16)))
        for paths in (malformed, overfull):
            upper, _, stats = population_bound(paths, Fraction(0), Fraction(1))
            old, _, _ = population_bound(paths, Fraction(0), Fraction(1), cap=False)
            self.assertEqual(upper, old)
            self.assertEqual(stats["subtree_caps_used"], 0)

    def test_general_asymmetric_stage_uses_full_cardinality_l1(self):
        asymmetric = FIRStage("asymmetric", 96, Fraction(48), 1, 2,
                              ((0, 0.5), (1, -0.125)))
        self.assertIsNone(halfband_alias_sum_upper(asymmetric))
        paths = independent_paths((asymmetric, halfband(48)), Fraction(1, 2))
        upper, _, stats = population_bound(paths, Fraction(0), Fraction(1))
        self.assertEqual(upper, iv.mpf("1.25"))
        self.assertGreater(stats["subtree_caps_used"], 0)
        for frequency in (Fraction(0), Fraction(2, 7), Fraction(1)):
            self.assertTrue(bool(explicit_population(paths, frequency, frequency).a <= upper))

    def test_full_expansion_agrees_with_explicit_continuous_enclosures(self):
        paths = independent_paths((halfband(96), halfband(48)), Fraction(1, 2))
        lo, hi = Fraction(1, 7), Fraction(2, 7)
        direct = explicit_population(paths, lo, hi)
        for capped in (False, True):
            upper, calls, _ = population_bound(paths, lo, hi, cap=capped, limit="0")
            self.assertGreater(calls, 0)
            self.assertTrue(bool(upper >= direct.a))
        # A source-frequency label collision does not merge distinct paths.
        collided = tuple(replace(path, upstream_shift=Fraction(0)) for path in paths)
        self.assertEqual(population_bound(paths, lo, hi)[0], population_bound(collided, lo, hi)[0])

    def test_rational_alias_transition_and_both_one_sided_limits(self):
        rational = FIRStage("rational", 24, Fraction(36), 3, 2,
                            ((0, 1.5), (1, 0.125)))
        downstream = halfband(36)
        operator = SimpleNamespace(input_hz=36, output_hz=18, U=3)
        with patch("p15_src_stagewise_continuum.make_native_stages", return_value=(rational,)), \
             patch("p15_src_stagewise_continuum.make_src_stages", return_value=(downstream,)), \
             patch("p15_src_stagewise_continuum.native_profile", return_value=(24, 36, (), {})):
            transition = complete_paths("synthetic", operator, Fraction(0), Fraction(9), require_direct=False)
            self.assertIsInstance(transition, BranchBoundary)
            self.assertEqual(transition.at, Fraction(6))
            for lo, hi in ((Fraction(0), Fraction(6)), (Fraction(6), Fraction(9)),
                           (Fraction(6), Fraction(6))):
                paths = complete_paths("synthetic", operator, lo, hi, require_direct=False)
                self.assertEqual(len(paths), 4)
                upper, _, stats = population_bound(paths, lo, hi)
                self.assertGreater(stats["subtree_caps_used"], 0)
                frequencies = (lo, (lo + hi) / 2, hi)
                for frequency in frequencies:
                    self.assertTrue(bool(explicit_population(paths, frequency, frequency).a <= upper))
                    independent = independent_paths((rational, downstream), frequency)
                    self.assertTrue(bool(explicit_population(independent, frequency, frequency).a <= upper))

    def test_actual_dsd256_native_tree_keeps_all_sixty_four_paths(self):
        stages = make_native_stages("master256")
        paths = independent_paths(stages, Fraction(1000, 3))
        self.assertEqual(len(paths), math.prod(stage.M for stage in stages))
        self.assertEqual(len(paths), 64)
        upper, calls, stats = population_bound(paths, Fraction(0), Fraction(1000))
        old, _, _ = population_bound(paths, Fraction(0), Fraction(1000), cap=False)
        self.assertTrue(bool(upper < old))
        self.assertEqual(calls, 0)
        self.assertGreater(stats["subtree_caps_used"], 0)
        for frequency in (Fraction(0), Fraction(1000, 3), Fraction(1000)):
            actual_paths = independent_paths(stages, frequency)
            self.assertEqual(len(actual_paths), 64)
            self.assertTrue(bool(explicit_population(actual_paths, frequency, frequency).a <= upper))


if __name__ == "__main__":
    unittest.main()

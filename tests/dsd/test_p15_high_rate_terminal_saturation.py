#!/usr/bin/env python3
"""Adversarial checks of abandoning an already saturated upper-bound sum.

An early return is not a failure witness.  It must still enclose every path
and allow the caller to certify smaller intervals with tighter stage bounds.
"""
from fractions import Fraction
import unittest

from mpmath import iv

from p15_src_branch_bound import bound_population
from p15_src_continuum_bounds import scalar
from p15_src_stagewise_alias_proof import FIRStage
from p15_src_stagewise_continuum import AliasPath


def paths_for(stage, count):
    # Integer-period shifts are intentional: the finite population contains
    # distinct formal paths of the same periodic response.  Every multiplicity
    # must remain counted, and no complete-physical-family claim is made.
    return tuple(AliasPath(Fraction(k), ((stage, Fraction(k)),), False)
                 for k in range(count))


class TerminalUpperSaturationTests(unittest.TestCase):
    def setUp(self):
        iv.dps = 75

    def test_early_return_retains_every_unevaluated_path_upper(self):
        stage = FIRStage('synthetic', 1, Fraction(1), 1, 1, ((0, 1.0),))
        paths = paths_for(stage, 64)
        calls = []

        def evaluate(term, lo, hi):
            calls.append(term[1])
            return iv.mpf(10 if term[1] == 0 else 1)

        stats = {}
        early, count = bound_population(paths, Fraction(0), Fraction(0),
            include=lambda p: True, limit='2', evaluate=evaluate, stats=stats)
        self.assertEqual(count, 1)
        self.assertEqual(calls, [Fraction(0)])
        # One evaluated upper of ten plus 63 unexpanded unit-gain leaves.
        self.assertTrue(bool(early >= 73))
        self.assertEqual(stats['terminal_saturation_returns'], 1)
        calls.clear()
        complete, complete_count = bound_population(paths, Fraction(0), Fraction(0),
            include=lambda p: True, limit='2', evaluate=evaluate,
            use_terminal_saturation=False)
        self.assertEqual(complete_count, 64)
        self.assertEqual(set(calls), set(Fraction(k) for k in range(64)))
        self.assertTrue(bool(complete <= early))
        # The independent exact transfer sum is 64, including every path.
        self.assertTrue(bool(complete >= 64))

    def test_smaller_intervals_can_pass_after_a_valid_coarse_upper_returns(self):
        # H(x) = (1-exp(2*pi*i*x))/2, so |H(x)| = |sin(pi*x)|.
        stage = FIRStage('difference', 1, Fraction(1), 1, 1,
                         ((0, 0.5), (1, -0.5)))
        paths = paths_for(stage, 64)
        lo, hi = Fraction(0), Fraction(1, 10000)

        def evaluate(term, left, right):
            if right-left > Fraction(1, 20000) and term[1] == 0:
                return iv.mpf(10)  # Deliberately loose but valid coarse upper.
            return iv.sin(iv.pi * scalar(right)).b

        stats = {}
        coarse, _ = bound_population(paths, lo, hi, include=lambda p: True,
            limit='0.1', evaluate=evaluate, stats=stats)
        self.assertTrue(bool(coarse > iv.mpf('0.1')))
        self.assertEqual(stats['terminal_saturation_returns'], 1)
        midpoint = (lo+hi)/2
        for left, right in ((lo, midpoint), (midpoint, hi)):
            child, _ = bound_population(paths, left, right,
                include=lambda p: True, limit='0.1', evaluate=evaluate)
            independent = 64 * iv.sin(iv.pi * scalar(right))
            self.assertTrue(bool(child < iv.mpf('0.1')))
            self.assertTrue(bool(child >= independent.a))

    def test_exact_accumulation_below_and_at_threshold_with_large_cancellation(self):
        # The large L1 initial total loses significant digits when old
        # frontier entries are subtracted.  The independent fixed-upper sum
        # must not confuse that enclosure width with terminal saturation.
        stage = FIRStage('cancellation', 1, Fraction(1), 1, 1,
                         ((0, 1e100), (1, -1e100)))
        paths = paths_for(stage, 4)
        delta = Fraction(1, 2**100)
        for last, expected in ((Fraction(0), 0), (2*delta, 1)):
            values = (Fraction(1, 2)-delta, Fraction(1, 2)-delta, last, Fraction(0))
            stats = {}

            def evaluate(term, lo, hi):
                return scalar(values[int(term[1])]).b

            upper, _ = bound_population(paths, Fraction(0), Fraction(0),
                include=lambda p: True, limit='1', evaluate=evaluate, stats=stats)
            self.assertEqual(stats['terminal_saturation_returns'], expected)
            # The exact response is zero at every integer-period shift.
            self.assertTrue(bool(upper >= 0))

    def test_multiple_subthreshold_terminal_upper_endpoints_accumulate(self):
        stage = FIRStage('constant', 1, Fraction(1), 1, 1, ((0, 0.5),))
        paths = paths_for(stage, 32)
        values = (Fraction(3, 4), Fraction(3, 4))
        stats = {}

        def evaluate(term, lo, hi):
            return scalar(values[int(term[1])] if term[1] < 2 else Fraction(1, 2)).b

        upper, calls = bound_population(paths, Fraction(0), Fraction(0),
            include=lambda p: True, limit='1.25', evaluate=evaluate, stats=stats)
        self.assertEqual(calls, 2)
        self.assertEqual(stats['terminal_saturation_returns'], 1)
        self.assertTrue(bool(upper >= 16))  # Exact complete magnitude sum.


if __name__ == '__main__':
    unittest.main()

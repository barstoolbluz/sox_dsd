#!/usr/bin/env python3
"""Independent adversarial checks of the high-rate alias-pair majorant.

The proof is the exact polynomial identity plus the interval cover.  Point
checks below independently exercise indexing, cancellation and boundaries;
they are not substituted for that continuous-frequency argument.
"""
from dataclasses import replace
from fractions import Fraction
from hashlib import sha256
import json
import math
import unittest

from mpmath import iv

from p15_src_continuum_bounds import (
    TrigPoly, magnitude_bounds as slow_complex_bounds, scalar)
from p15_src_halfband_majorant import (
    _certify_taps, halfband_alias_sum_upper, halfband_majorant,
    halfband_majorant_info)
from p15_src_stagewise_alias_proof import FIRStage, make_native_stages


def direct_complex_amplitude(taps, frequency):
    """Independent all-tap directed complex sum; no symmetry or recurrence."""
    real = iv.mpf(0)
    imaginary = iv.mpf(0)
    for k, coefficient in taps:
        angle = 2 * iv.pi * scalar(Fraction(frequency)) * k
        real += iv.mpf(coefficient) * iv.cos(angle)
        imaginary += iv.mpf(coefficient) * iv.sin(angle)
    return iv.sqrt(real**2 + imaginary**2)


class ExactHalfbandMajorantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        iv.dps = 75
        cls.source = make_native_stages('master256')[0]

    def test_source_global_cover_replayed_with_independent_complex_evaluator(self):
        proof = halfband_majorant(self.source)
        self.assertIsNotNone(proof)
        self.assertTrue(bool(proof.upper < iv.mpf('1.00000002')))
        self.assertLessEqual(proof.nodes_examined, 256)
        self.assertEqual(proof.covered_intervals[0][0], Fraction(0))
        self.assertEqual(proof.covered_intervals[-1][1], Fraction(1, 4))
        self.assertTrue(all(a[1] == b[0] for a, b in
                            zip(proof.covered_intervals, proof.covered_intervals[1:])))
        odd = TrigPoly(tuple((k, c) for k, c in self.source.taps if k), Fraction(0))
        for lo, hi in proof.covered_intervals:
            _lower, upper, _center = slow_complex_bounds(odd, lo, hi)
            self.assertTrue(bool(upper.b < iv.mpf('0.50000001').a),
                            (str(lo), str(hi), str(upper)))

    def test_source_pair_at_dc_nyquist_rational_and_one_sided_boundaries(self):
        upper = halfband_alias_sum_upper(self.source)
        epsilon = Fraction(1, 10**20)
        frequencies = (Fraction(0), epsilon, Fraction(1, 4) - epsilon,
                       Fraction(1, 4), Fraction(1, 4) + epsilon,
                       Fraction(1, 2) - epsilon, Fraction(1, 2),
                       Fraction(1, 2) + epsilon, Fraction(257, 1542),
                       Fraction(-1, 997))
        for frequency in frequencies:
            a = direct_complex_amplitude(self.source.taps, frequency)
            b = direct_complex_amplitude(self.source.taps, frequency + Fraction(1, 2))
            self.assertTrue(bool((a + b).b <= upper), str(frequency))

    def test_exact_pattern_admission_has_no_approximate_equality(self):
        base = self.source
        cases = [replace(base, L=2), replace(base, M=3),
                 replace(base, output_hz=base.output_hz + 1)]
        coefficients = dict(base.taps)
        center_changed = dict(coefficients)
        center_changed[0] = math.nextafter(0.5, math.inf)
        even_changed = dict(coefficients)
        even_changed[2] = 1e-300
        asymmetric = dict(coefficients)
        asymmetric[1] = math.nextafter(asymmetric[1], math.inf)
        cases.extend(replace(base, taps=tuple(sorted(x.items()))) for x in
                     (center_changed, even_changed, asymmetric))
        cases.append(replace(base, taps=base.taps + (base.taps[0],)))
        for stage in cases:
            self.assertIsNone(halfband_alias_sum_upper(stage))

    def test_valid_pattern_with_excessive_pair_norm_declines_shortcut(self):
        stage = FIRStage('synthetic', 16, Fraction(8), 1, 2,
                         ((-1, 0.4), (0, 0.5), (1, 0.4)))
        self.assertIsNone(halfband_alias_sum_upper(stage))
        a = direct_complex_amplitude(stage.taps, Fraction(0))
        b = direct_complex_amplitude(stage.taps, Fraction(1, 2))
        self.assertTrue(bool((a + b).a > iv.mpf('1.5')))

    def test_cancellation_and_sparse_zero_support(self):
        stage = FIRStage('synthetic', 16, Fraction(8), 1, 2,
                         ((-9, -0.125), (-4, 0.0), (0, 0.5),
                          (4, -0.0), (9, -0.125)))
        proof = halfband_majorant(stage)
        self.assertIsNotNone(proof)
        for frequency in (Fraction(0), Fraction(1, 36), Fraction(1, 4),
                          Fraction(1, 2), Fraction(3, 7)):
            response = (direct_complex_amplitude(stage.taps, frequency) +
                        direct_complex_amplitude(stage.taps, frequency + Fraction(1, 2)))
            # Here |Q| <= sum |q[k]| = 1/4 by exact dyadic arithmetic, so
            # both branches are positive and their magnitude sum is exactly
            # one.  A directed complex evaluation can straddle that exact
            # endpoint; requiring its upper endpoint <= 1 would be invalid.
            self.assertTrue(bool(response.a <= 1 <= response.b))
            self.assertTrue(bool(proof.upper >= 1))

    def test_partial_frequency_cover_never_returns_a_norm(self):
        self.assertIsNone(_certify_taps(self.source.taps, max_nodes=1))

    def test_normalized_proof_reused_across_exactly_matching_source_clocks(self):
        slower = replace(self.source, input_hz=self.source.input_hz // 2,
                         output_hz=self.source.output_hz / 2)
        self.assertIs(halfband_majorant(self.source), halfband_majorant(slower))
        original = halfband_majorant_info(self.source)
        repeated = halfband_majorant_info(slower)
        self.assertEqual(original, repeated)
        self.assertEqual(len(original['coefficient_sha256']), 64)
        self.assertGreater(len(original['closed_cover']), 1)

    def test_cache_preserves_exact_signed_zero_coefficient_identity(self):
        plus = FIRStage('signed_zero', 16, Fraction(8), 1, 2,
                        ((-2, 0.0), (-1, 0.125), (0, 0.5), (1, 0.125)))
        minus = replace(plus, taps=((-2, -0.0), (-1, 0.125),
                                    (0, 0.5), (1, 0.125)))
        a, b = halfband_majorant(plus), halfband_majorant(minus)
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertIsNot(a, b)
        self.assertNotEqual(a.coefficient_sha256, b.coefficient_sha256)
        for stage, proof in ((plus, a), (minus, b)):
            words = [[k, coefficient.hex()] for k, coefficient in
                     sorted(stage.taps)]
            expected = sha256(json.dumps(words, separators=(',', ':')).encode('ascii'))
            self.assertEqual(proof.coefficient_sha256, expected.hexdigest())
        self.assertTrue(bool(a.upper == b.upper))
        # Canonical tap order has no mathematical effect and retains exact words.
        self.assertIs(a, halfband_majorant(replace(plus, taps=plus.taps[::-1])))

    def test_cached_float_proof_does_not_admit_equal_nonfloat_values(self):
        valid = FIRStage('float_types', 16, Fraction(8), 1, 2,
                         ((-2, 0.0), (-1, 0.125), (0, 0.5), (1, 0.125)))
        self.assertIsNotNone(halfband_majorant(valid))
        cases = (
            replace(valid, taps=((-2, 0), (-1, 0.125), (0, 0.5), (1, 0.125))),
            replace(valid, taps=((-2, 0.0), (-1, 0.125),
                                 (0, Fraction(1, 2)), (1, 0.125))),
            replace(valid, taps=((-2, 0.0), (-1, 0.125),
                                 (0, 0.5), (Fraction(1), 0.125))),
        )
        for stage in cases:
            self.assertEqual(stage.taps, valid.taps)
            self.assertIsNone(halfband_majorant(stage))

    def test_two_decimation_levels_include_every_alias(self):
        """Four exact source branches, with no RMS or phase cancellation."""
        taps = self.source.taps
        norm = halfband_alias_sum_upper(self.source)
        for output_fraction in (Fraction(0), Fraction(1, 239),
                                Fraction(1, 4), Fraction(1, 2)):
            total = iv.mpf(0)
            # Frequencies are in cycles of the second-stage input.  Its two
            # inverse branches are separated by 1/2.  The first-stage input
            # clock is twice as fast, so each is divided by two before its
            # own complete two-branch sum is evaluated.
            for second_alias in (0, 1):
                middle = output_fraction + Fraction(second_alias, 2)
                second = direct_complex_amplitude(taps, middle)
                for first_alias in (0, 1):
                    upstream = middle / 2 + Fraction(first_alias, 2)
                    first = direct_complex_amplitude(taps, upstream)
                    total += first * second
            self.assertTrue(bool(total.b <= (norm * norm).b), str(output_fraction))


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""Focused adversarial checks for the original P15 ideal spectral prover.

These test the cited invariants; the source-level arguments, not finite test
coverage, justify the general mathematical claims.
"""
from __future__ import annotations

from fractions import Fraction as F
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import mpmath as mp
from mpmath import iv
from p15_src_stagewise_alias_proof import FIRStage
from p15_src_continuum_bounds import TrigPoly, scalar
from p15_src_fixed_interval import fixed_symmetric_magnitude_bounds
from p15_src_interval_recurrence import general_magnitude_bounds, magnitude_bounds
from p15_src_difference_upper import difference_upper
from p15_src_halfband_majorant import halfband_alias_sum_upper
from p15_src_branch_bound import bound_population, exact_l1_gain
from p15_src_stagewise_continuum import (AliasPath, BranchBoundary,
    _next_ceil_transition, _next_floor_transition, bounds_single, complete_paths)
from p15_full_band_campaign import canonical_plan, receipt_path, bindings, check_one
from p15_final_receipt_adjudicator import audit_receipt, UnacceptableReceipt


def stage(input_hz, output_hz, L, M, taps, kind='synthetic'):
    return FIRStage(kind, input_hz, F(output_hz), L, M, tuple(taps))


class OriginalProverAdversarial(unittest.TestCase):
    def test_exact_binary64_coefficient_inclusion(self):
        for x in [math.nextafter(1., 2.), -0.3, 1e-300, 2**-1074, -2**-1074]:
            value = iv.mpf(x)
            exact = scalar(F.from_float(x))
            self.assertTrue(bool(value.a <= exact.a and exact.b <= value.b))
            self.assertEqual(F.from_float(x), F(*x.as_integer_ratio()))

    def test_directed_trigonometric_critical_quadrants(self):
        for x, cos_expected, sin_expected in [
            (F(0), 1, 0), (F(1, 4), 0, 1),
            (F(1, 2), -1, 0), (F(3, 4), 0, -1)]:
            angle = 2 * iv.pi * scalar(x)
            c, s = iv.cos(angle), iv.sin(angle)
            self.assertTrue(bool(c.a <= cos_expected <= c.b))
            self.assertTrue(bool(s.a <= sin_expected <= s.b))
        for q in [F(1, 2) - F(1, 10**30), F(1, 2) + F(1, 10**30)]:
            self.assertTrue(bool(iv.sin(iv.pi * scalar(q)).a >= 0))

    def test_negative_and_asymmetric_fir_magnitudes(self):
        poly = TrigPoly(((0, .5), (1, -.25), (2, .125)), F(0))
        for q in (F(0), F(1, 4), F(1, 2)):
            a, b, _ = general_magnitude_bounds(poly, q, q)
            with mp.workdps(90):
                z = sum(mp.mpf(v) * mp.exp(2j * mp.pi * k *
                        mp.mpf(q.numerator) / q.denominator) for k, v in poly.taps)
                magnitude = abs(z)
            self.assertLessEqual(float(a.a), float(magnitude))
            self.assertGreaterEqual(float(b.b), float(magnitude))

    def test_symmetric_fir_exact_cancellation(self):
        poly = TrigPoly(((-1, .25), (0, -.5), (1, .25)), F(0))
        at_zero = magnitude_bounds(poly, F(0), F(0))
        at_nyquist = magnitude_bounds(poly, F(1, 2), F(1, 2))
        self.assertTrue(bool(at_zero[0].a <= 0 <= at_zero[1].b))
        self.assertTrue(bool(at_nyquist[0].a <= 1 <= at_nyquist[1].b))
        self.assertIsNotNone(fixed_symmetric_magnitude_bounds(poly, F(0), F(1, 2)))

    def test_finite_difference_does_not_omit_negative_taps(self):
        poly = TrigPoly(((0, 1.), (1, -1.)), F(0))
        upper = difference_upper(poly, F(1, 4), F(1, 2))
        self.assertIsNotNone(upper)
        self.assertTrue(bool(upper.b >= 2))  # |1-(-1)| = 2 at Nyquist

    def test_halfband_requires_exact_complement_identity(self):
        valid = stage(8, 4, 1, 2, ((-1, .25), (0, .5), (1, .25)))
        p = halfband_alias_sum_upper(valid)
        self.assertIsNotNone(p)
        self.assertTrue(bool(p.b >= 1))
        not_even = stage(8, 4, 1, 2, ((-1, .25), (0, .5), (1, math.nextafter(.25, 1.))))
        not_half = stage(8, 4, 1, 2, ((-1, .25), (0, math.nextafter(.5, 1.)), (1, .25)))
        self.assertIsNone(halfband_alias_sum_upper(not_even))
        self.assertIsNone(halfband_alias_sum_upper(not_half))

    def test_exact_rational_branch_transitions(self):
        q = F(-15, 8)
        self.assertEqual(_next_ceil_transition(F(0), F(1), q, F(4)), F(1, 2))
        self.assertEqual(_next_floor_transition(F(0), F(1), F(7, 8), F(4)), F(1, 2))
        self.assertIsNone(_next_ceil_transition(F(0), F(1, 2), q, F(4)))

    def test_complete_native_lattice_with_two_decimators(self):
        native = stage(8, 4, 1, 2, ((0, 1.),), 'native')
        src = stage(4, 2, 1, 2, ((0, 1.),), 'src')
        op = SimpleNamespace(input_hz=4, output_hz=2, U=1)
        import p15_src_stagewise_continuum as continuum
        with patch.object(continuum, 'make_native_stages', return_value=(native,)), \
             patch.object(continuum, 'make_src_stages', return_value=(src,)), \
             patch.object(continuum, 'native_profile', return_value=(8, 4, (), {})):
            paths = complete_paths('synthetic', op, F(1, 3), F(2, 3))
            self.assertEqual(len(paths), 4)
            self.assertEqual({p.upstream_shift for p in paths}, {F(-4), F(-2), F(0), F(2)})
            self.assertEqual(sum(p.direct for p in paths), 1)

    def test_path_multiplicity_and_unexpanded_branch_caps(self):
        first = stage(8, 4, 1, 2, ((0, 1.),), 'one')
        second = stage(4, 2, 1, 2, ((0, 1.),), 'two')
        paths = [AliasPath(F(0), ((first, F(i)), (second, F(j))), i == j == 0)
                 for i in (0, 4) for j in (0, 2)]
        # Repeat the *same complete path* to exercise conservative multiplicity
        paths.append(paths[0])
        for caps in (True, False):
            for saturated in (True, False):
                upper, _ = bound_population(paths, F(0), F(0),
                    include=lambda p: True, limit='0.5',
                    evaluate=lambda term, lo, hi: iv.mpf(1).b,
                    use_subtree_caps=caps, use_terminal_saturation=saturated)
                self.assertTrue(bool(upper.b >= 5))

    def test_cache_does_not_confuse_nearby_coefficient_words(self):
        x = stage(8, 4, 1, 2, ((0, .25),))
        y = stage(8, 4, 1, 2, ((0, math.nextafter(.25, 1.)),))
        self.assertNotEqual(x, y)
        self.assertTrue(bool(exact_l1_gain(x) < exact_l1_gain(y)))

    def test_receipt_fabricated_bound_is_detected_by_audit(self):
        job = next(j for j in canonical_plan() if j['mode'] == 'stop')
        originals = Path(__file__).resolve().parent / 'results/P15_full_band_campaign_certified_2026-10-18/receipts'
        d = json.loads(receipt_path(originals, job).read_text())
        forged = json.loads(json.dumps(d))
        forged['certificate']['max_native_stop_source_transfer_upper'] = .1
        with self.assertRaisesRegex(UnacceptableReceipt, 'contradicts policy'):
            audit_receipt(forged, job, bindings())
        # The historical campaign's check_one trusts its PASS flag: this is
        # a provenance-checker gap, not a demonstrated miscomputed FIR bound.
        with TemporaryDirectory() as temp:
            receipt_path(Path(temp), job).write_text(json.dumps(forged))
            self.assertEqual(check_one(Path(temp), job, bindings())['certificate']['status'],
                             'PASS-LOCAL-STOP-SOURCE')

    def test_policy_forgeries_refused(self):
        job = next(j for j in canonical_plan() if j['mode'] == 'pass')
        originals = Path(__file__).resolve().parent / 'results/P15_full_band_campaign_certified_2026-10-18/receipts'
        original = json.loads(receipt_path(originals, job).read_text())
        for field, value in [('profile', 'master256'), ('governing_stopband_hz', -1),
                              ('fully_proven_subintervals', 0)]:
            forged = json.loads(json.dumps(original))
            forged['certificate'][field] = value
            with self.assertRaises(UnacceptableReceipt):
                audit_receipt(forged, job, bindings())
        forged = json.loads(json.dumps(original))
        forged['certificate']['max_coherent_alias_upper'] = 1e-8
        with self.assertRaises(UnacceptableReceipt):
            audit_receipt(forged, job, bindings())

    def test_inward_dyadic_rounding_would_be_caught(self):
        from p15_src_fixed_interval import _mpf_dyadic
        # +3*2^-300 and -3*2^-300 on the 2^-288 dyadic grid.
        self.assertEqual(_mpf_dyadic((0, 3, -300, 2), up=False), 0)
        self.assertEqual(_mpf_dyadic((0, 3, -300, 2), up=True), 1)
        self.assertEqual(_mpf_dyadic((1, 3, -300, 2), up=False), -1)
        self.assertEqual(_mpf_dyadic((1, 3, -300, 2), up=True), 0)

    def test_independent_integer_trigonometric_anchor_crosscheck(self):
        from p15_r5_exact_trig import GRID, sincos
        # Disjoint rigorous enclosures would be an explicit backend alarm.
        # Their agreement on finite anchors is corroboration, not proof.
        for q in (F(0), F(1, 4), F(37, 257), F(119, 997),
                  F(10**6 + 1, 1000003)):
            int_sin, int_cos = sincos(q)
            for original, integer in ((iv.sin(2*iv.pi*scalar(q)), int_sin),
                                      (iv.cos(2*iv.pi*scalar(q)), int_cos)):
                low = scalar(F(integer[0], GRID)).a
                high = scalar(F(integer[1], GRID)).b
                self.assertTrue(bool(original.a <= high and original.b >= low))

    def test_stage_upsampling_gain_normalization(self):
        first = stage(8, 16, 2, 1, ((0, 2.),))
        second = stage(8, 16, 2, 1, ((0, 1.),))
        for s, gain in ((first, 1), (second, F(1, 2))):
            a, b = bounds_single(s, F(0), F(0), F(0))
            self.assertTrue(bool(a.a <= scalar(F(gain)).a and scalar(F(gain)).b <= b.b))

    def test_incorrect_source_lattice_count_refused(self):
        import p15_src_stagewise_continuum as continuum
        native = stage(8, 4, 1, 2, ((0, 1.),), 'native')
        src = stage(4, 2, 1, 2, ((0, 1.),), 'src')
        # Wrong U would advertise a false source-harmonic spacing.
        op = SimpleNamespace(input_hz=4, output_hz=2, U=2)
        with patch.object(continuum, 'make_native_stages', return_value=(native,)), \
             patch.object(continuum, 'make_src_stages', return_value=(src,)), \
             patch.object(continuum, 'native_profile', return_value=(8, 4, (), {})):
            with self.assertRaises(continuum.Unproved):
                complete_paths('synthetic', op, F(1, 3), F(2, 3))

    def test_perturbed_captured_production_word_refused(self):
        from p15_src_capture_matrix import verify_pair
        from p15_src_bound_operator import UnboundOperator
        snapshot = Path(__file__).resolve().parent / 'results/P15_SRC_STAGE_BOUND_OPT_2026-10-17/176400-44100'
        with TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest / 'operator-binding.json').write_bytes((snapshot / 'operator-binding.json').read_bytes())
            data = json.loads((snapshot / 'stage-snapshot.json').read_text())
            original = data['stages'][0]['coefficients'][0]
            word = float.fromhex(original)
            data['stages'][0]['coefficients'][0] = math.nextafter(word, math.inf).hex()
            (dest / 'stage-snapshot.json').write_text(json.dumps(data))
            with self.assertRaises(UnboundOperator):
                verify_pair(dest, 176400, 44100)


if __name__ == '__main__':
    unittest.main()

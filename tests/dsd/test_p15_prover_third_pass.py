"""Third-pass adaptive Taylor-order tests against independent complex intervals.

No sampled point is used to certify a whole interval. Interval enclosures are
proved by Taylor's theorem; independent evaluations are regression checks.
"""
from __future__ import annotations

from fractions import Fraction
import math
import random
import unittest

from mpmath import iv
from p15_src_continuum_bounds import TrigPoly, magnitude_bounds as independent_complex
from p15_src_capture_matrix import DEFAULT, verify_pair
from p15_src_stagewise_alias_proof import make_src_stages


class SourceFiniteDifferenceEnclosures(unittest.TestCase):
    def test_differences_match_exact_integer_polynomial_identity(self):
        from p15_src_difference_upper import difference_moments
        # Missing interior taps must be ZERO-padded, not compressed into
        # adjacent powers. Signed coefficients and negative exponents matter.
        poly=TrigPoly(((-8,2**-10),(-5,-0.125),(0,0.5),(4,-2**-17)),Fraction(0))
        from math import comb
        coeff={k:Fraction.from_float(v) for k,v in poly.taps}
        for power,computed in difference_moments(poly):
            expected={}
            for k,c in coeff.items():
                for j in range(power+1):
                    idx=k+j
                    expected[idx]=expected.get(idx,Fraction(0))+(-1)**j*comb(power,j)*c
            self.assertEqual(computed,sum(map(abs,expected.values()),Fraction(0)))

    def test_difference_encloses_independent_high_precision_point_spectrum(self):
        from p15_src_difference_upper import difference_upper
        rng=random.Random(0xA515)
        examples=[
            TrigPoly(((-7,0.125),(-1,-0.5),(0,0.125),(5,0.25)),Fraction(13,5)),
            TrigPoly(tuple(sorted({k:rng.randint(-100,100)*2**-20
                                  for k in range(-80,81)}.items())),Fraction(0)),
        ]
        for poly in examples:
            for lo,hi in ((Fraction(1,1000),Fraction(1,500)),
                          (Fraction(2,5),Fraction(41,100)),
                          (Fraction(1,2)-Fraction(1,1000),Fraction(1,2))):
                candidate=difference_upper(poly,lo,hi)
                self.assertIsNotNone(candidate)
                for f in (lo,(lo+hi)/2,hi):
                    _a,b,_=independent_complex(poly,f,f)
                    self.assertTrue(bool(candidate.b>=b.b),(lo,hi,f))
            self.assertIsNone(difference_upper(poly,Fraction(0),Fraction(1,100)))

    def test_real_source_4160_tap_alias_route_and_fallback(self):
        from p15_src_stagewise_continuum import cheap_alias_upper,bounds_single
        _,op=verify_pair(DEFAULT/'88200-192000',88200,192000)
        stage=next(s for s in make_src_stages(op) if len(s.taps)==4160)
        rate=stage.input_hz*stage.L
        # Shift into a high-frequency SRC image; 0..1Hz output interval.
        high=cheap_alias_upper(stage,Fraction(rate*2,5),Fraction(0),Fraction(1))
        self.assertIsNotNone(high)
        # The global difference upper need not be as tight as Taylor.
        strict=bounds_single(stage,Fraction(rate*2,5),Fraction(0),Fraction(1))[1]
        self.assertTrue(bool(high>=strict))
        self.assertTrue(bool(high<iv.mpf('1e-10')))
        # A near-passband alias must NOT use the cheap upper alone.
        self.assertIsNone(cheap_alias_upper(stage,Fraction(0),Fraction(0),Fraction(1)))

if __name__=='__main__':unittest.main()

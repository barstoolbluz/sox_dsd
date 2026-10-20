"""Adversarial R7 exact-ball, symmetry and mirror-pair interval proofs.

Containment of exact analytically known values is a theorem test; overlap with
an unrelated, already justified R5 enclosure is a regression corroboration.
Neither sampled numerical agreement nor a historical receipt can grant PASS.
"""
from __future__ import annotations
import unittest
from fractions import Fraction as F
from math import isqrt

from p15_r7_fast_fir import (ball_mul,ball_power,ball_from_rect,
    ball_conj,ball_rectangle,ceil_sqrt,certify_fir_auto,certify_fir_fast,
    certify_linear_phase_fir,certify_paired_fir)
from p15_r5_exact_trig import GRID,sincos
from p15_r5_integer_spectral import IntervalRefusal


def contains(c,q):
    return c.lower()<=q<=c.upper()


class TestR7CertifiedMath(unittest.TestCase):
    def test_integer_sqrt(self):
        for n in range(1000):
            r=ceil_sqrt(n)
            self.assertTrue((r-1)**2<n<=r*r if n else r==0)

    def test_ball_products_known_exact(self):
        for a in ((GRID,0,0),(0,GRID,0),(-GRID,0,0),(GRID,GRID,0),
                  (GRID//3,-GRID//2,2)):
            for b in ((GRID,0,0),(0,GRID,0),(0,0,GRID//4),(-GRID,GRID,1)):
                out=ball_mul(a,b)
                x=F(a[0]*b[0]-a[1]*b[1],GRID*GRID)
                y=F(a[0]*b[1]+a[1]*b[0],GRID*GRID)
                re,im=ball_rectangle(out)
                self.assertLessEqual(F(re[0],GRID),x)
                self.assertGreaterEqual(F(re[1],GRID),x)
                self.assertLessEqual(F(im[0],GRID),y)
                self.assertGreaterEqual(F(im[1],GRID),y)

    def test_power_known_roots_of_unity(self):
        s,c=sincos(F(1,4))
        z=ball_from_rect((c,s))
        for n,x,y in ((0,1,0),(1,0,1),(2,-1,0),(3,0,-1),(4,1,0),(64,1,0)):
            b=ball_power(z,n)
            re,im=ball_rectangle(b)
            self.assertLessEqual(re[0],GRID*x)
            self.assertGreaterEqual(re[1],GRID*x)
            self.assertLessEqual(im[0],GRID*y)
            self.assertGreaterEqual(im[1],GRID*y)

    def test_half_grid_dc_and_nyquist(self):
        h=((-1,.25),(0,.5),(1,.25))
        for f,known in ((F(0),F(1)),(F(1,4),F(1,2)),(F(1,2),F(0))):
            self.assertTrue(contains(certify_linear_phase_fir(h,f,f),known))

    def test_negative_coefficients_and_cancellation(self):
        h=((-1,-.25),(0,.5),(1,-.25))
        for f,known in ((F(0),F(0)),(F(1,4),F(1,2)),(F(1,2),F(1))):
            self.assertTrue(contains(certify_linear_phase_fir(h,f,f),known))

    def test_even_centered_zero_at_quarter(self):
        h=((-2,.25),(-1,.25),(0,.25),(1,.25))
        self.assertTrue(contains(certify_linear_phase_fir(h,F(1,4),F(1,4)),F(0)))
        self.assertTrue(contains(certify_linear_phase_fir(h,F(0),F(0)),F(1)))

    def test_nonpalindromic_mirror_pair_zero(self):
        h=((-1,.25),(0,-.25))
        self.assertTrue(contains(certify_paired_fir(h,F(0),F(0)),F(0)))
        self.assertTrue(contains(certify_paired_fir(h,F(1,2),F(1,2)),F(1,2)))

    def test_pair_support_missing_refuses(self):
        with self.assertRaises(IntervalRefusal):
            certify_paired_fir(((-3,.25),(0,.25),(2,.5)),F(0),F(1,100))

    def test_bad_symmetry_refuses(self):
        with self.assertRaises(IntervalRefusal):
            certify_linear_phase_fir(((-1,.24),(0,.5),(1,.25)),F(0),F(1,100))

    def test_sign_and_center_generic_fallback(self):
        h=((-3,.125),(-1,.25),(2,.375))
        # This support is not mirrored, and the auto path must remain generic.
        for lo,hi in ((F(0),F(1,1000)),(F(1,9),F(112,1000))):
            a=certify_fir_auto(h,lo,hi)
            b=certify_fir_fast(h,lo,hi)
            self.assertEqual(a,b)

    def test_sym_and_paired_continuum_overlap_independent_r5(self):
        filters=(
            ((-2,.125),(-1,-.25),(0,.75),(1,-.25),(2,.125)),
            ((-2,.25),(-1,-.5),(0,.25),(1,-.125)),
            ((-1,-.5),(0,.875),(1,.375)),
            ((-4,.0001),(-1,.75),(0,.01),(3,.5)),
        )
        ranges=((F(0),F(1,100)),(F(1,8),F(126,1000)),
                (F(1,4),F(1,4)),(F(49,100),F(1,2)))
        from p15_r5_integer_spectral import certify_fir
        for h in filters:
            for lo,hi in ranges:
                with self.subTest(h=h,lo=lo,hi=hi):
                    a=certify_fir_auto(h,lo,hi,order=8)
                    b=certify_fir(h,lo,hi,order=8)
                    self.assertLessEqual(a.lower(),b.upper())
                    self.assertLessEqual(b.lower(),a.upper())

    def test_nonfinite_and_duplicate_rejected(self):
        for h in (((1,float('nan')),),((0,.1),(0,.2)),((-1,float('inf')),(1,.25))):
            with self.assertRaises(IntervalRefusal):
                certify_fir_auto(h,F(0),F(1,100))

    def test_bad_interval_and_order_rejected(self):
        for lo,hi,order in ((F(-1),F(0),8),(F(0),F(3,4),8),
                            (F(1,10),F(1,100),8),(F(0),F(1,4),15)):
            with self.assertRaises(IntervalRefusal):
                certify_fir_auto(((0,1.),(1,0.)),lo,hi,order=order)


if __name__=='__main__':unittest.main()

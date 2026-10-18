#!/usr/bin/env python3
"""Independent enclosures for the P15 even-FIR dyadic interval evaluator."""
from __future__ import annotations
from fractions import Fraction
import math
import random
import unittest

from mpmath import iv
from p15_src_continuum_bounds import TrigPoly, magnitude_bounds as direct_reference
from p15_src_fixed_interval import (_Q, _from_iv, _mul, _mul_positive,
    _multiply_exact_coefficient, fixed_symmetric_magnitude_bounds)
from p15_src_symmetric_interval import even_taps, symmetric_magnitude_bounds
from p15_src_interval_recurrence import (magnitude_bounds,
    general_magnitude_bounds)
from p15_src_branch_bound import bound_population
from p15_src_stagewise_alias_proof import FIRStage
from p15_src_stagewise_continuum import (AliasPath, bounds_single,
    BranchBoundary, complete_paths)
from p15_src_capture_matrix import verify_pair, DEFAULT


def truth_contained(frequency, poly, lo, hi, order):
    fast_lo,fast_hi,_ = fixed_symmetric_magnitude_bounds(poly,lo,hi,order)
    # The point response is evaluated through the independent DIRECT
    # complex interval evaluator, rather than via the fixed-point recurrence.
    ref_lo,ref_hi,_=direct_reference(poly,frequency,frequency,order)
    assert bool(fast_lo.a <= ref_lo.a), (lo,hi,frequency,fast_lo,ref_lo)
    assert bool(fast_hi.b >= ref_hi.b), (lo,hi,frequency,fast_hi,ref_hi)


class FixedAlgebra(unittest.TestCase):
    def test_directed_dyadic_endpoints_and_products(self):
        random_gen=random.Random(2173)
        for _ in range(120):
            a=Fraction(random_gen.randint(-100000,100000),random_gen.randint(1,9000))
            b=Fraction(random_gen.randint(-100000,100000),random_gen.randint(1,9000))
            x=(a.numerator*_Q//a.denominator,
               -((-a.numerator*_Q)//a.denominator))
            y=(b.numerator*_Q//b.denominator,
               -((-b.numerator*_Q)//b.denominator))
            self.assertLessEqual(Fraction(x[0],_Q),a)
            self.assertGreaterEqual(Fraction(x[1],_Q),a)
            prod=_mul(x,y)
            self.assertLessEqual(Fraction(prod[0],_Q),a*b)
            self.assertGreaterEqual(Fraction(prod[1],_Q),a*b)
            coeff=math.ldexp(random_gen.randint(-500,500),-20)
            scaled=_multiply_exact_coefficient(x,coeff)
            expected=a*Fraction.from_float(coeff)
            self.assertLessEqual(Fraction(scaled[0],_Q),expected)
            self.assertGreaterEqual(Fraction(scaled[1],_Q),expected)
        x=_from_iv(iv.pi)
        def dyadic(raw):
            sign,mantissa,exponent,_ = raw
            return Fraction(-mantissa if sign else mantissa) * Fraction(2)**exponent
        self.assertLessEqual(Fraction(x[0],_Q),dyadic(iv.pi._mpi_[0]))
        self.assertGreaterEqual(Fraction(x[1],_Q),dyadic(iv.pi._mpi_[1]))

    def test_exact_symmetry_guard_and_complex_fallback(self):
        even=TrigPoly(((-3,0.),(-2,.125),(-1,-.25),(0,1.),
                       (1,-.25),(2,.125)),Fraction(0))
        self.assertIsNotNone(even_taps(even))
        empty=TrigPoly((),Fraction(0))
        self.assertIsNone(even_taps(empty))
        with self.assertRaises(Exception):
            magnitude_bounds(empty,Fraction(0),Fraction(1,2))
        odd=TrigPoly(((-1,.25),(0,1.),(1,.125)),Fraction(0))
        self.assertIsNone(even_taps(odd))
        for poly in (odd,TrigPoly(((0,1.0),(7,-.125)),Fraction(1,4))):
            self.assertIsNone(even_taps(poly))
            bounds=magnitude_bounds(poly,Fraction(1,17),Fraction(2,17))
            ref=general_magnitude_bounds(poly,Fraction(1,17),Fraction(2,17))
            self.assertEqual(bounds,ref)


class ContinuousPointEnclosures(unittest.TestCase):
    def test_adversarial_rational_nyquist_zero_and_cancellation(self):
        cases=[
            (TrigPoly(((-1,-.5),(0,1.),(1,-.5)),Fraction(0)),
                Fraction(0),Fraction(1,300)),
            (TrigPoly(((-2,.5),(0,-1.),(2,.5)),Fraction(0)),
                Fraction(1,4)-Fraction(1,100000),Fraction(1,4)+Fraction(1,100000)),
            (TrigPoly(((-3,.125),(-2,-.25),(0,.25),(2,-.25),(3,.125)),Fraction(0)),
                Fraction(499,1000),Fraction(1,2)),
            (TrigPoly(tuple((k, math.ldexp((-1)**k, -13)) for k in range(-800,801)),
                      Fraction(0)),Fraction(1,5),Fraction(1,5)+Fraction(1,30000)),
            (TrigPoly(((0,5e-200),),Fraction(0)),Fraction(0),Fraction(1,2)),
        ]
        for poly,lo,hi in cases:
            for order in (2,4,8,12):
                with self.subTest(n=len(poly.taps),lo=lo,order=order):
                    fixed=fixed_symmetric_magnitude_bounds(poly,lo,hi,order)
                    independent=symmetric_magnitude_bounds(poly,lo,hi,order)
                    # Two separately implemented directed interval algorithms
                    # need not produce nested interval widths.
                    for t in (lo, (lo*3+hi)/4,(lo+hi)/2,(lo+hi*3)/4,hi):
                        reflow,refhigh,_=direct_reference(poly,t,t,order)
                        for result in (fixed,independent):
                            self.assertTrue(bool(result[0].a<=reflow.a))
                            self.assertTrue(bool(result[1].b>=refhigh.b))
                    self.assertAlmostEqual(float(fixed[1].b),float(independent[1].b),places=9)

    def test_150_digit_independent_point_enclosures(self):
        # Independently increase reference precision beyond the numerical
        # evaluator's 75-digit transcendental anchor arithmetic.
        source = TrigPoly(tuple((k,math.ldexp((-1)**(abs(k)//2),-12))
                         for k in range(-240,241)),Fraction(0))
        a=Fraction(1,7)-Fraction(1,100000)
        b=Fraction(1,7)+Fraction(1,100000)
        fast=fixed_symmetric_magnitude_bounds(source,a,b,order=12)
        old=iv.dps
        try:
            iv.dps=150
            for f in (a,(3*a+b)/4,(a+b)/2,(a+3*b)/4,b):
                ref=direct_reference(source,f,f,order=12)
                self.assertTrue(bool(fast[0].a <= ref[0].a))
                self.assertTrue(bool(fast[1].b >= ref[1].b))
        finally:
            iv.dps=old

    def test_randomized_high_order_endpoints(self):
        rnd=random.Random(857)
        for i in range(24):
            coeff=[math.ldexp(rnd.uniform(-1,1),-rnd.randint(0,20))
                   for _ in range(rnd.randint(4,100))]
            taps=[(0,math.ldexp(rnd.uniform(-1,1),-10))]
            for k,c in enumerate(coeff,1): taps.extend(((-k,c),(k,c)))
            poly=TrigPoly(tuple(sorted(taps)),Fraction(0))
            lo=Fraction(rnd.randrange(0,10000),20000)
            hi=min(Fraction(1,2),lo+Fraction(rnd.randint(0,500),10000000))
            order=rnd.choice((1,3,7,8,12))
            for f in (lo,(lo+hi)/2,hi):
                with self.subTest(i=i,f=f):truth_contained(f,poly,lo,hi,order)


class AliasAndTransitionValidation(unittest.TestCase):
    def test_complete_multi_alias_hierarchical_upper(self):
        s1=FIRStage('first',1000,Fraction(1000),1,1,
                    ((-2,.125),(0,.75),(2,.125)))
        s2=FIRStage('second',1000,Fraction(1000),1,1,
                    ((-3,-.0625),(0,.625),(3,-.0625)))
        shifts=[Fraction(-300),Fraction(-150),Fraction(0),Fraction(150)]
        paths=[AliasPath(f,((s1,f),(s2,f)),f==0) for f in shifts]
        lo,hi=Fraction(150),Fraction(151)
        bound,_=bound_population(paths,lo,hi,include=lambda p:not p.direct,
                         limit='1e-10',evaluate=lambda term,l,h:
                          bounds_single(term[0],term[1],l,h)[1])
        for f in (lo,(lo+hi)/2,hi):
            total=iv.mpf(0)
            for path in paths:
                if path.direct:continue
                term=iv.mpf(1)
                for stage,offset in path.terms:
                    p=TrigPoly(stage.taps,Fraction(0))
                    fn=abs(f+offset)/stage.input_hz
                    term*=direct_reference(p,fn,fn)[2]
                total+=term
            self.assertTrue(bool(total.b<=bound.b))

    def test_long_real_source_fir_encloses_direct_analytic_reference(self):
        # Exercise the actual bound, not only synthetic symmetric filters.
        from p15_src_stagewise_alias_proof import make_src_stages
        _,op=verify_pair(DEFAULT/'88200-192000',88200,192000)
        stage=next(s for s in make_src_stages(op) if len(s.taps)==4160)
        self.assertEqual(stage.taps[0][1],0.0)  # exact unpaired zero
        poly=TrigPoly(stage.taps,Fraction(0))
        lo=Fraction(1374,10000)
        hi=lo+Fraction(1,10000000)
        fast=fixed_symmetric_magnitude_bounds(poly,lo,hi)
        for f in (lo,(lo+hi)/2,hi):
            ref=direct_reference(poly,f,f)
            self.assertTrue(bool(fast[0].a<=ref[0].a))
            self.assertTrue(bool(fast[1].b>=ref[1].b))

    def test_one_sided_rational_branch_splits(self):
        _,op=verify_pair(DEFAULT/'176400-48000',176400,48000)
        l,h=Fraction(0),Fraction(1000)
        whole=complete_paths('master128',op,l,h)
        self.assertIsInstance(whole,BranchBoundary)
        self.assertEqual(whole.at,600)
        for low,high in ((l,whole.at),(whole.at,h)):
            sub=complete_paths('master128',op,low,high)
            self.assertEqual(len(sub),4704)
            self.assertEqual(sum(x.direct for x in sub),1)
            for k in (0,1,2):
                # The relevant analytic response at a branch's one-sided
                # endpoint is covered by the interval carrying that branch.
                p=sub[k]
                stage,shift=p.terms[0]
                bounded=bounds_single(stage,shift,low,high)
                self.assertGreaterEqual(float(bounded[1].b),0)


if __name__=='__main__':unittest.main()

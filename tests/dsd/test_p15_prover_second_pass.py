#!/usr/bin/env python3
"""Second-pass independent enclosure, path-population, and deadline tests."""
from __future__ import annotations

from fractions import Fraction
import random
import signal
import time
import unittest

from mpmath import iv
from p15_src_continuum_bounds import TrigPoly, magnitude_bounds as independent_complex
from p15_src_fixed_interval import (
    _Q, _derivative_weights, _multiply_ratio, fixed_symmetric_magnitude_bounds)
from p15_src_stagewise_continuum import complete_paths, BranchBoundary
from p15_src_stagewise_alias_proof import make_native_stages, make_src_stages, branches
from p15_src_capture_matrix import verify_pair, DEFAULT
from p15_src_complete_aliases import native_profile, alias_families
from p15_src_branch_bound import bound_population
from p15_src_stagewise_continuum import AliasPath, bounds_single
from p15_src_stagewise_alias_proof import FIRStage
from p15_full_band_campaign import interval_deadline, IntervalBudgetExpired


class ExactDerivativeWeights(unittest.TestCase):
    def test_exact_rational_identity_and_cache(self):
        poly=TrigPoly(((-13,0.125),(-7,-2**-40),(-1,0.375),
                       (0,-0.5),(1,0.375),(7,-2**-40),(13,0.125)),Fraction(0))
        weights=_derivative_weights(poly,12)
        self.assertIs(weights,_derivative_weights(poly,12))
        for k, items in weights:
            val=dict(poly.taps)[k]
            for j,(n,d) in enumerate(items):
                self.assertEqual(Fraction(n,d),2*Fraction.from_float(val)*k**j)

    def test_directed_signed_rational_multiplication(self):
        rng=random.Random(0xF15)
        for _ in range(300):
            a=Fraction(rng.randrange(-10000,10000),rng.randrange(1,10000))
            b=Fraction(rng.randrange(-10000,10000),rng.randrange(1,10000))
            lo=a.numerator*_Q//a.denominator
            hi=-((-a.numerator*_Q)//a.denominator)
            result=_multiply_ratio((lo,hi),b.numerator,b.denominator)
            self.assertLessEqual(Fraction(result[0],_Q),a*b)
            self.assertGreaterEqual(Fraction(result[1],_Q),a*b)

    def test_optimized_encloses_independent_direct_complex_at_dense_adversarial_points(self):
        rng=random.Random(0x177)
        for size in (3,27,143,701):
            taps={0:0.5 if size%3 else -0.5}
            for k in range(1,size+1):
                x=rng.choice((-1,1))*rng.randrange(1,10000)*2**-35
                taps[k]=taps[-k]=x
            poly=TrigPoly(tuple(sorted(taps.items())),Fraction(0))
            for lo,hi in ((Fraction(0),Fraction(1,10**7)),
                          (Fraction(1,4)-Fraction(1,10**6),Fraction(1,4)+Fraction(1,10**6)),
                          (Fraction(1,2)-Fraction(1,10**7),Fraction(1,2))):
                b=fixed_symmetric_magnitude_bounds(poly,lo,hi,order=8)
                for f in (lo,(2*lo+hi)/3,(lo+hi)/2,(lo+2*hi)/3,hi):
                    independent=independent_complex(poly,f,f,order=8)
                    self.assertTrue(bool(b[0].a<=independent[0].a))
                    self.assertTrue(bool(b[1].b>=independent[1].b))


class CollidingNativeLattice(unittest.TestCase):
    def test_source_bound_factorized_routes_cover_every_primitive_family(self):
        for profile,inp,out,want_paths,want_unique in (
            ('master64',88200,48000,9408,4704),
            ('master128',176400,96000,9408,4704),
            ('master256',176400,96000,18816,9408),
        ):
            with self.subTest(profile=profile):
                _,op=verify_pair(DEFAULT/f'{inp}-{out}',inp,out)
                paths=complete_paths(profile,op,Fraction(0),Fraction(1),max_paths=20000)
                self.assertIsInstance(paths,tuple)
                self.assertEqual(len(paths),want_paths)
                self.assertEqual(len({p.upstream_shift for p in paths}),want_unique)
                self.assertEqual(sum(p.direct for p in paths),1)
                native,*_=native_profile(profile)
                freq=Fraction(1,2)
                reference={fam.source_hz-freq for fam in alias_families(native,op,freq)}
                self.assertEqual({p.upstream_shift for p in paths},reference)
                self.assertEqual(len(paths),len(make_native_stages(profile)) and
                    __import__('math').prod(s.M for s in
                       make_native_stages(profile)+make_src_stages(op)))

    def test_triangle_bound_cannot_discard_coherent_duplicate_paths(self):
        a=FIRStage('identity',100,Fraction(100),1,1,((0,1.0),))
        paths=[AliasPath(Fraction(1),((a,Fraction(1)),),False),
               AliasPath(Fraction(1),((a,Fraction(1)),),False),
               AliasPath(Fraction(2),((a,Fraction(2)),),False)]
        upper,n=bound_population(paths,Fraction(0),Fraction(1),include=lambda p:True,
                                 limit='1e-12',evaluate=lambda term,l,h:
                                 bounds_single(term[0],term[1],l,h)[1],
                                 use_terminal_saturation=False)
        self.assertTrue(bool(upper.b>=iv.mpf(3).b))
        self.assertGreaterEqual(n,2)
        # The default may stop after one terminal upper reaches the limit;
        # its complete bound must still include both duplicate contributions
        # and the remaining unevaluated path. Count three, irrespective of
        # how many individual FIR evaluations were needed to enclose them.
        early,_=bound_population(paths,Fraction(0),Fraction(1),include=lambda p:True,
                                 limit='1e-12',evaluate=lambda term,l,h:
                                 bounds_single(term[0],term[1],l,h)[1])
        self.assertTrue(bool(early.b>=iv.mpf(3).b))


class RepeatDeadline(unittest.TestCase):
    def test_first_swallowed_expiration_is_redelivered(self):
        caught=0
        started=time.monotonic()
        with interval_deadline(0.012):
            while caught<2 and time.monotonic()-started<0.30:
                try:
                    # Sleep is interrupted by the raised signal exception;
                    # unlike a hot loop this leaves normal scheduling room
                    # between deliveries and avoids an exception in teardown.
                    time.sleep(0.03)
                except IntervalBudgetExpired:
                    caught+=1
                    if caught>=2:
                        signal.setitimer(signal.ITIMER_REAL,0)
                        break
        self.assertGreaterEqual(caught,2,'one-shot delivery must not be suppressible')
        self.assertLess(time.monotonic()-started,0.31)


if __name__=='__main__':unittest.main()

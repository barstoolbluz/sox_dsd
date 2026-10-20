"""Independent analytic/mutation regression for signed-grid recurrence."""
from __future__ import annotations
import random,unittest
from fractions import Fraction as F
from p15_r7_fast_fir import *
from p15_r5_integer_spectral import certify_fir,IntervalRefusal
from p15_r6_exact_composite import ExactRefusal


class FastFIRTests(unittest.TestCase):
    def test_unit_and_zero_at_all_frequencies(self):
        for lo,hi in ((F(0),F(1,2)),(F(1,7),F(3,11)),(F(1,4),F(1,4))):
            self.assertEqual(certify_fir_fast(((0,1.),),lo,hi).lower(),F(1))
            self.assertEqual(certify_fir_fast(((0,1.),),lo,hi).upper(),F(1))
            self.assertEqual(certify_fir_fast(((0,0.),),lo,hi).upper(),F(0))

    def test_triangle_encloses_known_exact_extrema(self):
        taps=((-1,0.5),(1,0.5))  #  cos(2*pi*f)
        for lo,hi in ((F(0),F(1,2)),(F(0),F(1,4)),(F(1,4),F(1,2))):
            b=certify_fir_fast(taps,lo,hi)
            self.assertLessEqual(b.lower(),F(0) if lo<=F(1,4)<=hi else F(1))
            self.assertGreaterEqual(b.upper(),F(1))

    def test_signs_high_index_and_phase_shift(self):
        taps=((-16384,0.25),(-2,-0.375),(3,0.125),(32767,0.5))
        for c in (F(0),F(1,3)):
            a=certify_fir(taps,F(1,17),F(1,16),center=c)
            b=certify_fir_fast(taps,F(1,17),F(1,16),center=c)
            # Independent outward algorithms may differ but always overlap.
            self.assertLessEqual(a.lower(),b.upper())
            self.assertLessEqual(b.lower(),a.upper())

    def test_ball_signed_recurrence_exact_unit_phases(self):
        si,co=sincos(F(1,4))
        z=ball_from_rect((co,si))
        for n in (-32767,-257,-17,-4,-1,0,1,4,19,256,32768):
            v=ball_rectangle(ball_power(z if n>=0 else ball_conj(z),abs(n)))
            expected=sincos(F(n,4))
            self.assertLessEqual(v[0][0],expected[1][1])
            self.assertLessEqual(expected[1][0],v[0][1])
            self.assertLessEqual(v[1][0],expected[0][1])
            self.assertLessEqual(expected[0][0],v[1][1])
            # Error grows at most polynomially, unlike repeated rectangles.
            self.assertLess(ball_power(z,abs(n))[2],10**9)

    def test_many_seeded_sparse_sign_cancellation(self):
        rng=random.Random(271828)
        for _ in range(40):
            ks=sorted(rng.sample(range(-100,100),rng.randint(2,12)))
            taps=tuple((k,rng.randrange(-32768,32769)/65536.) for k in ks)
            lo=F(rng.randrange(0,15),32)
            hi=min(F(1,2),lo+F(rng.randrange(0,6),128))
            a=certify_fir(taps,lo,hi,order=6)
            b=certify_fir_fast(taps,lo,hi,order=6)
            self.assertLessEqual(a.lower(),b.upper())
            self.assertLessEqual(b.lower(),a.upper())
            # The independent exact midpoint interval is inside both methods.
            mid=(lo+hi)/2
            pa=certify_fir(taps,mid,mid,order=4)
            self.assertLessEqual(b.lower(),pa.upper())
            self.assertGreaterEqual(b.upper(),pa.lower())

    def test_refuse_invalid_inputs(self):
        for bad in (((0,float('nan')),),((0,0.0),(0,1.0))):
            with self.assertRaises(IntervalRefusal):certify_fir_fast(bad,F(0),F(1,8))
        with self.assertRaises(IntervalRefusal):certify_fir_fast(((0,1.0),),F(-1),F(0))
        with self.assertRaises(IntervalRefusal):ball_power((GRID,0,0),-1)

    def test_ball_multiplication_encloses_known_unit(self):
        si,co=sincos(F(1,6))
        z=ball_from_rect((co,si))
        product=ball_rectangle(ball_mul(z,ball_conj(z)))
        self.assertTrue(product[0][0]<=GRID<=product[0][1])
        self.assertTrue(product[1][0]<=0<=product[1][1])

    def test_prod_4khz_prior_rectangle_dependency_regression(self):
        from p15_src_capture_matrix import verify_pair,DEFAULT
        from p15_src_stagewise_alias_proof import make_src_stages
        _,op=verify_pair(DEFAULT/'88200-44100',88200,44100)
        stage=make_src_stages(op)[-1]
        f=F(4000,88200)
        fast=certify_fir_fast(stage.taps,f,f,order=8)
        independent=certify_fir(stage.taps,f,f,order=8)
        self.assertGreater(fast.lower(),F(999,1000))
        self.assertLess(fast.upper(),F(1001,1000))
        self.assertLessEqual(fast.lower(),independent.upper())
        self.assertGreaterEqual(fast.upper(),independent.lower())

if __name__=='__main__':unittest.main()

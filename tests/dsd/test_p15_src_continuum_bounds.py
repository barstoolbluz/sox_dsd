"""Proof-oriented regression checks, including extrema invisible to sparse grids."""
import unittest
from p15_src_continuum_bounds import TrigPoly, certify, db_band, BadWitness


def poly(**pairs):
    return TrigPoly.from_hex({int(k[1:]): float(v).hex() for k,v in pairs.items()})


class ContinuumBounds(unittest.TestCase):
    def test_constant_unity_full_band(self):
        p=poly(k0=1)
        lo,hi=db_band()
        got=certify((p,),0,.5,amplitude_min=lo,amplitude_max=hi)
        self.assertEqual(got['status'],'PASS',got)

    def test_stopband_has_proven_continuum_not_sampled_grid(self):
        p=poly(k0=5e-10, k4=-2e-10)
        got=certify((p,),0.1,.5,amplitude_max=1e-8)
        self.assertEqual(got['status'],'PASS',got)

    def test_between_sample_worst_case_is_detected(self):
        # At 0 and 1/2 this transfer is identically zero. Its magnitude at
        # 1/4 is 1, so tests that inspect only endpoints would falsely PASS.
        p=poly(k0=.5,k2=-.5)
        got=certify((p,),0,.5,amplitude_max=.01)
        self.assertEqual(got['status'],'FAIL',got)

    def test_coherent_sum_is_not_quadrature(self):
        p=poly(k0=7e-9)
        got=certify((p,p),0,.5,amplitude_max=1e-8)
        self.assertEqual(got['status'],'FAIL',got)

    def test_known_unsafe_pass_gain_fails(self):
        p=poly(k0=1.00003)
        lo,hi=db_band()
        self.assertEqual(certify((p,),0,.5,
                                 amplitude_min=lo,amplitude_max=hi)['status'],'FAIL')

    def test_budget_exhaustion_is_not_success(self):
        p=poly(k0=1,k1=.1)
        got=certify((p,),0,.5,amplitude_max=1.2,max_nodes=1)
        self.assertEqual(got['status'],'OPEN',got)

    def test_invalid_witness_and_alias_contract_fail_closed(self):
        with self.assertRaises(BadWitness):
            TrigPoly.from_hex({0:'nan'})
        with self.assertRaises(BadWitness):
            certify((poly(k0=1),poly(k0=1)),0,.5,amplitude_min=.1,amplitude_max=2)


if __name__=='__main__':unittest.main()

"""Adversarial unit tests for exact R6 composite proof kernel.

Analytic fixtures are mathematics tests and are NOT source-bound P15 PASSes.
"""
from __future__ import annotations
from fractions import Fraction as F
from math import isfinite
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import shutil
import unittest

from p15_r5_exact_trig import GRID,pi_interval,sincos,TrigRefusal
from p15_r5_integer_spectral import certify_fir,IntervalRefusal
from p15_r6_exact_policy import db_pass_bounds,ln10_bounds
from p15_r6_exact_composite import (ExactComposite,ExactRefusal,Split,
                                     all_paths,frac)
from p15_src_stagewise_alias_proof import FIRStage
from p15_src_stagewise_continuum import complete_paths
from p15_src_capture_matrix import DEFAULT,verify_pair
from p15_src_bound_operator import UnboundOperator
from p15_full_band_campaign import canonical_plan,digest
from p15_r6_witness import RECEIPTS, canonical_receipt


def fixture(stage):
    c=ExactComposite.__new__(ExactComposite)
    c.profile='ANALYTIC-FIXTURE-NOT-P15'
    c.op=SimpleNamespace(output_hz=int(stage.output_hz),U=1)
    c.stages=(stage,);c.native=stage.input_hz;c.R=stage.input_hz
    c.max_evaluations=64;c.max_halfband_nodes=256;c.bounds_cache={}
    c.moments_cache={};c.halfbands={};c.evaluations=0
    c.difference_uses=0;c.alias_frontier=0;c.global_caps_used=0
    return c


class ExactR6Test(unittest.TestCase):
    def test_pi_machin_enclosure(self):
        lo,hi=pi_interval()
        self.assertLess(F(3),lo);self.assertLess(hi,F(22,7))
        self.assertLess(hi-lo,F(1,2**310))

    def test_integer_trig_special_angles_and_periodicity(self):
        for q in (F(0),F(1,4),F(1,2),F(3,4),F(-1,2),F(-1000001,4)):
            s,c=sincos(q)
            s2,c2=sincos(q+37)
            self.assertLessEqual(s[0],s2[1]);self.assertGreaterEqual(s[1],s2[0])
            self.assertLessEqual(c[0],c2[1]);self.assertGreaterEqual(c[1],c2[0])
        s,c=sincos(F(1,4))
        self.assertLessEqual(s[0],GRID);self.assertGreaterEqual(s[1],GRID)
        self.assertLessEqual(c[0],0);self.assertGreaterEqual(c[1],0)
        with self.assertRaises(TrigRefusal):sincos(F(1,2**8200))

    def test_signed_cancellation_and_nyquist_exact(self):
        # At exactly 1/2, 1+z is identically 0, within integer enclosure.
        plus=certify_fir(((-3,1.0),(-2,1.0)),F(1,2),F(1,2))
        self.assertLessEqual(plus.lower(),F(0))
        self.assertLess(plus.upper(),F(1,10**16))
        minus=certify_fir(((-1,1.0),(0,-1.0)),F(1,2),F(1,2))
        self.assertLessEqual(minus.lower(),F(2));self.assertGreaterEqual(minus.upper(),F(2))

    def test_rigorous_degenerate_polynomial_interval(self):
        coeff=((-1,0.25),(0,0.5),(1,0.25))
        c=certify_fir(coeff,F(0),F(0))
        self.assertLessEqual(c.lower(),F(1));self.assertGreaterEqual(c.upper(),F(1))
        self.assertLess(c.upper()-c.lower(),F(1,2**250))

    def test_threshold_inwardness(self):
        lo,hi=db_pass_bounds()
        self.assertLess(lo[0],lo[1]);self.assertLess(lo[1],1)
        self.assertGreater(hi[0],1);self.assertLess(hi[0],hi[1])
        self.assertLess(ln10_bounds()[1]-ln10_bounds()[0],F(1,2**320))

    def test_original_0_0001db_boundary_not_relaxed(self):
        s1=FIRStage('synthetic',100,F(100),1,1,((0,1.0),))
        good=fixture(s1).leaf(F(0),F(0),'pass',40)
        self.assertTrue(good['safe'])
        s2=FIRStage('synthetic',100,F(100),1,1,((0,1.00002),))
        self.assertFalse(fixture(s2).leaf(F(0),F(0),'pass',40)['safe'])
        s3=FIRStage('synthetic',100,F(100),1,1,((0,0.99997),))
        self.assertFalse(fixture(s3).leaf(F(0),F(0),'pass',40)['safe'])

    def test_analytic_two_branch_reconstruction_and_alias(self):
        s=FIRStage('synthetic-halfband',100,F(50),1,2,
                   ((-1,0.25),(0,0.5),(1,0.25)))
        c=fixture(s)
        families=all_paths((s,),100,50,1,F(0),F(0))
        self.assertEqual(len(families),2)
        self.assertEqual(sum(p.direct for p in families),1)
        self.assertTrue(c.leaf(F(0),F(0),'pass',45)['safe'])
        self.assertTrue(c.leaf(F(0),F(0),'stop',45)['safe'])
        self.assertGreaterEqual(c.global_caps_used,0)

    def test_halfband_shortcut_refuses_perturbed_symmetry(self):
        valid=FIRStage('halfband',100,F(50),1,2,
                       ((-1,0.25),(0,0.5),(1,0.25)))
        invalid=FIRStage('bad-even-tap',100,F(50),1,2,
                       ((-2,0.125),(-1,0.25),(0,0.5),(1,0.25),(2,0.125)))
        self.assertIsNotNone(fixture(valid)._odd_halfband(0))
        self.assertIsNone(fixture(invalid)._odd_halfband(0))
        self.assertIsNone(fixture(invalid).halfband_cap(0))

    def test_halfband_complete_quarter_continuum_bound(self):
        c=fixture(FIRStage('halfband',100,F(50),1,2,
                     ((-1,0.25),(0,0.5),(1,0.25))))
        bound,nodes=c.halfband_cap(0)
        self.assertGreater(nodes,1)
        self.assertGreaterEqual(bound,F(1))
        self.assertLess(bound,F(5000001,5000000))

    def test_exact_signed_finite_difference_bound(self):
        s=FIRStage('signed-diff',100,F(100),1,1,((0,1.0),(1,-1.0)))
        c=fixture(s)
        upper=c._difference_upper(0,F(1,2),F(1,2))
        self.assertGreaterEqual(upper,F(2))
        self.assertLess(upper,F(3))

    def test_refuse_nonfinite_and_repeated_taps(self):
        s=FIRStage('bad',100,F(100),1,1,((0,1.0),(0,1.0)))
        with self.assertRaises((ExactRefusal,IntervalRefusal)):fixture(s).leaf(F(1),F(1),'pass',40)
        with self.assertRaises(ExactRefusal):frac(float('inf'))

    def test_stage_clock_or_missing_native_family_refused(self):
        stage=FIRStage('malformed-clock',100,F(51),1,2,((0,1.0),))
        with self.assertRaises(ExactRefusal):
            all_paths((stage,),100,51,1,F(1),F(1))
        s=FIRStage('decimation',100,F(50),1,2,((0,1.0),))
        with self.assertRaises(ExactRefusal):
            all_paths((s,),150,50,1,F(1),F(1))

    def test_canonical_campaign_exact_inventory(self):
        jobs=canonical_plan(1000)
        self.assertEqual(len(jobs),11516)
        self.assertEqual(len({digest(x) for x in jobs}),11516)
        self.assertEqual(len({x['cell_id'] for x in jobs}),72)
        self.assertEqual(sum(x['mode']=='pass' for x in jobs),2850)

    def test_source_stage_snapshot_mutation_rejected(self):
        base=DEFAULT/'88200-96000'
        with TemporaryDirectory() as tmp:
            dest=Path(tmp)
            for name in ('stage-snapshot.json','operator-binding.json'):
                shutil.copy2(base/name,dest/name)
            snapshot=dest/'stage-snapshot.json'
            snapshot.write_bytes(snapshot.read_bytes()+b' ')
            with self.assertRaises((UnboundOperator,ValueError)):
                verify_pair(dest,88200,96000)

    def test_source_bound_real_alias_lattice_and_collision(self):
        _,op=verify_pair(DEFAULT/'88200-384000',88200,384000)
        engine=ExactComposite('master64',op,max_evaluations=1)
        for a,b in ((F(0),F(0)),(F(1000),F(1001)),(F(10000),F(12000))):
            got=all_paths(engine.stages,engine.native,op.output_hz,op.U,a,b)
            prior=complete_paths('master64',op,a,b)
            if isinstance(got,Split):
                self.assertEqual(got.at,prior.at)
            else:
                self.assertEqual(len(got),len(prior))
                self.assertEqual({p.source_shift for p in got},
                                 {p.upstream_shift for p in prior})
                self.assertGreaterEqual(len(got),len({p.source_shift for p in got}))

    def test_immutable_original_receipt_identity(self):
        jobs=canonical_plan(1000)
        path=RECEIPTS/(digest(jobs[0])+'.json')
        self.assertEqual(canonical_receipt(path),jobs[0])
        with TemporaryDirectory() as temp:
            altered=Path(temp)/path.name
            altered.write_bytes(path.read_bytes())
            with self.assertRaises(ExactRefusal):canonical_receipt(altered)



# Separate mock-bound payload mutations: these check verifier mechanics, not
# source-bound mathematical qualification of any production rate cell.
class WitnessMutationTest(unittest.TestCase):
    def _fixture(self):
        from p15_r6_witness import check_summary_candidate
        import p15_r6_witness as witness
        from unittest.mock import patch
        stage=FIRStage('identity-analytical',100,F(100),1,1,((0,1.0),))
        job={'mode':'pass','source_s':40,'lo':'1','hi':'2','profile':'ANALYTIC-NOT-P15'}
        binding={'source':'ANALYTIC-ONLY','original_receipt_name':'mock.json'}
        op=SimpleNamespace(output_hz=100,U=1)
        leaf=fixture(stage).leaf(F(1),F(2),'pass',40)
        leafrow={'lo':'1','hi':'2',
                 'bounds':__import__('p15_r6_exact_composite').exact_json(
                          {k:v for k,v in leaf.items() if k!='safe'})}
        proof={'schema':'P15/R6/source-bound-integer-composite/1',
               'binding':binding,'job':job,'leaves':[leafrow]}
        def source_binding(_):return job,op,dict(source='ANALYTIC-ONLY',original_receipt_name='mock.json')
        def engine(_job,_op,max_fir_evals):return fixture(stage)
        return proof,source_binding,engine

    def test_synthetic_replay_then_corrupt_aggregate(self):
        import p15_r6_witness as w
        from unittest.mock import patch
        proof,bound,eng=self._fixture()
        with patch.object(w,'input_binding',side_effect=bound),patch.object(w,'new_engine',side_effect=eng):
            proof['independent_check']=w.check_summary_candidate(proof)
            self.assertEqual(w.check_proof(proof)['status'],'PASS-LOCAL-R6-INDEPENDENT')
            proof['leaves'][0]['bounds']['total_upper']='0'
            with self.assertRaises(ExactRefusal):w.check_proof(proof)

    def test_synthetic_coverage_gap_and_identity_refusal(self):
        import p15_r6_witness as w
        from unittest.mock import patch
        proof,bound,eng=self._fixture()
        with patch.object(w,'input_binding',side_effect=bound),patch.object(w,'new_engine',side_effect=eng):
            proof['independent_check']=w.check_summary_candidate(proof)
            proof['leaves'][0]['lo']='3/2'
            with self.assertRaises(ExactRefusal):w.check_proof(proof)
            proof['leaves'][0]['lo']='1'
            proof['binding']['source']='TAMPERED'
            with self.assertRaises(ExactRefusal):w.check_proof(proof)

    def test_synthetic_midpoint_leaf_omission_refused(self):
        import p15_r6_witness as w
        from unittest.mock import patch
        proof,bound,eng=self._fixture()
        with patch.object(w,'input_binding',side_effect=bound),patch.object(w,'new_engine',side_effect=eng):
            proof['independent_check']=w.check_summary_candidate(proof)
            proof['leaves']=[]
            with self.assertRaises(ExactRefusal):w.check_proof(proof)

if __name__=='__main__':
    unittest.main()

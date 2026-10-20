#!/usr/bin/env python3
"""Adversarial, source-bound R9 uniform stop certification tests."""
from fractions import Fraction as F
from pathlib import Path
import hashlib
import json
import unittest

from p15_r9_uniform_stop import (CELL,NATIVE_TARGET,source_context,
    prove_native_global_caps,prove_src_global_cap,folded_range,fdist,
    family_ks,verify_native_leaf,ExactRefusal)
from p15_r9_src_global_family import (all_profile_cells,stage_global_alias_cap,
    family_src_proofs,STOP_LIMIT)
from p15_full_band_campaign import canonical_plan

HERE=Path(__file__).resolve().parent
WITNESS=HERE/'results/P15_R9_UNIFORM_STOP_2026-10-19/uniform_native_stop.json'

class R9UniformMathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.job,cls.op,cls.binding,cls.e=source_context()
        cls.caps,cls.last=prove_native_global_caps(cls.e)
        cls.raw=json.loads(WITNESS.read_text())

    def test_certificate_source_and_method_hashes(self):
        self.assertEqual(self.raw['status'],'CANDIDATE')
        from p15_r9_uniform_stop import method_identity
        self.assertEqual(self.raw['method'],method_identity())
        self.assertEqual(self.raw['source_binding'],self.binding)
        self.assertEqual(self.raw['native_group_target'],str(NATIVE_TARGET))

    def test_exact_continuum_cover_without_gap(self):
        cursor=F(0);edges=[]
        for leaf in self.raw['leaves']:
            a,b=F(leaf['lo']),F(leaf['hi'])
            self.assertEqual(a,cursor)
            self.assertLess(a,b)
            cursor=b
            if b==80000:edges.append(b)
        self.assertEqual(len(edges),1)
        self.assertEqual(cursor,F(88200))
        self.assertEqual(len(self.raw['leaves']),179)

    def test_native_family_harmonic_population(self):
        before=family_ks(self.e,F(79500),F(80000))
        after=family_ks(self.e,F(80000),F(80500))
        self.assertEqual(len(before),63)
        self.assertEqual(len(after),64)
        self.assertEqual(set(after)-set(before),{0})

    def test_folded_range_across_both_extrema(self):
        a,b=folded_range(F(-7,4),F(7,4),1)
        self.assertEqual((a,b),(F(0),F(1,2)))
        a,b=folded_range(F(1,8),F(3,8),1)
        self.assertEqual((a,b),(F(1,8),F(3,8)))
        a,b=folded_range(F(-1,4),F(1,4),1)
        self.assertEqual((a,b),(F(0),F(1,4)))
        self.assertEqual(fdist(F(-3,2)),F(1,2))

    def test_independent_recalculation_first_native_leaf(self):
        leaf=self.raw['leaves'][0]
        u=verify_native_leaf(self.e,self.caps,leaf)
        self.assertLessEqual(u,F(leaf['native_upper']))
        self.assertLess(F(leaf['native_upper']),NATIVE_TARGET)

    def test_detect_corrupt_transfer_upper(self):
        leaf=dict(self.raw['leaves'][0]);leaf['native_upper']='0'
        with self.assertRaisesRegex(ExactRefusal,'not conservative'):
            verify_native_leaf(self.e,self.caps,leaf)

    def test_detect_missing_native_harmonic(self):
        leaf=dict(self.raw['leaves'][0]);leaf['stages']=leaf['stages'][:-1]
        with self.assertRaisesRegex(ExactRefusal,'missing native source family'):
            verify_native_leaf(self.e,self.caps,leaf)

    def test_detect_duplicate_native_stage(self):
        leaf=dict(self.raw['leaves'][0]);leaf['stages']=[list(x) for x in leaf['stages']]
        leaf['stages'][0]=[leaf['stages'][0][0],[0,0]]
        with self.assertRaisesRegex(ExactRefusal,'invalid refined stage selection'):
            verify_native_leaf(self.e,self.caps,leaf)

    def test_src_bound_is_below_limit_for_384k(self):
        cap,_=prove_src_global_cap(self.e)
        self.assertLess(cap*NATIVE_TARGET,STOP_LIMIT)
        self.assertLess(cap,F(7153,1000))

    def test_family_counts_cover_8_cells(self):
        cells=all_profile_cells()
        self.assertEqual(len(cells),8)
        self.assertEqual(sum(sum(x['mode']=='stop' for x in v) for v in cells.values()),958)

    def test_family_bounds_have_exact_five_passes(self):
        proof=family_src_proofs(native_status='CANDIDATE_UNREPLAYED')
        passed=[r for r in proof['cells'] if r['uniform_inequality_pass']]
        self.assertEqual(len(passed),5)
        self.assertEqual(sum(r['canonical_stop_jobs'] for r in passed),790)
        self.assertFalse(any(r['mathematically_qualified'] for r in proof['cells']))
        for r in passed:
            self.assertLess(F(r['composite_stop_upper']),STOP_LIMIT)

    def test_reject_unreviewed_even_multiplicity(self):
        class E:
            stages=[type('S',(),{'L':1,'M':4,'input_hz':100,'output_hz':F(25)})()]
            def l1(self,i):return F(1)
            def halfband_cap(self,i):return None
        with self.assertRaisesRegex(ExactRefusal,'unreviewed'):
            stage_global_alias_cap(E(),0)

if __name__=='__main__':unittest.main()

"""Regression coverage for exact branch transitions, bounded dispatch and archives."""
from __future__ import annotations
from collections import Counter
from fractions import Fraction
import json
import math
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

from mpmath import iv
from p15_src_capture_matrix import verify_pair,DEFAULT as ACTIVE_STAGE_ROOT
from p15_src_stagewise_continuum import (BranchBoundary,complete_paths,
    certificate,bounds_single)
from p15_src_continuum_bounds import (TrigPoly,magnitude_bounds as reference_bounds)
from p15_src_interval_recurrence import magnitude_bounds as accelerated_bounds
from p15_src_branch_bound import bound_population,exact_l1_gain
from p15_src_stagewise_alias_proof import FIRStage
from p15_full_band_campaign import (interval_deadline,IntervalBudgetExpired,
    run_campaign,receipt_path,import_archived_partial,ARCHIVED_PARTIAL)
from p15_boundary_schedule_replay import DEFAULT as ROUTING_REPLAY
from p15_physical_archive_review import review as physical_review,ArchivedEvidenceError,ARCHIVE

SNAPSHOTS=ACTIVE_STAGE_ROOT


class ExactBranchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _,cls.operator=verify_pair(SNAPSHOTS/'176400-48000',176400,48000)

    def test_non_dyadic_transition_is_split_exactly(self):
        lo,hi=Fraction(0),Fraction(1000)
        boundary=complete_paths('master128',self.operator,lo,hi)
        self.assertIsInstance(boundary,BranchBoundary)
        self.assertEqual(boundary.at,Fraction(600))
        self.assertNotIn(Fraction(600),{lo+Fraction(hi-lo,2**i)
                                           for i in range(1,40)})
        left=complete_paths('master128',self.operator,lo,boundary.at)
        right=complete_paths('master128',self.operator,boundary.at,hi)
        self.assertEqual(len(left),4704)
        self.assertEqual(len(right),4704)
        self.assertEqual({p.upstream_shift for p in left},
                         {p.upstream_shift for p in right})
        self.assertEqual(sum(p.direct for p in left),1)
        self.assertEqual(sum(p.direct for p in right),1)

    def test_both_sides_of_multiple_inverse_fold_transitions(self):
        # Output=192k from DSD64 has several fold changes, including one
        # to the LEFT of the midpoint.  A right-only crossover search
        # previously refused these otherwise stationary exact partitions.
        _,op=verify_pair(SNAPSHOTS/'88200-192000',88200,192000)
        todo=[(Fraction(0),Fraction(1000))]
        boundaries=[];leaves=[]
        while todo:
            lo,hi=todo.pop()
            result=complete_paths('master64',op,lo,hi)
            if isinstance(result,BranchBoundary):
                self.assertLess(lo,result.at)
                self.assertLess(result.at,hi)
                boundaries.append(result.at)
                todo.extend(((lo,result.at),(result.at,hi)))
            else:
                self.assertEqual(len(result),4704)
                self.assertEqual(sum(p.direct for p in result),1)
                leaves.append((lo,hi))
        self.assertEqual(set(boundaries),{Fraction(300),Fraction(600),Fraction(900)})
        self.assertEqual(len(leaves),4)
        self.assertEqual(sorted(leaves),[(Fraction(0),Fraction(300)),
            (Fraction(300),Fraction(600)),(Fraction(600),Fraction(900)),
            (Fraction(900),Fraction(1000))])

    def test_subdivision_is_work_bounded(self):
        # With node budget one, a rational branch split MUST return OPEN.
        result=certificate('master128',self.operator,'0','1000',max_nodes=1)
        self.assertEqual(result['status'],'OPEN')
        self.assertEqual(result['reason'],'subdivision_node_budget')
        self.assertEqual(result['exact_branch_splits'],1)
        self.assertEqual(result['nodes_examined'],1)


class IntervalAlgebraTests(unittest.TestCase):
    def test_complex_rotation_recurrence_encloses_reference(self):
        samples=[
            (TrigPoly(((0,1.0),(3,-.125),(7,.03125)),Fraction(0)),
             Fraction(1,29),Fraction(5,29)),
            (TrigPoly(tuple((k,math.ldexp((-1)**k, -15)) for k in
                             range(-90,91)),Fraction(1,3)),
             Fraction(9,50),Fraction(9,50)+Fraction(1,10000)),
            (TrigPoly(((0,1.),(400,-.5), (401,.1)),Fraction(1,2)),
             Fraction(0),Fraction(1,500)),
        ]
        for poly,lo,hi in samples:
            for order in (2,4,8):
                with self.subTest(length=len(poly.taps),order=order):
                    old=reference_bounds(poly,lo,hi,order=order)
                    new=accelerated_bounds(poly,lo,hi,order=order)
                    # Two independent outward interval implementations.
                    # Bounds can differ, but both enclose the midpoint and
                    # the original bound endpoints at normal float scale.
                    for result in (old,new):
                        self.assertTrue(bool(result[0].a<=result[2].a))
                        self.assertTrue(bool(result[1].b>=result[2].b))
                    self.assertAlmostEqual(float(old[1].b),float(new[1].b),places=13)
                    self.assertAlmostEqual(float(old[0].a),float(new[0].a),places=13)

    def test_global_l1_bound_includes_unexpanded_aliases(self):
        s1=FIRStage('a',1000,Fraction(1000),1,1,((0,.75),))
        s2=FIRStage('b',1000,Fraction(1000),1,1,((0,.5),))
        from p15_src_stagewise_continuum import AliasPath
        paths=[AliasPath(Fraction(k),((s1,Fraction(k)),(s2,Fraction(k))),False)
               for k in range(4)]
        count=Counter()
        def evaluate(term,lo,hi):
            count[term[0].kind]+=1
            return iv.mpf(term[0].taps[0][1]).b
        upper,used=bound_population(paths,Fraction(0),Fraction(1),
            include=lambda p:True,limit='2',evaluate=evaluate)
        self.assertGreaterEqual(float(upper.b),1.5)
        self.assertEqual(used,0)  # strict upper sufficient; no term omitted
        exact,used=bound_population(paths,Fraction(0),Fraction(1),
            include=lambda p:True,limit='1e-8',evaluate=evaluate)
        self.assertGreaterEqual(float(exact.b),1.5)
        self.assertGreater(used,0)
        self.assertEqual(int(count['a']),4)
        self.assertEqual(int(count['b']),4)
        limited,_=bound_population(paths,Fraction(0),Fraction(1),
            include=lambda p:p.upstream_shift < 2,limit='2',evaluate=evaluate)
        self.assertGreaterEqual(float(limited.b),.75)
        self.assertLess(float(limited.b),float(exact.b))


class RealBoundRegressionTests(unittest.TestCase):
    def test_real_source_bound_pass_and_stop_local_intervals(self):
        # Recreate previously proven tiny source-bound intervals with the
        # new recurrence and exact-path population majorants. They are
        # rigorously PASS-LOCAL, never a full-band/release promotion.
        for rate,lo,hi,mode,expected in (
            (44100,'1000','1000.001','pass','PASS-LOCAL-BAND'),
            (176400,'70000','70000.001','stop','PASS-LOCAL-STOP-SOURCE')):
            with self.subTest(output_hz=rate,mode=mode):
                _,op=verify_pair(SNAPSHOTS/f'88200-{rate}',88200,rate)
                result=certificate('master64',op,lo,hi,mode=mode,max_nodes=32)
                self.assertEqual(result['status'],expected)
                self.assertFalse(result['qualified_release'])
                self.assertEqual(result['fully_proven_subintervals'],1)
                self.assertLess(result['max_coherent_alias_upper']
                    if mode=='pass' else result['max_native_stop_source_transfer_upper'],1e-8)
                self.assertIsNone(result['max_total_transfer_upper'] if mode=='stop' else
                                  result['max_native_stop_source_transfer_upper'])


class DeadlineTests(unittest.TestCase):
    def test_deadline_yields_openable_exception_and_restores_alarm(self):
        before=__import__('signal').getsignal(__import__('signal').SIGALRM)
        with self.assertRaises(IntervalBudgetExpired):
            with interval_deadline(.02):time.sleep(.3)
        self.assertEqual(__import__('signal').getsignal(__import__('signal').SIGALRM),before)
        with self.assertRaisesRegex(Exception,'invalid'):
            with interval_deadline(float('nan')):pass

    def test_timed_out_worker_publishes_open_then_runs_following_job(self):
        jobs=[{'cell_id':f'case{i}','profile':'master128','intermediate_hz':176400,
               'output_hz':48000,'mode':'pass','lo':str(i),'hi':str(i+1)}
              for i in range(2)]
        binding={'source':{'fake':'digest'},'design':'design'}
        def work(profile,op,lo,hi,**kw):
            if lo=='0':time.sleep(.1)
            return dict(status='PASS-LOCAL-BAND',certified_hz=[lo,hi],
                band_kind='pass',input_hz=176400,output_hz=48000,
                governing_passband_hz=30000)
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            with patch('p15_full_band_campaign.canonical_plan',return_value=jobs),\
                 patch('p15_full_band_campaign.bindings',return_value=binding),\
                 patch('p15_full_band_campaign.source_operators',return_value={(176400,48000):object()}),\
                 patch('p15_full_band_campaign.certificate',side_effect=work):
                result=run_campaign(folder,interval_seconds=.02,limit=2)
                self.assertEqual(result['mathematical_intervals_open'],1)
                self.assertEqual(result['local_intervals_proven'],1)
                first=json.loads(receipt_path(folder,jobs[0]).read_text())
                second=json.loads(receipt_path(folder,jobs[1]).read_text())
                self.assertEqual(first['certificate']['reason'],
                                 'interval_wall_clock_budget_exhausted')
                self.assertEqual(second['certificate']['status'],'PASS-LOCAL-BAND')
                self.assertFalse(first['qualified_release'])
                prior=[receipt_path(folder,j).read_bytes() for j in jobs]
                rerun=run_campaign(folder,interval_seconds=.02,limit=2)
                self.assertEqual(rerun,result)
                self.assertEqual(prior,[receipt_path(folder,j).read_bytes() for j in jobs])


class ArchivedCampaignResumeTests(unittest.TestCase):
    def test_replay_of_original_43_stalls_has_no_unproven_routes(self):
        record=json.loads(ROUTING_REPLAY.read_text())
        self.assertFalse(record['qualified_release'])
        self.assertEqual(record['previously_stalled_intervals'],43)
        self.assertEqual(sum(r['exact_splits'] for r in
            record['stationary_schedule_results']),73)
        self.assertTrue(all(r['status']=='COMPLETE-SCHEDULE' and
            r['stationary_leaves']==r['exact_splits']+1 and
            r['error'] is None for r in record['stationary_schedule_results']))

    def test_historical_evidence_cannot_be_used_as_import_destination(self):
        with self.assertRaisesRegex(Exception,'independent output'):
            import_archived_partial(ARCHIVED_PARTIAL/'receipts')
        with tempfile.TemporaryDirectory() as d:
            with patch('p15_full_band_campaign.ARCHIVED_PARTIAL_SHA256','0'*64):
                with self.assertRaisesRegex(Exception,'SHA drift'):
                    import_archived_partial(Path(d))


class ArchivedPhysicalTests(unittest.TestCase):
    def test_pinned_archived_physical_measurements_are_scoped(self):
        result=physical_review()
        self.assertEqual(result['status'],'PASS-SCOPED-ARCHIVED-PHYSICAL-EVIDENCE')
        self.assertFalse(result['qualified_release'])
        self.assertEqual(result['performance_comparisons_verified'],8)
        self.assertGreater(result['minimum_95pct_bootstrap_speedup_lower_bound'],3.6)
        self.assertTrue(result['absent_bulk_inputs_and_executables'])
        self.assertFalse(result['physical_host_retested'])

    def test_modified_or_missing_archived_evidence_refused(self):
        with tempfile.TemporaryDirectory() as d:
            copy=Path(d)/'receipt'
            shutil.copytree(ARCHIVE,copy)
            (copy/'bench/RECEIPT.json').write_text((copy/'bench/RECEIPT.json').read_text()+' ')
            with self.assertRaises(ArchivedEvidenceError):physical_review(copy)
            shutil.copyfile(ARCHIVE/'bench/RECEIPT.json',copy/'bench/RECEIPT.json')
            (copy/'comparator/AUDIO_SHA256.txt').unlink()
            with self.assertRaises(ArchivedEvidenceError):physical_review(copy)

if __name__=='__main__':unittest.main()

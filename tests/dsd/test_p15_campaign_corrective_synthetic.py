#!/usr/bin/env python3
"""Self-contained corrective tests: no frozen stage snapshots or audio needed.

These are algorithmic smoke tests, not full 72-cell source-bound qualification.
"""
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest import TestCase,main
from unittest.mock import patch

from p15_src_stagewise_alias_proof import FIRStage,branches
from p15_src_stagewise_continuum import (BranchBoundary,complete_paths,
    certificate,bound_segment,Unproved)
from p15_full_band_campaign import (SCHEMA,receipt_path,
    import_archived_partial,archived_receipt_inventory,check_one,Unproved as CampaignUnproved)


class SyntheticDispatchTests(TestCase):
    def setUp(self):
        self.outer=FIRStage('outer',1200,Fraction(2400),2,1,((0,2.0),))
        self.inner=FIRStage('inner',600,Fraction(1200),2,1,((0,2.0),))
        self.operator=SimpleNamespace(input_hz=600,output_hz=2400,U=1)
        # Mathematically consistent topology of two inverse folding stages;
        # synthetic native identity makes exactly one output harmonic.
        self.p1=patch('p15_src_stagewise_continuum.make_native_stages',
                      return_value=(self.inner,))
        self.p2=patch('p15_src_stagewise_continuum.make_src_stages',
                      return_value=(self.outer,))
        self.p3=patch('p15_src_stagewise_continuum.native_profile',
                      return_value=(2400,600,(),{}))
        for p in (self.p1,self.p2,self.p3):p.start();self.addCleanup(p.stop)

    def test_non_dyadic_and_multiple_inverse_fold_boundaries(self):
        todo=[(Fraction(0),Fraction(1000))]
        boundaries=[];leaves=[]
        while todo:
            lo,hi=todo.pop()
            path=complete_paths('master64',self.operator,lo,hi,
                                require_direct=False)
            if isinstance(path,BranchBoundary):
                self.assertLess(lo,path.at)
                self.assertLess(path.at,hi)
                boundaries.append(path.at)
                todo.extend(((lo,path.at),(path.at,hi)))
            else:
                self.assertEqual(len(path),1)
                leaves.append((lo,hi))
        self.assertEqual(set(boundaries),{Fraction(300),Fraction(600),Fraction(900)})
        self.assertEqual(sorted(leaves),[(Fraction(0),Fraction(300)),
            (Fraction(300),Fraction(600)),(Fraction(600),Fraction(900)),
            (Fraction(900),Fraction(1000))])
        self.assertNotIn(Fraction(300),{Fraction(1000,2**i) for i in range(1,40)})

    def test_node_limit_open_not_spurious_pass(self):
        r=certificate('master64',self.operator,'0','1000',mode='stop',max_nodes=1)
        self.assertEqual(r['status'],'OPEN')
        self.assertEqual(r['reason'],'subdivision_node_budget')
        self.assertEqual(r['nodes_examined'],1)
        self.assertEqual(r['exact_branch_splits'],1)
        self.assertFalse(r['qualified_release'])

    def test_stop_receipt_does_not_report_passband_total(self):
        r=certificate('master64',self.operator,'1','2',mode='stop',max_nodes=2)
        self.assertEqual(r['status'],'PASS-LOCAL-STOP-SOURCE')
        self.assertIsNone(r['max_total_transfer_upper'])
        self.assertIsNone(r['max_coherent_alias_upper'])
        self.assertFalse(r['qualified_release'])

    def test_pass_receipt_keeps_the_unmodified_limits(self):
        # Both filters have exactly unit normalized transfer, with one path.
        r=certificate('master64',self.operator,'1','2',mode='pass',max_nodes=2)
        self.assertEqual(r['status'],'PASS-LOCAL-BAND')
        self.assertLess(r['max_coherent_alias_upper'],1e-8)
        self.assertGreater(r['min_wanted_transfer_lower'],0.99998)
        self.assertLess(r['max_total_transfer_upper'],1.00002)
        self.assertEqual(r['limits'],dict(passband_db='0.0001',coherent_alias_db='-160'))
        self.assertFalse(r['qualified_release'])

    def test_zero_width_boundary_is_not_subdivided_forever(self):
        r=complete_paths('master64',self.operator,Fraction(300),Fraction(300),
                         require_direct=False)
        self.assertEqual(len(r),1)

    def test_stationary_interiors_match_independent_point_routing(self):
        # Verify all sample points of each stationary leaf against independent
        # branches() rather than recycling complete_paths' algebra.
        todo=[(Fraction(0),Fraction(1000))]
        leaves=[]
        while todo:
            lo,hi=todo.pop()
            paths=complete_paths('master64',self.operator,lo,hi,
                                 require_direct=False)
            if isinstance(paths,BranchBoundary):
                todo.extend(((lo,paths.at),(paths.at,hi)))
            else:
                leaves.append((lo,hi,paths))
        for lo,hi,paths in leaves:
            for n in (1,3,5,7,9):
                frequency=lo+(hi-lo)*Fraction(n,10)
                families=[(frequency,())]
                for stage in (self.outer,self.inner):
                    families=[(up,terms+((stage,high-frequency),))
                        for current,terms in families
                        for high,up in branches(stage,current)]
                actual={(p.upstream_shift,p.terms) for p in paths}
                expected={(up-frequency,terms) for up,terms in families}
                self.assertEqual(actual,expected)


class SyntheticArchiveTests(TestCase):
    def test_pinned_import_is_independent_idempotent_and_never_promotes_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'historical'; archived=archive/'receipts'
            archived.mkdir(parents=True)
            output=Path(tmp)/'new';output.mkdir()
            summary=archive/'SUMMARY.json'
            summary.write_text(json.dumps(dict(intervals_nonterminating=43,
                nonterminating_intervals=[{'case':i} for i in range(43)],receipts=1)))
            digest=sha256(summary.read_bytes()).hexdigest()
            # Preserve the historical-plan size restriction with a synthetic
            # plan, but only the first receipt exists on disk.
            jobs=[dict(cell_id=str(i),profile='master64',intermediate_hz=176400,
                output_hz=48000,mode='pass',lo=str(i),hi=str(i+1))
                for i in range(11516)]
            bind=dict(source={'fake':'digest'},design='design')
            doc=dict(schema=SCHEMA,job=jobs[0],binding=bind,
                certificate=dict(status='OPEN',reason='historical_timeout'),
                qualified_release=False)
            receipt_path(archived,jobs[0]).write_text(json.dumps(doc))
            archive_digest=archived_receipt_inventory(archived)[1]
            with patch('p15_full_band_campaign.ARCHIVED_PARTIAL',archive), \
                 patch('p15_full_band_campaign.ARCHIVED_RECEIPTS_SHA256',archive_digest), \
                 patch('p15_full_band_campaign.ARCHIVED_PARTIAL_SHA256',digest), \
                 patch('p15_full_band_campaign.canonical_plan',return_value=jobs), \
                 patch('p15_full_band_campaign.bindings',return_value=bind):
                self.assertEqual(import_archived_partial(output),1)
                before=receipt_path(output,jobs[0]).read_bytes()
                self.assertEqual(import_archived_partial(output),0)
                self.assertEqual(receipt_path(output,jobs[0]).read_bytes(),before)
                self.assertEqual(json.loads(before)['certificate']['status'],'OPEN')
                with self.assertRaisesRegex(CampaignUnproved,'independent output'):
                    import_archived_partial(archived)
                # The summary is still pinned, but altered contents cannot
                # silently become a different mathematical disposition.
                corrupted=json.loads(receipt_path(archived,jobs[0]).read_text())
                corrupted['certificate']['status']='PASS-LOCAL-BAND'
                receipt_path(archived,jobs[0]).write_text(json.dumps(corrupted))
                with self.assertRaisesRegex(CampaignUnproved,'receipt inventory'):
                    import_archived_partial(output)
                receipt_path(archived,jobs[0]).unlink()
                with self.assertRaisesRegex(CampaignUnproved,'receipt inventory'):
                    import_archived_partial(output)

    def test_receipt_pass_status_must_match_job_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            job=dict(cell_id='case',profile='master64',intermediate_hz=88200,
                     output_hz=44100,mode='pass',lo='0',hi='1')
            binding=dict(source={'fake':'digest'},design='design')
            cert=dict(status='PASS-LOCAL-STOP-SOURCE',certified_hz=['0','1'],
                      band_kind='pass',input_hz=88200,output_hz=44100,
                      governing_passband_hz=20000,qualified_release=False)
            doc=dict(schema=SCHEMA,job=job,binding=binding,certificate=cert,
                     qualified_release=False)
            receipt_path(path,job).write_text(json.dumps(doc))
            with self.assertRaisesRegex(CampaignUnproved,'status incompatible'):
                check_one(path,job,binding)


class SyntheticRationalStageTests(TestCase):
    def test_nontrivial_L_over_M_routing_crosses_at_exact_rational(self):
        stage=FIRStage('rational',1000,Fraction(1500),3,2,((0,3.0),))
        op=SimpleNamespace(input_hz=1000,output_hz=1500,U=3)
        with patch('p15_src_stagewise_continuum.make_native_stages',return_value=(stage,)), \
             patch('p15_src_stagewise_continuum.make_src_stages',return_value=()), \
             patch('p15_src_stagewise_continuum.native_profile',
                   return_value=(1000,1000,(),{})):
            crossing=complete_paths('master64',op,Fraction(0),Fraction(700),
                                    require_direct=False)
            self.assertIsInstance(crossing,BranchBoundary)
            self.assertEqual(crossing.at,Fraction(500))
            for lo,hi in ((Fraction(0),Fraction(500)),
                          (Fraction(500),Fraction(700))):
                paths=complete_paths('master64',op,lo,hi,require_direct=False)
                self.assertEqual(len(paths),2)
                for x in (lo+(hi-lo)/7,lo+(hi-lo)*Fraction(6,7)):
                    independently={(up-x,high-x)
                                   for high,up in branches(stage,x)}
                    certified={(p.upstream_shift,p.terms[0][1]) for p in paths}
                    self.assertEqual(certified,independently)


if __name__=='__main__':main()

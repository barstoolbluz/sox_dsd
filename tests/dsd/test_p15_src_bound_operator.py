"""Source/audit adversarial tests for the complete P15 SRC stage phase lattice."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from p15_src_bound_operator import (SRCOperator,Stage,UnboundOperator,
    capture,load_snapshot,sha_file,source_identity)
from p15_src_complete_aliases import all_active_cells

ROOT=Path(__file__).resolve().parents[2]
RESULTS=ROOT/'tests/dsd/results/P15_SRC_STAGE_BOUND_2026-10-16'
EXPORTER=ROOT/'test/dsd_test_p15_src_stage_export'


class SourceStageProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not RESULTS.is_dir():
            raise unittest.SkipTest('source-bound captured stage archive not installed')
        cls.cells=all_active_cells()
        cls.pairs=sorted({(c['intermediate_hz'],c['output_hz']) for c in cls.cells})

    def binding(self,pair):
        d=RESULTS/('%s-%s'%pair)
        raw=d/'stage-snapshot.json'
        receipt=json.loads((d/'operator-binding.json').read_text())
        self.assertEqual(receipt['source_sha256'],source_identity())
        self.assertEqual(receipt['snapshot_sha256'],sha_file(raw))
        self.assertEqual(receipt['status'],'SOURCE_BOUND_UNCERTIFIED')
        self.assertIs(receipt['qualified'],False)
        op=load_snapshot(raw)
        self.assertEqual((op.U,op.V),(receipt['U'],receipt['V']))
        return op

    def test_all_24_stage_realizations_clock_and_transform(self):
        self.assertEqual(len(self.pairs),24)
        for a,b in self.pairs:
            with self.subTest(pair=(a,b)):
                op=self.binding((a,b))
                self.assertEqual(Fraction(op.U,op.V),Fraction(b,a))
                for n in (0,1):
                    self.assertEqual(op.shift_residual(n),0.0)
                self.assertTrue(all(x.order==0 for x in op.stages if x.kind==3))

    def test_exactly_72_src_active_cells(self):
        self.assertEqual(len(self.cells),72)
        self.assertEqual(len({(x['intermediate_hz'],x['output_hz']) for x in self.cells}),24)
        self.assertEqual({x['matrix'] for x in self.cells},{'v1','v2'})
        self.assertEqual([sum(x['matrix']==m for x in self.cells) for m in ('v1','v2')],[48,24])
        for c in self.cells:
            self.assertTrue((RESULTS/f"{c['intermediate_hz']}-{c['output_hz']}").is_dir())

    def test_integer_ratio_misses_halfband_parity(self):
        op=self.binding((352800,48000))
        self.assertEqual((op.reduced_U,op.reduced_V),(20,147))
        self.assertEqual((op.U,op.V,op.stage_period_multiple),(40,294,2))
        a=dict(op.row(2));b=dict(op.row(2+op.reduced_U))
        reduced_error=max((abs(a.get(k,0)-b.get(k+op.reduced_V,0)) for k in a),default=0)
        self.assertGreater(reduced_error,1e-13)
        self.assertEqual(op.shift_residual(2),0.)

    def test_first_last_finite_operator_rows(self):
        op=self.binding((88200,48000))
        for n in (0,1,2,op.U):
            inf=dict(op.row(n))
            finite=dict(op.row(n,512))
            self.assertTrue(set(finite).issubset(k for k in inf if 0<=k<512))
            self.assertTrue(all(abs(v)<3 for v in finite.values()))
            self.assertTrue(all(0<=j<512 for j in finite))

    def test_snapshot_tamper_rejected(self):
        source=RESULTS/'88200-48000/stage-snapshot.json'
        obj=json.loads(source.read_text())
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'tamper.json'
            trials=[]
            trial=copy.deepcopy(obj);trial['stages'][0]['M']*=2;trials.append(trial)
            trial=copy.deepcopy(obj);trial['stages'][1]['fft4g_realized_bins'][0]='0x1.0p+100';trials.append(trial)
            trial=copy.deepcopy(obj);trial['stages'][0]['at_i64']='5.2';trials.append(trial)
            trial=copy.deepcopy(obj);trial['stages'][0]['coefficients'][3]='nan';trials.append(trial)
            trial=copy.deepcopy(obj);trial['stages'][0]['order']=1;trials.append(trial)
            for case in trials:
                with self.subTest(case=trials.index(case)):
                    out.write_text(json.dumps(case))
                    with self.assertRaises(UnboundOperator):load_snapshot(out)

    def test_source_change_invalidates_binding(self):
        # No fixture rewrite: its recorded hash must disagree with *any*
        # source modification in the currently pinned source set.
        d=RESULTS/'88200-48000'
        with mock.patch('p15_src_bound_operator.source_identity',return_value={'src/rate.c':'0'*64}):
            with self.assertRaises(UnboundOperator):
                # Reuse branch refuses stale source. Executable need not run.
                capture(EXPORTER,88200,48000,d)

    @unittest.skipUnless(EXPORTER.is_file(),'test-only C stage exporter not built')
    def test_capture_atomic_and_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)/'bound'
            a=capture(EXPORTER,88200,44100,d)
            first={x.name:x.read_bytes() for x in d.iterdir()}
            self.assertEqual(a,capture(EXPORTER,88200,44100,d))
            self.assertEqual(first,{x.name:x.read_bytes() for x in d.iterdir()})
            with self.assertRaises(UnboundOperator):capture(EXPORTER,88200,48000,d)
            (d/'stage-snapshot.json').write_text('tampered')
            with self.assertRaises(UnboundOperator):capture(EXPORTER,88200,44100,d)


if __name__=='__main__':unittest.main()

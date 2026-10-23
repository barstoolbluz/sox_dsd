"""Private P10 candidate-soak interface checks; not a qualification test."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
EXE=ROOT/'test/dsd_test_p10'
PROFILE='encode.experimental.ntf.order7-pareto-g3p0.dsd512'
GOOD=['0x1p+60']*8
LOW=['0x1p-1']*8
ENV={**os.environ,'LSX_DSD_SDM_KERNEL':'scalar'}

class CandidateSoakContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not EXE.is_file():
            raise unittest.SkipTest('native private P10 executable absent')

    def run_candidate(self,flag,values,profile=PROFILE):
        with tempfile.TemporaryDirectory() as folder:
            prefix=Path(folder)/'run'
            call=[str(EXE),flag,'22579200','1','1',str(prefix),profile]+values
            done=subprocess.run(call,capture_output=True,env=ENV)
            report=Path(str(prefix)+'-result.json')
            record=json.loads(report.read_text()) if report.exists() else None
            states=list(prefix.parent.glob(prefix.name+'-*.state'))
            return done.returncode,record,states

    def test_candidate_nominal_one_instance(self):
        code,result,states=self.run_candidate('--soak-candidate-nominal',GOOD)
        self.assertEqual(code,0)
        self.assertEqual(result['status'],3)
        self.assertEqual(result['profile'],PROFILE)
        self.assertEqual(result['mode'],'soak-candidate-nominal')
        self.assertEqual(result['input_frames'],176400)
        self.assertEqual(result['committed_native_frames'],22579200)
        self.assertEqual(result['processed_native_frames'],22579200)
        self.assertEqual(result['nonfinite_states'],0)
        self.assertEqual(result['excursions28'],0)
        self.assertEqual(len(states),2) # interval + final, no reset

    def test_fail_closed_on_candidate_specific_guard(self):
        code,result,states=self.run_candidate('--soak-candidate',LOW)
        self.assertNotEqual(code,0)
        self.assertEqual(result['failure'],4)
        self.assertEqual(result['coordinate'],0)
        self.assertEqual(result['processed_native_frames'],1)
        self.assertTrue(any('failure' in p.name for p in states))

    def test_unknown_candidate_rejected(self):
        code,result,states=self.run_candidate('--soak-candidate',GOOD,profile='encode.experimental.ntf.unknown.dsd512')
        self.assertNotEqual(code,0)
        self.assertIsNone(result)
        self.assertEqual(states,[])

    def test_nonfinite_bound_rejected(self):
        code,result,states=self.run_candidate('--soak-candidate',GOOD[:-1]+['nan'])
        self.assertNotEqual(code,0)
        self.assertIsNone(result)
        self.assertEqual(states,[])

    def test_original_p20_soak_still_works(self):
        with tempfile.TemporaryDirectory() as folder:
            prefix=Path(folder)/'reference'
            done=subprocess.run([str(EXE),'--soak-nominal-dsd512-v2','22579200','1','1',str(prefix)],capture_output=True,env=ENV)
            self.assertEqual(done.returncode,0,done.stderr)
            result=json.loads(Path(str(prefix)+'-result.json').read_text())
            self.assertEqual(result['profile'],'encode.mastering.v2.dsd512')
            self.assertEqual(result['status'],3)
            self.assertEqual(result['mode'],'soak-nominal-v2')

    def test_no_calibrated_guard_cannot_run_citable_soak(self):
        with tempfile.TemporaryDirectory() as folder:
            done=subprocess.run([sys.executable,str(ROOT/'tests/dsd/ntf_study/qualify_g3.py'),
                                 'soak','--seconds','1','--segment-seconds','1','--prefix',str(Path(folder)/'run')],
                                capture_output=True,text=True,env=ENV)
            self.assertNotEqual(done.returncode,0)
            self.assertIn('candidate training guard not frozen',done.stderr)

if __name__=='__main__':unittest.main()

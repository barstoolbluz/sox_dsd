#!/usr/bin/env python3
"""Stand-alone fail-closed tests for a nonproduction DSD1024 NTF study."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from scipy.signal import freqz

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0,str(HERE))
from model import RATE, ROOT as MODEL_ROOT, P19, DESIGNS512, SOURCE, FAMILY_NAMES
from model import load_legacy, make_designs, positive_coefficients, linear_metrics, sha, canonical
from study import check_scratch, native_pass, prepare, instrument, definitions
from requalify import placeholder, authority


class DesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.disk=json.loads((HERE/'designs.json').read_text())

    def test_exact_source_design_identity(self):
        self.assertEqual(ROOT.resolve(), MODEL_ROOT.resolve())
        self.assertEqual(self.disk,definitions())
        self.assertEqual(self.disk['native_hz'],45158400)
        self.assertEqual(self.disk['working_hz'],176400)
        self.assertEqual(len(self.disk['designs']),55)
        self.assertEqual(self.disk['source_sha256']['src/sdm.c'],sha(SOURCE))
        self.assertNotIn('ntf_dsd1024_trials.h', SOURCE.read_text())

    def test_ten_historical_families_no_omissions(self):
        originals=load_legacy()
        self.assertEqual(set(originals),FAMILY_NAMES)
        for kind in ('clans','sdm'):
            for order in (4,5,6,7,8):
                rec=self.disk['designs'][f'{kind}-{order}']
                self.assertEqual(rec['a'], originals[f'{kind}-{order}']['a'])
                self.assertEqual(rec['g'], originals[f'{kind}-{order}']['g'])
                self.assertEqual(rec['order'],order)

    def test_dsd512_transfers_are_original_binary64(self):
        upstream=json.loads(DESIGNS512.read_text())['designs']
        for key,original in [('d512-r8-a20','o7-r8-a20'),('d512-r5-a20','o7-r5-a20'),
                             ('d512-sdm7-g3','order7-pareto-g3p0')]:
            current=self.disk['designs'][key]
            self.assertEqual(current['a'],upstream[original]['a'])
            self.assertEqual(current['g'],upstream[original]['g'])

    def test_resonator_transfers_and_binary64_canonical(self):
        for key,rec in self.disk['designs'].items():
            positive_coefficients(rec['a'],rec['g'],rec['order'])
            if rec['g_multiplier']!=1:
                seed=self.disk['designs'][key.rsplit('-g',1)[0]]
                self.assertEqual(rec['a'],seed['a'])
                for actual,original in zip(rec['g'],seed['g']):
                    self.assertEqual(float.fromhex(actual),float.fromhex(original)*rec['g_multiplier'])

    def test_unexpected_source_or_coefficient_rejected(self):
        with self.assertRaises(ValueError):
            positive_coefficients([float(1).hex()]*7, [float(0).hex()]*6+[float(2).hex()],7)
        with self.assertRaises(ValueError):
            positive_coefficients(['nan']*7, [float(0).hex()]*7,7)
        with self.assertRaises(ValueError):
            positive_coefficients([float(1).hex()]*7, [float(0).hex()]*7,8)

    def test_all_linearized_metrics_are_descriptive_not_stability_gates(self):
        for name,rec in self.disk['designs'].items():
            lm=rec['linearized_ntf']
            self.assertGreater(lm['sampled_peak_gain'],0)
            self.assertGreater(lm['pole_max_radius'],0)
            self.assertTrue(np.isfinite(list(float(v) for k,v in lm.items() if isinstance(v,(int,float)))).all(),name)
            self.assertIn('not a nonlinear stability',lm['note'])

    def test_authority_and_profile_state_unchanged(self):
        g=authority()
        self.assertFalse(g['qualified'])
        self.assertEqual(g['training_case_count'],17)
        self.assertEqual(g['coefficients_sha256'],sha(ROOT/'src/sdm_p19_candidates.h'))
        p19=P19.read_text()
        self.assertIn('"clans-7-p19-dsd1024"',p19)
        self.assertIn('encode.mastering.v2.dsd1024',SOURCE.read_text())
        self.assertNotIn('encode.experimental.ntf.',SOURCE.read_text())


class NativeSafetyTests(unittest.TestCase):
    def setUp(self):
        self.r={'return_code':0,'timed_out':False,'status':{'status':3,'failure':0,
            'nonfinite_states':0,'monitor_overloads_nominal_half':0,'excursions28':0,
            'min_ones28':6,'max_ones28':22}}
    def test_short_native_success_not_certification(self):
        passed,reason=native_pass(self.r)
        self.assertTrue(passed)
        self.assertIn('not nominal soak',reason)
    def test_all_failures_block_fidelity(self):
        changes=[('return_code',1),('timed_out',True),('status',None)]
        for name,v in changes:
            bad=copy.deepcopy(self.r);bad[name]=v
            self.assertFalse(native_pass(bad)[0])
        for name,v in [('status',1),('failure',2),('nonfinite_states',1),
                       ('monitor_overloads_nominal_half',1),('excursions28',1),
                       ('min_ones28',0),('max_ones28',28)]:
            bad=copy.deepcopy(self.r);bad['status'][name]=v
            self.assertFalse(native_pass(bad)[0],name)

    def test_original_tree_cannot_be_experimentally_instrumented(self):
        with self.assertRaises(RuntimeError):
            check_scratch(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                check_scratch(Path(tmp))

    def test_p19_requalification_placeholder_is_distinct(self):
        self.assertIn('Replaced only by P19 freeze',placeholder())
        self.assertNotEqual(placeholder(),(ROOT/'src/pcmdsd_v2_guards.h').read_text())
        self.assertEqual((ROOT/'src/pcmdsd_v2_guards.h').read_text().count('0x1.'),8)

    def test_mastering_prefilter_limits_ultrasonic_source_claims(self):
        import re
        txt=(ROOT/'src/pcmdsd_coeffs.h').read_text()
        match=re.search(r'lsx_pcmdsd_coeff_master64_256\[61\] = \{(.*?)\};',txt,re.S)
        self.assertIsNotNone(match)
        h=np.asarray([float.fromhex(v.strip()) for v in match.group(1).split(',') if v.strip()])
        def db(hz):return 20*np.log10(abs(freqz(h,worN=[2*np.pi*hz/176400])[1][0]))
        self.assertAlmostEqual(db(40000),0.,delta=.0001)
        self.assertAlmostEqual(db(60000),-6.0206,delta=.0003)
        self.assertLess(db(80000),-180.)
        self.assertEqual(176400//2,88200)


if __name__=='__main__':unittest.main()

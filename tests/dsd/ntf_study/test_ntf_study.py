#!/usr/bin/env python3
"""Nonproduction study integrity, numerical and evidence invariants."""
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

import numpy as np
from scipy.signal import firwin,freqz

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
import design_ntf as design
from analyze_renders import BANDS,dbfs,residual_and_bands


def load(relative):return json.loads((HERE/relative).read_text())

def band(d, ranges):
 parts=d['analysis']['parts']
 return dbfs(math.sqrt(sum(parts[f'{l}-{u}Hz']['rms']**2 for l,u in ranges)))


class NtfStudyIntegrity(unittest.TestCase):
    def test_source_is_original_unmodified_encoder(self):
        model=load('designs.json')
        actual=hashlib.sha256((ROOT/'src/sdm.c').read_bytes()).hexdigest()
        self.assertEqual(model['source_sha256'],actual)
        p20=(ROOT/'src/sdm_p20_candidates.h').read_text()
        self.assertIn('0x1.1b366e8f27ddap+0',p20)
        self.assertNotIn('ntf_experiment_candidates.h',(ROOT/'src/sdm.c').read_text())

    def test_seed_coefficients_exact_words(self):
        model=load('designs.json')
        seeds=design.legacy_coeffs()
        for key in ('sdm-4','sdm-5','sdm-6','sdm-7','clans-7'):
            a,g=seeds[key]
            self.assertEqual([float(t).hex() for t in a],model['references'][key]['a'])
            self.assertEqual([float(t).hex() for t in g],model['references'][key]['g'])

    def test_analytic_ntfs_meet_design_screen_but_not_stability_proof(self):
        model=load('designs.json')
        self.assertEqual(set(model['designs']),{f'order{i}-band{b}k' for i in range(4,8) for b in (100,150)})
        for name,data in model['designs'].items():
            self.assertFalse(data['screen_rejected'],name)
            a=np.asarray([float.fromhex(v) for v in data['a']]);g=np.asarray([float.fromhex(v) for v in data['g']])
            self.assertEqual(len(a),data['order'])
            m=design.metrics(a,g)
            self.assertLess(m['ntf_max_gain'],1.61,name)
            self.assertLess(m['pole_max_radius'],.981,name)
            self.assertAlmostEqual(m['ntf_rms_0_150k_db'],data['linearized_ntf']['ntf_rms_0_150k_db'],delta=1e-9)

    def test_balanced_sweep_preserves_topology(self):
        base=load('designs.json')['references']['sdm-7']
        candidate=load('designs-sweep.json')['designs']['order7-pareto-g3p0']
        self.assertEqual(base['a'],candidate['a'])
        for old,new in zip(base['g'],candidate['g']):
            self.assertEqual(float.fromhex(new),3*float.fromhex(old))

    def test_frozen_baseline_bitstream_reproduced(self):
        orig=json.loads((HERE.parent/'results/P20_RESIDUAL_ASYMMETRY_2026-10-22/analysis.json').read_text())
        rec=load('evidence/renders/P20-CLANS7-baseline.receipt.json')
        self.assertEqual(rec['packed_sha256'],orig['sources']['unquantized_f64']['dsd512']['v2']['packed_sha256'])
        self.assertEqual(rec['status']['committed_native_frames'],36126720)

    def test_rectangular_spectral_leakage_is_detected_and_corrected(self):
        fs=352800;n=np.arange(int(1.6*fs),dtype=np.float64)
        signal=.25*np.sin(2*np.pi*997*n/fs)+1e-10*np.sin(2*np.pi*10001*n/fs)
        signal+=3e-5*np.sin(2*np.pi*160000.65*n/fs)
        windowed=residual_and_bands(signal,fs,BANDS,windowed=True)
        rectangular=residual_and_bands(signal,fs,BANDS,windowed=False)
        groups=BANDS[:2]
        actual=dbfs(math.sqrt(sum(windowed['parts'][f'{l}-{u}Hz']['rms']**2 for l,u in groups)))
        bogus=dbfs(math.sqrt(sum(rectangular['parts'][f'{l}-{u}Hz']['rms']**2 for l,u in groups)))
        self.assertLess(actual,-190,(actual,bogus))
        self.assertGreater(bogus,actual+35,(actual,bogus))

    def test_independent_final_firs_match_spectral_bands(self):
        for key,directory in [('P20-CLANS7-baseline','spectrum-sweep'),('order7-pareto-g3p0','spectrum-sweep'),('order7-band100k','spectrum')]:
            base=load(f'evidence/{directory}/{key}.json')
            alt=load(f'evidence/{directory}/{key}.alternate.json')
            self.assertEqual(base['packed_sha256'],alt['packed_sha256'])
            # Compare integrated bands, not individual noise bins.
            for ranges in (BANDS[:2],BANDS[2:5],BANDS[5:7]):
                self.assertLess(abs(band(base,ranges)-band(alt,ranges)),.2,(key,ranges))

    def test_balanced_audio_gain_and_high_input_failures(self):
        baseline=load('evidence/spectrum/P20-CLANS7-baseline.json')
        balanced=load('evidence/spectrum-sweep/order7-pareto-g3p0.json')
        self.assertLess(band(balanced,BANDS[:2]),band(baseline,BANDS[:2]))
        self.assertLess(band(balanced,BANDS[2:5]),band(baseline,BANDS[2:5])-35)
        self.assertLess(band(balanced,BANDS[5:7]),band(baseline,BANDS[5:7])-25)
        for order in (4,5,6,7):
            for bw in (100,150):
                key=f'order{order}-band{bw}k'
                rec=load(f'evidence/holdouts/tone997-hot/renders/{key}.receipt.json')
                if key!='order6-band100k':
                    self.assertEqual(rec['returncode'],1,key)
                    self.assertGreater(rec['status']['nonfinite_states'],0,key)
                else:self.assertEqual(rec['returncode'],0)

    def test_continuous_32s_results_and_limitations(self):
        for kind,key in [('renders','P20-CLANS7-baseline'),('renders-sweep','order7-pareto-g3p0')]:
            r=load(f'evidence/holdouts/stress32/{kind}/{key}.receipt.json')
            st=r['status']
            self.assertEqual(r['returncode'],0)
            self.assertEqual(st['committed_native_frames'],722534400)
            self.assertEqual((st['min_ones28'],st['max_ones28']),(7,21))
            self.assertEqual((st['excursions28'],st['nonfinite_states']),(0,0))
            self.assertFalse(r['candidate_qualified'])

    def test_extended_band_is_noise_only_in_this_pipeline(self):
        prefilter=(ROOT/'src/pcmdsd_coeffs.h').read_text()
        import re
        text=re.search(r'lsx_pcmdsd_coeff_master64_256\[61\] = \{(.*?)\};',prefilter,re.S).group(1)
        h=np.array([float.fromhex(x.strip()) for x in text.split(',') if x.strip()])
        def gain(f):return 20*math.log10(abs(freqz(h,worN=[2*math.pi*f/176400])[1][0]))
        self.assertLess(abs(gain(40000)),1e-4)
        self.assertAlmostEqual(gain(60000),-6.0206,delta=.0002)
        self.assertLess(gain(80000),-180)

if __name__=='__main__':unittest.main()

#!/usr/bin/env python3
"""R2 audit regressions: semantic spectra, authoritative sources, native PSD."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from model import RATE, WORKING, sha
from r2_screen import CASES, material, generate, r2_native_pass
from study import ROOT, check_scratch, official_analysis
from verify_evidence import verified_spectrum
from r2_welch import FFT_SIZE, analyze

HERE=Path(__file__).resolve().parent
E=HERE/'evidence'


class CorrectiveR2Tests(unittest.TestCase):
    def test_all_mandatory_sources_exact_and_bounded(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as temp:
            t=Path(temp)
            generate(t)
            first=(t/'manifest.json').read_bytes()
            generate(t)
            self.assertEqual((t/'manifest.json').read_bytes(),first)
            manifest=json.loads(first)['cases']
            self.assertEqual(set(manifest),set(CASES))
            for name in CASES:
                p=t/(name+'.f64le')
                self.assertEqual(sha(p),manifest[name]['sha256'])
                self.assertEqual(p.read_bytes(),material(name)[0])
                x=np.fromfile(p,dtype='<f8')
                self.assertTrue(np.isfinite(x).all())
                self.assertLessEqual(np.max(abs(x)),1.+1e-15)
                self.assertEqual(len(x),manifest[name]['frames'])
            self.assertEqual(manifest['programme-unclipped-0p90']['frames'],round(3.2*WORKING))
            p=t/'dc-positive-1p0.f64le'
            p.write_bytes(b'source corruption')
            with self.assertRaises(RuntimeError):generate(t)

    def test_holdout_window_is_source_bound(self):
        a=json.loads((E/'finalists/tone-20k/sdm-8.json').read_text())
        b=json.loads((E/'finalists/tone-40k/sdm-8.json').read_text())
        c=json.loads((E/'primary/sdm-8.json').read_text())
        self.assertEqual(official_analysis(a),(20000.,.25,.95))
        self.assertEqual(official_analysis(b),(40000.,.25,.95))
        self.assertEqual(official_analysis(c),(997.,.4,1.2))
        self.assertIsNone(official_analysis({'input_sha256':'0'*64,'input_frames':1}))

    def test_bad_analysis_window_rejected_even_with_numeric_edit(self):
        rp=E/'finalists/tone-20k/sdm-8.json';render=json.loads(rp.read_text())
        spec=json.loads((E/'holdout-spectra/tone-20k/sdm-8.json').read_text())
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'s.json'
            def check(obj):
                path.write_text(json.dumps(obj));
                return verified_spectrum(path,'sdm-8',rp,render,case='tone-20k')
            self.assertEqual(check(spec),spec)
            mutated=copy.deepcopy(spec)
            mutated['spectrum']['start_s']=.4
            mutated['spectrum']['stop_s']=1.2
            mutated['integrated_sine_equivalent_dbfs']['0_40k']=-46.8059533
            with self.assertRaises(AssertionError):check(mutated)
            for field in ('last_fir_beta','halfband_taps'):
                mutated=copy.deepcopy(spec);mutated[field]=999
                with self.assertRaises(AssertionError):check(mutated)
            mutated=copy.deepcopy(spec)
            mutated['integrated_sine_equivalent_dbfs']['0_40k']+=1.
            with self.assertRaises(AssertionError):check(mutated)
            mutated=copy.deepcopy(spec)
            mutated['spectrum']['parts']['0-20000Hz']['rms']*=1.1
            with self.assertRaises(AssertionError):check(mutated)

    def test_fullscale_roundoff_not_misclassified_as_nonlinear_failure(self):
        from study import native_pass
        p=HERE/'evidence_r2/screen/tone997-0dbfs/receipts/clans-7.json'
        row=json.loads(p.read_text())
        self.assertEqual(row['status']['monitor_overloads_nominal_half'],11)
        self.assertFalse(native_pass(row)[0])
        good,why=r2_native_pass(row,'tone997-0dbfs')
        self.assertTrue(good,why)
        self.assertIn('NOT zero overload',why)
        good,why=r2_native_pass(row,'tone997-minus0p1dbfs')
        self.assertFalse(good)
        unstable=json.loads((HERE/'evidence_r2/screen/tone997-0dbfs/receipts/clans-8.json').read_text())
        self.assertFalse(r2_native_pass(unstable,'tone997-0dbfs')[0])
        synthetic=copy.deepcopy(row)
        synthetic['status']['peak']=.50000001
        self.assertFalse(r2_native_pass(synthetic,'tone997-0dbfs')[0])

    def test_research_cannot_instrument_source_descendant(self):
        with self.assertRaises(RuntimeError):check_scratch(ROOT/'tests')
        with self.assertRaises(RuntimeError):check_scratch(ROOT)
        with self.assertRaises(RuntimeError):check_scratch(ROOT.parent)

    def test_welch_parseval_and_bit_endianness(self):
        # A synthetic constant +1 stream has total normalized PSD power 1.
        # This independently tests Hann normalization and native bit order.
        n=round(1.6*RATE)
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'ones.packed'
            f.write_bytes(bytes([255])*(n//8))
            base=json.loads((E/'primary/clans-7.json').read_text())
            base.update(packed_sha256=sha(f),native_hz=RATE,working_hz=WORKING)
            stats=analyze(f,base)
            self.assertAlmostEqual(stats['total_bipolar_power'],1.,delta=1e-10)
            self.assertEqual(stats['nfft'],FFT_SIZE)
            self.assertEqual(stats['native_bits_per_sample'],1)
            self.assertEqual(stats['bit_order'],'MSB first; 1->+1, 0->-1')


if __name__=='__main__':unittest.main()

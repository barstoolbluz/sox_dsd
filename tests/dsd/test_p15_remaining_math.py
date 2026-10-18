#!/usr/bin/env python3
"""Focused fail-closed regression for P15 partial numerical/spectral certificates.

Acceptance is carefully separated: the new interval tests certify stated local
ideal-operator domains; none turns a whole release gate into PASS.
"""
from __future__ import annotations
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

THIS=Path(__file__).resolve().parent
ROOT=THIS.parents[1]
if str(THIS) not in sys.path: sys.path.insert(0,str(THIS))

from p15_src_capture_matrix import verify_pair,DEFAULT as ACTIVE_STAGE_ROOT
from p15_src_bound_operator import load_snapshot,UnboundOperator,source_identity
from p15_fft_coefficient_interval import certificate as fft_cert,CertificateError as FFTError
from p15_native_coefficient_interval import certificate as native_cert,CertificateError as NativeError
from p15_src_stagewise_continuum import (certificate as spectral_cert,
    Unproved,complete_paths,PROFILE_BANDS)
from p15_src_complete_aliases import native_profile
from p15_dsd256_comparator_2026 import (verify as verify_match,InvalidReceipt,command)

RESULT=THIS/'results/P15_REMAINING_PROOF_2026-10-16'
STAGES=ACTIVE_STAGE_ROOT


class NativeCoeffTests(unittest.TestCase):
    def test_exact_rounding_and_tiny_artifacts(self):
        r=native_cert(112)
        self.assertEqual(r['status'],'PASS')
        self.assertFalse(r['qualified_release'])
        self.assertEqual(sum(x['taps_strictly_rounded'] for x in r['banks']),1421)
        self.assertEqual(sum(len(x['tiny_generator_artifacts']) for x in r['banks']),18)
        self.assertEqual(r,json.loads((RESULT/'native-interval-certificate.json').read_text()))

    def test_source_drift_rejected(self):
        # A change in any binary64 header word must invalidate the receipt;
        # these digests cover both native sources, not just one profile.
        r=json.loads((RESULT/'native-interval-certificate.json').read_text())
        for name,expected in r['source_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),expected)


class FFTCoeffTests(unittest.TestCase):
    def test_all_24_evidence_identity(self):
        a=json.loads((RESULT/'fft-bins/SUMMARY.json').read_text())
        self.assertEqual(len(a['all_pairs']),24)
        self.assertEqual(a['status'],'ALL_CAPTURED_FFT_BINS_BOUNDED')
        self.assertFalse(a['qualified_release'])
        for r in a['all_pairs']:
            f=RESULT/'fft-bins'/f"{r['pair']}.json"
            self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(),r['sha256'])
            self.assertNotIn('execution-roundoff',json.loads(f.read_text())['status'])

    def test_recompute_independently_and_refuse_stage_tampering(self):
        src=STAGES/'88200-48000/stage-snapshot.json'
        result=fft_cert(src)
        frozen=json.loads((RESULT/'fft-bins/88200-48000.json').read_text())
        # The historical FFT receipt is immutable and intentionally names
        # the frozen SOURCE identity. Recomputing against the opt-in branch
        # must yield identical numerical evidence but a *different* source map.
        self.assertEqual(result['source_sha256'],source_identity())
        self.assertNotEqual(result['source_sha256'],frozen['source_sha256'])
        changed={k for k in result['source_sha256'] if
                 result['source_sha256'][k]!=frozen['source_sha256'][k]}
        self.assertEqual(changed,{'src/rate_poly_fir0.h',
                                  'tests/dsd/p15_src_capture_matrix.py'})
        self.assertEqual({k:v for k,v in result.items() if k!='source_sha256'},
                         {k:v for k,v in frozen.items() if k!='source_sha256'})
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);fake=p/'stage-snapshot.json';fake.write_bytes(src.read_bytes()+b' ')
            (p/'operator-binding.json').write_bytes((src.parent/'operator-binding.json').read_bytes())
            with self.assertRaises(FFTError):fft_cert(fake)


class SpectralTests(unittest.TestCase):
    def test_full_chain_one_millihertz_passband_interior(self):
        profile='decode.mastering.v2.dsd256'
        rate=STAGES/'176400-705600'
        _,op=verify_pair(rate,176400,705600)
        r=spectral_cert(profile,op,'1000','1000.001',max_nodes=4)
        self.assertEqual(r['status'],'PASS-LOCAL-BAND')
        self.assertLess(r['max_coherent_alias_upper'],1e-8)
        self.assertFalse(r['qualified_release'])
        self.assertEqual(PROFILE_BANDS[profile],(66000,80000))

    def test_full_chain_one_millihertz_stopband_interior(self):
        profile='master64';rate=STAGES/'88200-176400'
        _,op=verify_pair(rate,88200,176400)
        r=spectral_cert(profile,op,'70000','70000.001',mode='stop',max_nodes=4)
        self.assertEqual(r['status'],'PASS-LOCAL-STOP-SOURCE')
        self.assertLess(r['max_native_stop_source_transfer_upper'],1e-8)

    def test_refuse_false_pass_band_or_stage_budget(self):
        _,op=verify_pair(STAGES/'88200-44100',88200,44100)
        with self.assertRaises(Unproved):spectral_cert('master64',op,20000,20001)
        with self.assertRaises(Unproved):spectral_cert('master64',op,-1,0,mode='stop')
        r=spectral_cert('master64',op,'1000','1000.001',max_paths=1)
        self.assertEqual(r['status'],'OPEN')
        self.assertIn('operator_path_precondition',r['reason'])

    def test_exact_alias_population_and_source_binding(self):
        _,op=verify_pair(STAGES/'88200-44100',88200,44100)
        paths=complete_paths('master64',op,Fraction(1000),Fraction(1000001,1000))
        self.assertEqual(len(paths),64)
        self.assertEqual(len(set(p.upstream_shift for p in paths)),64)
        self.assertEqual(sum(p.direct for p in paths),1)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);src=STAGES/'88200-44100'
            (p/'stage-snapshot.json').write_bytes((src/'stage-snapshot.json').read_bytes()+b' ')
            (p/'operator-binding.json').write_bytes((src/'operator-binding.json').read_bytes())
            with self.assertRaises((UnboundOperator,ValueError)):verify_pair(p,88200,44100)


class ComparatorTests(unittest.TestCase):
    def test_control_is_ps_matched_and_full_band(self):
        for p,s in [(40000,80000),(66000,80000)]:
            cmd=command(Path('/binary/sox'),native=Path('/native.dsf'),output=Path('/ctl.wav'),
                        rate=176400,pass_hz=p,stop_hz=s)
            self.assertEqual(cmd[-7:],["sinc","-a","180","-t",str(s-p),'-'+str((s+p)//2),'rate','-v'][-7:])
            self.assertNotIn('-66000',cmd)
            self.assertIn('-t',cmd)

    def test_replay_matched_and_wrong_control(self):
        sox=ROOT/'src/sox_ng';candidate=ROOT/'test/sox_p10_candidate'
        if not sox.is_file() or not candidate.is_file():
            self.skipTest('no locally compiled source-bound binaries; run on build host')
        good=verify_match(RESULT/'ps-matched-comparator',sox,candidate)
        bad=verify_match(RESULT/'ps-matched-comparator-negative-selftest',sox,candidate,allow_wrong=True)
        self.assertTrue(good['spectrally_matched_on_fixture'])
        self.assertFalse(bad['spectrally_matched_on_fixture'])
        self.assertEqual(len(good['rows']),4)
        self.assertEqual(len(bad['rows']),4)
        self.assertTrue(all(r['verification']['transition_excluded_fraction']==0 for r in good['rows']))
        self.assertLess(max(r['verification']['max_abs_difference_db'] for r in good['rows']),0.01)
        self.assertGreater(max(r['verification']['max_abs_difference_db'] for r in bad['rows']),50.)


if __name__=='__main__':unittest.main()

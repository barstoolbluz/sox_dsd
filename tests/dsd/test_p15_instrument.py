#!/usr/bin/env python3
"""Focused tests/mutations for the P15 independent full-matrix instrument.

Pure-reference checks run without a built repository. Set P15_LIVE=1 after
building the test C probes for exercised decoder/SRC and evidence-failure tests.
An isolated P15_LIVE=1 run writes disposable evidence only to temp directories.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
from scipy.signal import resample_poly

sys.path.insert(0,str(Path(__file__).resolve().parent))
import p15_matrix_instrument as instrument
from p15_matrix_contract import make_plan
import p15_numerical_reference as ref
import p15_src_spectral as spectral
import p15_matrix_receipt_review as receipt_review

ROOT=Path(__file__).resolve().parents[2]
PROBE=Path(os.environ.get('P15_PROBE',str(ROOT/'test/dsd_test_p15_instrument')))
SRC_PROBE=Path(os.environ.get('P15_SRC_PROBE',str(ROOT/'test/dsd_test_p07_reference')))
SOX=Path(os.environ.get('P15_SOX',str(ROOT/'src/sox')))
LIVE=os.environ.get('P15_LIVE')=='1'


def live_test(func):
    return unittest.skipUnless(LIVE and PROBE.is_file(),
                               'requires P15_LIVE=1 and built test probes')(func)


class P15Reference(unittest.TestCase):
    def test_54_cells_and_cross_isa_contract(self):
        plan=make_plan()
        self.assertEqual(plan['summary']['scalar_cells'],54)
        self.assertEqual(plan['summary']['integer_reference_cells'],30)
        self.assertEqual(plan['summary']['fractional_reference_cells'],24)
        self.assertEqual(plan['summary']['all_tier_functional_jobs'],270)
        self.assertEqual(plan['summary']['minimum_detailed_cross_isa_jobs'],96)
        self.assertEqual(len({x['id'] for x in plan['scalar_cells']}),54)
        self.assertTrue(all(x['status']=='UNRUN' for x in plan['scalar_cells']))
        self.assertEqual(plan['status'],'PLAN_ONLY_NOT_EXECUTED')

    def test_source_coefficients_and_spectral_certificate(self):
        self.assertEqual(len(ref.bank_data()[0]['banks']),4)
        self.assertEqual(instrument.inherited_fir_certificate()['six_profiles'],6)
        self.assertEqual(len(ref.bank_data()[0]['profiles']),6)

    def test_manifest_modification_fails_closed(self):
        original=ref.MANIFEST
        with tempfile.TemporaryDirectory() as tmp:
            tampered=Path(tmp)/'manifest.json'
            obj=json.loads(original.read_text())
            obj['banks'][next(iter(obj['banks']))]['rounded_hex_sha256']='bad'
            tampered.write_text(json.dumps(obj))
            try:
                ref.MANIFEST=tampered
                ref.bank_data.cache_clear()
                with self.assertRaisesRegex(ValueError,'P06 certified coefficient'):
                    ref.bank_data()
            finally:
                ref.MANIFEST=original
                ref.bank_data.cache_clear()

    def test_reference_preserves_finite_numeric_zero_extension(self):
        profile='master64'
        taps,delay,down=ref.equivalent_exact(profile)
        self.assertEqual(len(taps),2*delay+1)
        for length in (0,1,2,3,31,32,33,129):
            b=np.arange(length,dtype=np.uint8)%2
            actual=ref.front_end(b,profile)
            self.assertEqual(len(actual),(length+down-1)//down)
            for m in (0,max(0,len(actual)-1)):
                if len(actual):
                    center=delay+m*down
                    exact=sum(float(taps[center-n])*(1 if b[n] else -1)
                              for n in range(length) if 0<=center-n<len(taps))
                    self.assertLess(abs(float(actual[m])-exact),1e-12)

    def test_mp_composition_witness_uses_exact_cascade(self):
        b=(np.arange(1024,dtype=np.int64)%3==0).astype(np.uint8)
        receipt=ref.front_mp_witness(b,'master64',(0,11,31))
        self.assertEqual(receipt['precision_digits'],75)
        self.assertEqual(len(receipt['witnesses']),3)
        for item in receipt['witnesses']:
            self.assertLess(item['longdouble_vs_75digit_abs'],1e-16)
            self.assertGreater(len(item['exact_75digit']),24)

    def test_fractional_independent_src_reproduces_polyphase_identity(self):
        rng=np.random.default_rng(271828)
        x=rng.normal(size=397).astype(np.longdouble)
        for src,dst in ((88200,48000),(176400,705600),(352800,192000),
                        (176400,176400)):
            with self.subTest(src=src,dst=dst):
                actual=ref.polyphase(x,src,dst)
                up,down=ref.pair_ratio(src,dst)
                if src==dst:
                    self.assertTrue(np.array_equal(actual,x))
                else:
                    expected=resample_poly(np.asarray(x,dtype=float),up,down,
                                         window=np.asarray(ref.rational_taps(up,down),dtype=float))
                    self.assertEqual(len(actual),len(expected))
                    self.assertLess(float(np.max(np.abs(actual-expected))),6e-14)
                    w=ref.polyphase_mp_witness(x,src,dst,len(actual),
                                               (0,len(actual)//2,len(actual)-1))
                    self.assertTrue(all(t['longdouble_vs_75digit_abs']<1e-13
                                        for t in w['witnesses']))

    def test_rational_rounded_native_output_count(self):
        zeros=np.ones(43,dtype=np.uint8)
        for n in (0,1,2,3,42):
            for pcm in (44100,48000,192000,705600):
                _,got=ref.reference(zeros[:n],'master64',2822400,pcm)
                self.assertEqual(len(got),(n*pcm+1411200)//2822400)

    def test_invalid_input_rejected(self):
        with self.assertRaisesRegex(ValueError,'unsupported stimulus'):
            instrument.native_bits(64,2822400,9)
        with self.assertRaisesRegex(ValueError,'invalid native one-bit'):
            instrument.run_probe(PROBE,native=2822400,pcm=88200,
                profile='mastering',tier='scalar',stimulus=np.array([[3]],dtype=np.uint8),chunk=8)
        with self.assertRaises(ValueError):
            ref.front_end(np.array([0,2],dtype=np.uint8),'master64')

    def test_phase_of_shifted_impulse_is_not_silently_zero(self):
        n=4096
        wave=np.zeros(n,dtype=np.float64)
        wave[n//2]=1.
        moved=np.roll(wave,1)
        receipt=instrument.phase_alignment(moved,wave,88200,20000)
        self.assertAlmostEqual(receipt['relative_group_delay_pcm_frames'],1,places=5)
        self.assertFalse(receipt['aligned_to_subsample_0_005'])

    def test_machine_path_removed(self):
        self.assertTrue(instrument.absolute_path_free({'a': ['rel/file',{'c':2}]}))
        self.assertFalse(instrument.absolute_path_free({'a':'/tmp/private/path'}))
        self.assertFalse(instrument.absolute_path_free({'a':'C:\\Users\\alice'}))

    def test_sampled_src_tone_limit_mutation(self):
        def fake(src,fr,to,n,tone,timeout=180):
            length=(n*to+fr//2)//fr
            freq=tone%to
            if freq>to/2:freq=to-freq
            if freq<0:freq=-freq
            x=np.arange(length,dtype=np.float64)
            data=.5*np.sin(2*np.pi*freq*x/to)
            return data,dict(tone_hz=tone,binary64_sha256='f'*64)
        with mock.patch.object(spectral,'run_tone',side_effect=fake):
            result=spectral.evaluate(SRC_PROBE,88200,48000,20000,frames=8192)
            self.assertFalse(result['passed'])
            self.assertEqual(result['status'],'SAMPLED_FAIL')
            self.assertTrue(any(not x['pass_alias'] for x in result['aliases']))


class P15BuiltProbe(unittest.TestCase):
    @live_test
    def test_zero_tiny_endpoint_real_c(self):
        for count in (0,1,2,3,31,32,33,257):
            b=instrument.native_bits(count,2822400)
            got,proof=instrument.run_probe(PROBE,native=2822400,pcm=88200,
                            profile='mastering',tier='scalar',stimulus=b,chunk=3)
            self.assertEqual(got.shape,((count*88200+1411200)//2822400,1))
            self.assertEqual(proof['output_frames'],len(got))

    @live_test
    def test_trailing_byte_and_invalid_bit_fail(self):
        argv=[str(PROBE),'2822400','88200','mastering','scalar','1','1','1']
        for payload in (b'\x01\x00',b'\x03',b''):
            result=subprocess.run(argv,input=payload,capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertNotIn(b'P15_PROBE_OK',result.stderr)

    @live_test
    def test_unsupported_hardware_not_promoted(self):
        b=instrument.native_bits(128,2822400)
        # The unknown forced tier itself is an error; don't rewrite to scalar.
        argv=[str(PROBE),'2822400','88200','mastering','made-up','1','128','32']
        r=subprocess.run(argv,input=b.tobytes(),capture_output=True)
        self.assertNotEqual(r.returncode,0)
        self.assertNotIn(b'P15_PROBE_OK',r.stderr)

    @live_test
    def test_sacd_exact_gain_and_chunk_idempotence(self):
        b=instrument.native_bits(16384,2822400)
        def run(chunk,level):
            x,_=instrument.run_probe(PROBE,native=2822400,pcm=48000,
                     profile='mastering',tier='scalar',stimulus=b,chunk=chunk,level=level)
            return x
        scalar=run(1,'preserve')
        self.assertTrue(np.array_equal(scalar,run(333,'preserve')))
        self.assertTrue(np.array_equal(scalar*2,run(317,'sacd')))

    @live_test
    def test_actual_private_src_spectral_probe(self):
        if not SRC_PROBE.is_file():self.skipTest('built private SRC exporter missing')
        got=spectral.evaluate(SRC_PROBE,88200,48000,20000,frames=8192)
        self.assertGreater(got['checks'],7)
        self.assertTrue(got['passed'])

    @live_test
    def test_evidence_replay_and_tampering_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix='p15-tamper-') as tmp:
            base=Path(tmp)
            import argparse
            options=argparse.Namespace(results=base,probe=PROBE,src_probe=None,
                sox=None,native=2822400,pcm=88200,profile='mastering',
                frames=8192,src_frames=8192,tiers=('scalar',),
                resume=False,stop_on_fail=True,require_qualified=False,
                capture_src_raw=False,capture_graph_raw=False,
                require_all_observations=False)
            self.assertEqual(instrument.execute(options),0)
            options.resume=True
            self.assertEqual(instrument.execute(options),0)
            receipt=next((base/'arrays').glob('*.npz'))
            original=receipt.read_bytes()
            receipt.write_bytes(original[:-1]+bytes([original[-1]^1]))
            with self.assertRaisesRegex(ValueError,'tampered/missing raw'):
                instrument.execute(options)
            receipt.write_bytes(original)
            session=base/'session.json'
            obj=json.loads(session.read_text())
            obj['frames']=9999
            session.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,'resume binding mismatch'):
                instrument.execute(options)

    @live_test
    def test_lost_session_and_worklist_do_not_rebind_old_cells(self):
        import argparse
        with tempfile.TemporaryDirectory(prefix='p15-rebind-') as tmp:
            root=Path(tmp)
            options=argparse.Namespace(results=root,probe=PROBE,src_probe=None,
                sox=None,native=2822400,pcm=88200,profile='mastering',
                frames=8192,src_frames=8192,tiers=('scalar',),
                resume=False,stop_on_fail=True,require_qualified=False,
                capture_src_raw=False,capture_graph_raw=False,
                require_all_observations=False)
            self.assertEqual(instrument.execute(options),0)
            options.resume=True
            session=root/'session.json'
            original=session.read_bytes()
            session.unlink()
            with self.assertRaisesRegex(ValueError,'missing original session'):
                instrument.execute(options)
            self.assertFalse(session.exists())
            session.write_bytes(original)
            worklist=root/'worklist.json'
            worklist.unlink()
            with self.assertRaisesRegex(ValueError,'original worklist'):
                instrument.execute(options)

    @live_test
    def test_complete_observation_mode_is_not_just_full_duration(self):
        import argparse
        with tempfile.TemporaryDirectory(prefix='p15-require-') as tmp:
            args=argparse.Namespace(results=Path(tmp),probe=PROBE,src_probe=None,
                sox=None,native=None,pcm=None,profile=None,
                frames=262144,src_frames=131072,tiers=('scalar',),
                resume=False,stop_on_fail=True,require_qualified=False,
                capture_src_raw=False,capture_graph_raw=False,
                require_all_observations=True)
            with self.assertRaisesRegex(ValueError,'requires all 54 cells'):
                instrument.execute(args)

    @live_test
    def test_cross_host_review_recomputes_vectors_and_rejects_forged_metrics(self):
        import argparse
        with tempfile.TemporaryDirectory(prefix='p15-review-') as tmp:
            base=Path(tmp)/'evidence'
            args=argparse.Namespace(results=base,probe=PROBE,src_probe=None,
                sox=None,native=2822400,pcm=88200,profile='mastering',
                frames=8192,src_frames=8192,tiers=('scalar',),
                resume=False,stop_on_fail=True,require_qualified=False,
                capture_src_raw=False,capture_graph_raw=False,
                require_all_observations=False)
            self.assertEqual(instrument.execute(args),0)
            report=receipt_review.review([base])
            self.assertEqual(report['scalar_full_duration_cells'],0)
            self.assertFalse(report['release_gate_closed'])
            self.assertEqual(report['sessions'][0]['measured_cells'],1)
            original=next((base/'cells').glob('*.json'))
            old=original.read_bytes()
            obj=json.loads(old)
            obj['scalar_program']['metric']['max_abs']+=0.1
            original.write_text(json.dumps(obj))
            original.with_suffix('.sha256').write_text(instrument.file_hash(original)+'\n')
            with self.assertRaisesRegex(ValueError,'statistic does not match raw'):
                receipt_review.review([base])
            original.write_bytes(old)
            original.with_suffix('.sha256').write_text(instrument.file_hash(original)+'\n')
            self.assertEqual(receipt_review.review([base])['session_count'],1)

    @live_test
    def test_scalar_phase_mismatch_is_a_failure_not_an_observation(self):
        plan=make_plan()
        cell=next(x for x in plan['scalar_cells'] if x['id']=='dsd64.mastering.pcm88200')
        with mock.patch.object(instrument,'phase_alignment',return_value={
                'relative_group_delay_pcm_frames':1.,
                'aligned_to_subsample_0_005':False}):
            with self.assertRaisesRegex(AssertionError,'scalar end-to-end phase'):
                instrument.make_one_cell(PROBE,cell,8192)

    @live_test
    def test_raw_src_and_graph_files_are_replayed_not_just_trusted(self):
        import argparse
        if not SRC_PROBE.is_file() or not SOX.is_file():
            self.skipTest('built SRC and actual SoX CLI required')
        with tempfile.TemporaryDirectory(prefix='p15-raw-review-') as tmp:
            base=Path(tmp)
            args=argparse.Namespace(results=base,probe=PROBE,src_probe=SRC_PROBE,
                sox=SOX,native=2822400,pcm=48000,profile='mastering',
                frames=8192,src_frames=8192,tiers=('scalar','sse2'),
                resume=False,stop_on_fail=True,require_qualified=False,
                capture_src_raw=True,capture_graph_raw=True,
                require_all_observations=False)
            self.assertEqual(instrument.execute(args),0)
            self.assertEqual(receipt_review.review([base])['session_count'],1)
            tone=next((base/'src-raw').rglob('pass-000.f64'))
            data=tone.read_bytes()
            tone.write_bytes(data[:-1]+bytes([data[-1]^1]))
            with self.assertRaisesRegex(ValueError,'tampered/missing SRC raw'):
                receipt_review.review([base])
            tone.write_bytes(data)
            graph=next((base/'graph-raw').rglob('one_thread_tiny_chunks.wav'))
            data=graph.read_bytes()
            graph.write_bytes(data[:-1]+bytes([data[-1]^1]))
            with self.assertRaisesRegex(ValueError,'missing/changed raw graph'):
                receipt_review.review([base])
            graph.write_bytes(data)
            args.resume=True
            self.assertEqual(instrument.execute(args),0)
            self.assertEqual(receipt_review.review([base])['session_count'],1)
            # A forged detailed ISA statistic with a freshly written JSON
            # checksum must not be accepted as a genuine comparison.
            row=next((base/'cells').glob('*.json'))
            old=row.read_bytes()
            forged=json.loads(old)
            forged['cross_isa'][0]['impulse_detail'][0]['same_cell_scalar']['max_abs']+=.01
            row.write_text(json.dumps(forged))
            row.with_suffix('.sha256').write_text(instrument.file_hash(row)+'\n')
            with self.assertRaisesRegex(ValueError,'scalar_impulse'):
                receipt_review.review([base])
            row.write_bytes(old)
            row.with_suffix('.sha256').write_text(instrument.file_hash(row)+'\n')
            self.assertEqual(receipt_review.review([base])['session_count'],1)


if __name__=='__main__':
    unittest.main(verbosity=2)

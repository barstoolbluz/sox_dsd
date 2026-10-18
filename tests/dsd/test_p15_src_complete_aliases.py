"""Exact alias lattice and native-FIR/SRC composition conformance tests."""
from p15_src_capture_matrix import DEFAULT as ACTIVE_STAGE_ROOT
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest

import mpmath as mp
import numpy as np

from p15_src_bound_operator import SRCOperator,Stage,UnboundOperator,load_snapshot
from p15_src_complete_aliases import (alias_families,complete_sample,
        native_profile,snapshot_receipt,src_image_coefficients)
from p15_src_full_chain import full_period,native_composite_gain
from p15_numerical_reference import equivalent_exact

ROOT=Path(__file__).resolve().parents[2]
RESULTS=ACTIVE_STAGE_ROOT


def synthetic_identity():
    stage=Stage(kind=3,order=0,n=2,L=1,M=1,phases=1,phase_bits=0,
        preload=0,pre=0,pre_post=1,dft_taps=0,dft_length=0,dft_post_peak=0,
        remL=0,remM=0,at_i64=0,step_i64=1<<32,
        coeff=(1.,0.),fft_bins=())
    return SRCOperator(44100,44100,(stage,))

class CompleteAliasing(unittest.TestCase):
    def test_exact_nyquist_half_open_and_all_families(self):
        op=synthetic_identity()
        for f in (0,Fraction(1,2),22050):
            fam=alias_families(2822400,op,f)
            self.assertEqual(len(fam),64)
            self.assertEqual(len(set(x.source_hz for x in fam)),64)
            self.assertEqual(sum(x.desired for x in fam),1)
            self.assertEqual(fam[0].source_hz>=-1411200,True)
            self.assertEqual(fam[-1].source_hz<1411200,True)
            self.assertEqual((fam[-1].source_hz-fam[0].source_hz)/44100,63)
        with self.assertRaises(UnboundOperator):alias_families(88201,op,1000)
        with self.assertRaises(UnboundOperator):alias_families(2822400,op,22051)

    def test_synthetic_pure_delta_has_no_spurious_alias(self):
        op=synthetic_identity()
        self.assertEqual(op.row(17),((17,1.),))
        amps=src_image_coefficients(op,Fraction(1200,7))
        self.assertEqual(len(amps),1)
        self.assertAlmostEqual(abs(amps[0]),1,places=14)

    @unittest.skipUnless(RESULTS.is_dir(),'current source-bound stage receipts missing')
    def test_native_and_src_phase_product_uses_all_stages(self):
        op=load_snapshot(RESULTS/'352800-48000/stage-snapshot.json')
        self.assertEqual(full_period('wide256',op),(32*294,40))
        native,R,_,_=native_profile('wide256')
        self.assertEqual((native,R),(11289600,352800))
        # Independent exact native-bank FIR witness + exact-stage row.
        coeff, delay,D=equivalent_exact('wide256')
        self.assertEqual(len(coeff),2*delay+1)
        row=op.exact_row(0,3)
        sample=native_composite_gain('wide256',op,0,0,native_frames=3*D)
        with mp.workdps(75):
            oracle=mp.fsum(x*coeff[delay+j*D] for j,x in row.items()
                           if 0<=delay+j*D<len(coeff))
            self.assertEqual(sample,oracle)

    @unittest.skipUnless(RESULTS.is_dir(),'current source-bound stage receipts missing')
    def test_full_lattice_on_real_two_clock_routes(self):
        for input_hz,output_hz,profile in [(88200,48000,'master64'),
                                          (352800,48000,'wide256')]:
            with self.subTest(rate=(input_hz,output_hz)):
                path=RESULTS/f'{input_hz}-{output_hz}'/'stage-snapshot.json'
                op=load_snapshot(path)
                native,_,_,_=native_profile(profile)
                for f in (0,Fraction(1000),Fraction(output_hz,2)):
                    families=alias_families(native,op,f)
                    self.assertEqual(len(families),native*op.U//output_hz)
                    self.assertEqual(len(families),native//(output_hz/op.U))
                    self.assertEqual(sum(x.desired for x in families),1)
                    self.assertEqual(len(set(x.s for x in families)),len(families))
                    self.assertEqual(len({x.src_residue for x in families}),op.V)

    @unittest.skipUnless((ROOT/'test/dsd_test_p07_reference').is_file(),
                         'unmodified production P07 export probe not built')
    def test_source_bound_real_production_finite_edges(self):
        from p15_src_full_chain import verify_real_composite,verify_real_src_impulses
        probe=ROOT/'test/dsd_test_p07_reference'
        for R,F,profile in ((88200,48000,'master64'),
                            (352800,48000,'wide256'),
                            (176400,48000,'decode.mastering.v2.dsd256')):
            with self.subTest(route=(R,F,profile)):
                op=load_snapshot(RESULTS/f'{R}-{F}/stage-snapshot.json')
                result=verify_real_composite(probe,profile,op)
                self.assertLess(result['maximum_observed_disagreement'],1e-8,
                         'diagnostic model regression, not an arithmetic acceptance threshold')
                self.assertIs(result['qualified'],False)
        op=load_snapshot(RESULTS/'88200-48000/stage-snapshot.json')
        result=verify_real_src_impulses(probe,op,frames=4096,anchors=(0,1,2048,4095))
        self.assertTrue(all(x['maximum_absolute_observed_disagreement']<1e-8
                            for x in result['checked']))
        self.assertIs(result['qualified'],False)

    @unittest.skipUnless(RESULTS.is_dir(),'current source-bound stage receipts missing')
    def test_coherent_non_rms_complete_sample_and_binding(self):
        base=RESULTS/'88200-48000'/'stage-snapshot.json'
        sample=snapshot_receipt(base,'master64',1000)
        report=sample['sample']
        self.assertEqual(report['alias_family_count'],32*147)
        self.assertGreater(report['coherent_unwanted_abs'],0)
        self.assertEqual(report['status'],'SAMPLED_DIAGNOSTIC_UNCERTIFIED')
        self.assertIs(report['qualified'],False)
        self.assertGreaterEqual(report['coherent_including_wanted_abs'],
                                report['coherent_unwanted_abs']+report['wanted_abs']-1e-12)
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);q=d/'stage-snapshot.json';q.write_bytes(base.read_bytes())
            (d/'operator-binding.json').write_bytes((base.parent/'operator-binding.json').read_bytes())
            o=json.loads(q.read_text());o['stages'][0]['coefficients'][0]='0x1.000p-13'
            q.write_text(json.dumps(o))
            with self.assertRaises(UnboundOperator):snapshot_receipt(q,'master64',1000)


if __name__=='__main__':unittest.main()

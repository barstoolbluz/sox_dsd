#!/usr/bin/env python3
"""Focused additive v2 metrology contract, certificate and replay regressions.

Does not rewrite any committed v1 receipt. Optional built-probe tests run only
with P15_LIVE=1 and P15_PROBE set to a prepared real decoder exporter.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p15_matrix_contract import make_plan, write_json_atomic
from p15_matrix_instrument import (PROBE_RE, SPEC, SPEC_V2,
                                   inherited_fir_certificate, run_probe, native_bits)
import p15_graph_integration as graph
import p15_numerical_reference as reference
from p15_matrix_receipt_review import review

ROOT = Path(__file__).resolve().parents[2]


class P15V2Plan(unittest.TestCase):
    def test_frozen_v1_plan_is_semantically_byte_for_byte_unchanged(self):
        original = json.loads((ROOT/'tests/dsd/results/P15_R3_matrix_2026-10-15/scalar/worklist.json').read_text())
        self.assertEqual(json.loads(json.dumps(make_plan())), original)
        self.assertEqual(make_plan()['summary']['scalar_cells'], 54)
        self.assertEqual(make_plan()['schema'], 'P15/decode-numerical-worklist/1')

    def test_v2_requires_exactly_27_mastering_cells_and_distinct_schema(self):
        plan = make_plan('v2')
        self.assertEqual(plan['summary'], dict(
            scalar_cells=27, integer_reference_cells=15, fractional_reference_cells=12,
            all_tier_functional_jobs=135, minimum_detailed_cross_isa_jobs=48,
            independent_metrology_passed=0))
        self.assertEqual(len(set(x['id'] for x in plan['scalar_cells'])), 27)
        self.assertEqual({x['profile'] for x in plan['scalar_cells']}, {'mastering_v2'})
        self.assertNotEqual(plan['schema'], make_plan()['schema'])
        self.assertFalse(plan['qualified'])
        self.assertEqual({x['status'] for x in plan['scalar_cells']}, {'UNRUN'})
        with self.assertRaises(ValueError):
            make_plan('v3')

    def test_probe_receipt_accepts_real_v2_id_but_not_masquerading_v1(self):
        receipt=('P15_PROBE_OK native=2822400 pcm=48000 profile=mastering_v2 '
                 'tier=scalar channels=1 input=128 output=2 chunk=17 level=preserve')
        self.assertIsNotNone(PROBE_RE.fullmatch(receipt))
        self.assertIsNone(PROBE_RE.fullmatch(receipt.replace('mastering_v2', 'mastering-v2')))
        self.assertEqual(graph.pinned_decoder_profile(2822400,'mastering_v2'),
                         'decode.mastering.v2.dsd64')
        self.assertEqual(graph.pinned_decoder_profile(5644800,'mastering_v2'),
                         'decode.mastering.v2.dsd128')
        self.assertEqual(graph.pinned_decoder_profile(11289600,'mastering_v2'),
                         'decode.mastering.v2.dsd256')
        self.assertEqual(graph.pinned_decoder_profile(2822400,'mastering'),
                         'decode.mastering.v1.dsd64')
        with self.assertRaises(ValueError):
            graph.pinned_decoder_profile(2822400,'mastering_v3')

    def test_v2_reference_uses_exact_production_words_and_certificates(self):
        v1 = reference.bank_data('v1')
        meta, banks = reference.bank_data('v2')
        self.assertTrue(np.array_equal(banks['halfband'], v1[1]['halfband']))
        self.assertEqual(len(meta['profiles']), 3)
        for native in (2822400, 5644800, 11289600):
            name = reference.profile_name('mastering_v2', native)
            self.assertEqual(meta['profiles'][name]['native_hz'], native)
            self.assertEqual(reference.bank_data_for_profile(name)[0]['schema'],
                             'sox-ng/p15-r3-coefficients/1')
        proof = inherited_fir_certificate('v2')
        self.assertEqual(proof['status'], 'P15_R3_V2_NATIVE_FIR_CERTIFICATE_VERIFIED')
        self.assertEqual(proof['three_profiles'], 3)
        self.assertEqual(proof['v1_halfband']['six_profiles'], 6)
        self.assertNotEqual(proof['sha256'], proof['v1_halfband']['sha256'])
        self.assertEqual(inherited_fir_certificate()['status'],
                         'P06_NATIVE_FIR_CERTIFICATE_VERIFIED')

    def test_v2_header_word_corruption_fails_closed(self):
        original = reference.V2_BANKS
        with tempfile.TemporaryDirectory() as tmp:
            alternate = Path(tmp)/'v2.h'
            source = original.read_text()
            self.assertIn('0x', source)
            alternate.write_text(source.replace('0x', '0y', 1))
            try:
                reference.V2_BANKS = alternate
                reference.bank_data.cache_clear()
                with self.assertRaises((ValueError, AssertionError)):
                    reference.bank_data('v2')
            finally:
                reference.V2_BANKS = original
                reference.bank_data.cache_clear()

    def test_v2_high_precision_convolution_is_centered_and_finite(self):
        for native in (2822400, 5644800, 11289600):
            name = reference.profile_name('mastering_v2', native)
            _, delay, factor = reference.equivalent_exact(name)
            manifest, _ = reference.bank_data('v2')
            meta = manifest['profiles'][name]
            self.assertEqual((delay, factor), (meta['delay_native_frames'],meta['factor']))
            for n in (0, 1, factor-1, factor, factor+1):
                bits = (np.arange(n)%3==0).astype(np.uint8)
                got = reference.front_end(bits, name)
                self.assertEqual(len(got), (n+factor-1)//factor)
                self.assertTrue(np.all(np.isfinite(got)))
            zero = np.zeros(1024, dtype=np.uint8)
            _, converted = reference.reference(zero, name, native, 48000)
            self.assertEqual(len(converted), (1024*48000+native//2)//native)

    def test_v2_reviewer_requires_v2_binding_and_complete_27(self):
        plan = make_plan('v2')
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            binding = dict(schema=SPEC_V2,
                           worklist_sha256=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest(),
                           mode='development-subset', tiers=['scalar'], cells=[], frames=8192,src_frames=8192,
                           reference_inputs={'tests/dsd/p15_matrix_contract.py':
                               hashlib.sha256((ROOT/'tests/dsd/p15_matrix_contract.py').read_bytes()).hexdigest()},
                           production_exporter_sha256='0'*64,runtime={'host':'untrusted-fixture'})
            write_json_atomic(directory/'session.json', binding)
            write_json_atomic(directory/'worklist.json', plan)
            result = review([directory], matrix='v2')
            self.assertEqual(result['expected_scalar_cells'], 27)
            self.assertEqual(result['expected_forced_isa_jobs'], 108)
            self.assertEqual(result['expected_detailed_jobs'], 48)
            self.assertEqual(len(result['remaining_scalar_cells']), 27)
            self.assertFalse(result['release_gate_closed'])
            with self.assertRaisesRegex(ValueError,'incompatible binding'):
                review([directory], matrix='v1')
            binding['worklist_sha256'] = '0'*64
            write_json_atomic(directory/'session.json',binding)
            with self.assertRaisesRegex(ValueError,'incompatible binding'):
                review([directory],matrix='v2')

    @unittest.skipUnless(os.environ.get('P15_LIVE')=='1', 'optional built probe test')
    def test_actual_v2_decoder_distinct_from_v1_and_exact_small_count(self):
        probe=Path(os.environ.get('P15_PROBE',str(ROOT/'test/dsd_test_p15_instrument')))
        if not probe.is_file():
            self.skipTest('no built instrument C exporter')
        stimulus=native_bits(8193,2822400)
        v2,_=run_probe(probe,native=2822400,pcm=88200,profile='mastering_v2',
                       tier='scalar',stimulus=stimulus,chunk=31)
        v1,_=run_probe(probe,native=2822400,pcm=88200,profile='mastering',
                       tier='scalar',stimulus=stimulus,chunk=31)
        self.assertEqual(v2.shape, v1.shape)
        self.assertFalse(np.array_equal(v2, v1))


if __name__ == '__main__':
    unittest.main()

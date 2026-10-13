#!/usr/bin/env python3
"""Self-tests for the P15 question-resolution plan and physical-host guard.

These are policy/tool tests. They are NOT 54 independent measured spectra.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p15_matrix_contract as matrix
from check_p15_avx1_receipt import inspect_receipt, BENCH_SOURCES
from p15_compare_cross_host import compare
from reference import fixtures


class Worklist(unittest.TestCase):
    def test_no_false_numerical_certificate(self):
        result = matrix.make_plan()
        self.assertEqual(result['status'], 'PLAN_ONLY_NOT_EXECUTED')
        self.assertFalse(result['qualified'])
        self.assertEqual(result['summary']['independent_metrology_passed'], 0)
        self.assertTrue(all(r['status'] == 'UNRUN' for r in result['scalar_cells']))

    def test_all_cells_reference_families_and_ratios(self):
        result = matrix.make_plan()
        cells = result['scalar_cells']
        self.assertEqual(len(cells), 54)
        self.assertEqual(len({x['id'] for x in cells}), 54)
        self.assertEqual(sum('decimated-convolution' in x['reference_type'] for x in cells), 30)
        self.assertEqual(sum('rational-src' in x['reference_type'] for x in cells), 24)
        self.assertEqual({x['pcm_hz'] for x in cells}, set(matrix.PCM_RATES))
        self.assertEqual({x['native_hz'] for x in cells}, set(matrix.NATIVE_RATES))
        self.assertEqual({x['profile'] for x in cells}, set(matrix.PROFILES))
        self.assertEqual({x['reference_type'] for x in cells if x['pcm_hz'] == 48000},
                         {'independent-high-precision-rational-src-of-reconstruction'})
        self.assertEqual({x['reference_type'] for x in cells if x['pcm_hz'] == 705600},
                         {'independent-high-precision-finite-decimated-convolution'})
        self.assertTrue(all(x['output_per_native'].count('/') == 1 for x in cells))

    def test_all_tier_grid_and_selected_detailed_grid(self):
        result = matrix.make_plan()
        all_jobs = result['release_forced_isa_functional']
        detail = result['selected_cross_isa_detail']
        self.assertEqual(len(all_jobs), 270)
        self.assertEqual(len({(j['cell'], j['tier']) for j in all_jobs}), 270)
        self.assertEqual(len(detail), 96)
        self.assertEqual(len({(j['cell'], j['tier']) for j in detail}), 96)
        by_cell = {j['id']: j for j in result['scalar_cells']}
        for native in matrix.NATIVE_RATES:
            for profile in matrix.PROFILES:
                these = [j for j in detail if by_cell[j['cell']]['native_hz'] == native
                         and by_cell[j['cell']]['profile'] == profile]
                self.assertEqual({by_cell[j['cell']]['pcm_hz'] for j in these},
                                 set(matrix.CROSS_ISA_DETAIL_ENDPOINTS))
        self.assertTrue(all('scalar' != j['tier'] for j in detail))
        self.assertTrue(all(j['status'] == 'UNRUN' for j in all_jobs + detail))

    def test_atomic_deterministic_worklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'nested' / 'plan.json'
            matrix.write_json_atomic(out, matrix.make_plan())
            first = out.read_bytes()
            matrix.write_json_atomic(out, matrix.make_plan())
            self.assertEqual(first, out.read_bytes())
            self.assertEqual(json.loads(first)['summary']['scalar_cells'], 54)
            self.assertEqual(list(out.parent.iterdir()), [out])


class PhysicalOlderAvxReview(unittest.TestCase):
    def _complete_fixture(self, root: Path, *, avx2='no'):
        root.mkdir(parents=True, exist_ok=True)
        (root/'kernel').mkdir(exist_ok=True)
        (root/'host.txt').write_text('model name : Physical Test CPU\nmicrocode 0x01\n'
                                       f'avx / avx2 yes / {avx2}\n'
                                       'virt none (hypervisor flag absent)\n')
        (root/'gate-eligibility.txt').write_text('gate_relevant=yes\n')
        (root/'clock.txt').write_text(''.join(
            f'  {tier} median 3000 MHz p10 3000 p90 3000 busy samples 50 of 52\n'
            for tier in ('scalar','sse2','avx1')))
        (root/'kernel.log').write_text('P15 benchmark PASS\n')
        (root/'kernel-output-sha256.txt').write_text('synthetic unit fixture only\n')
        raw = [dict(mode=mode, tier=tier, round=i, exit=0) for mode in
               ('fir-single','fir-block','sdm') for tier in ('scalar','sse2','avx1')
               for i in range(15)]
        repository = Path(__file__).resolve().parents[2]
        record = dict(status='PASS', errors=[], unrun=[], raw=raw,
                      config=dict(repetitions=15, modes=['fir-single','fir-block','sdm'],
                                  tiers=['scalar','sse2','avx1']),
                      source_sha256={relative: hashlib.sha256(
                          (repository/relative).read_bytes()).hexdigest()
                          for relative in BENCH_SOURCES})
        (root/'kernel/kernel-timing.json').write_text(json.dumps(record))

    def test_bad_attached_host_and_no_raw_is_blocked(self):
        # Originally this asserted against the live
        # results/P15_avx1_physical_2026-10-13 directory while that directory
        # held a contradictory host.txt and no raw receipts. A test pinned to a
        # real directory being broken becomes wrong the moment the directory is
        # repaired, which is what happened: the operator delivered the genuine
        # Xeon E5-1680 v2 artifacts and the checker now reports
        # ADMISSIBLE_FOR_INDEPENDENT_REVIEW. The adjudication's intent was that
        # a wrong-host record with absent receipts must block, so that is what
        # is asserted here, against a fixture the test owns.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.mkdir(parents=True, exist_ok=True)
            (root/'host.txt').write_text(
                'model name : AMD Ryzen Threadripper 7970X 32-Cores\n'
                'avx / avx2  yes / yes\n'
                'virt none (hypervisor flag absent)\n')
            result = inspect_receipt(root)
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertFalse(result['ready_for_release'])
            self.assertTrue(any('AVX1 without AVX2' in p for p in result['problems']))
            self.assertTrue(any('missing or empty raw receipt' in p
                                for p in result['problems']))

    def test_delivered_physical_record_is_admissible(self):
        # The live directory, once the operator's artifacts were delivered.
        directory = Path(__file__).resolve().parent/'results/P15_avx1_physical_2026-10-13'
        result = inspect_receipt(directory)
        self.assertEqual(result['status'], 'ADMISSIBLE_FOR_INDEPENDENT_REVIEW')
        self.assertEqual(result['problems'], [])
        self.assertFalse(result['ready_for_release'])

    def test_expected_eligible_provenance_not_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._complete_fixture(root)
            r = inspect_receipt(root)
            self.assertEqual(r['status'], 'ADMISSIBLE_FOR_INDEPENDENT_REVIEW')
            self.assertFalse(r['ready_for_release'])
            self.assertFalse(r['cross_host_byte_hash_requirement'])

    def test_avx2_or_missing_times_rejected_even_if_self_labeled_gate_yes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._complete_fixture(root, avx2='yes')
            r = inspect_receipt(root)
            self.assertEqual(r['status'], 'BLOCKED')
            self.assertTrue(any('AVX1 without AVX2' in p for p in r['problems']))
            (root/'clock.txt').unlink()
            r = inspect_receipt(root)
            self.assertTrue(any('clock.txt' in p for p in r['problems']))

    def test_repetitions_source_binding_and_host_virtualization_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._complete_fixture(root)
            p = root/'kernel/kernel-timing.json'
            result = json.loads(p.read_text())
            result['raw'] = result['raw'][:-1]
            result['source_sha256']['src/dsd_dispatch.c'] = '0'*64
            p.write_text(json.dumps(result))
            host = root/'host.txt'
            host.write_text(host.read_text().replace('none (hypervisor flag absent)',
                                                      'kvm (hypervisor flag PRESENT)'))
            r = inspect_receipt(root)
            self.assertEqual(r['status'], 'BLOCKED')
            self.assertTrue(any('raw benchmark repetitions incomplete' in p for p in r['problems']))
            self.assertTrue(any('benchmark source hash differs' in p for p in r['problems']))
            self.assertTrue(any('nonvirtualized' in p for p in r['problems']))


class HostOutputComparison(unittest.TestCase):
    def test_identical_source_and_bit_chronology(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wav_a = root/'a.wav'
            wav_b = root/'b.wav'
            wav_a.write_bytes(b'fixture source bytes')
            wav_b.write_bytes(wav_a.read_bytes())
            bits = fixtures.bits(513, 1, '69')
            dsf_a = root/'a.dsf'; dsf_b = root/'b.dsf'
            dsf_a.write_bytes(fixtures.make_dsf(bits))
            dsf_b.write_bytes(dsf_a.read_bytes())
            result = compare(wav_a, wav_b, dsf_a, dsf_b)
            self.assertEqual(result['status'], 'MATCHING_AUDIO')
            self.assertTrue(result['chronological_bits_identical'])
            self.assertFalse(result['cross_host_scalar_bit_equality_required'])
            other = fixtures.bits(513, 1, 'zeros')
            dsf_b.write_bytes(fixtures.make_dsf(other))
            result = compare(wav_a, wav_b, dsf_a, dsf_b)
            self.assertEqual(result['status'], 'AUDIO_DIFFERS_NEEDS_METROLOGY')
            self.assertFalse(result['chronological_bits_identical'])
            wav_b.write_bytes(b'different source')
            result = compare(wav_a, wav_b, dsf_a, dsf_b)
            self.assertEqual(result['status'], 'SOURCE_MISMATCH')
            self.assertNotIn('native', result)


if __name__ == '__main__':
    unittest.main()

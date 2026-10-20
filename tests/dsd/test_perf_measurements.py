#!/usr/bin/env python3
"""Regression tests for investigation tooling, not performance thresholds."""
from __future__ import annotations
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
UNIT = Path(os.environ.get('DSD_BENCH_UNIT', str(ROOT / 'test/dsd_test_p11'))).resolve()


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tests/dsd' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


profile = load('profile_decode')
matrix = load('bench_p13_matrix')
sys.path.insert(0, str(ROOT / 'tests/dsd'))
from reference import fixtures


class MeasurementTests(unittest.TestCase):
    def bench(self, tier, mode, frames=16384):
        result = subprocess.run([str(UNIT), '--bench', tier, mode, str(frames)],
                                capture_output=True, text=True, timeout=30)
        if result.returncode == 2:
            return None
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_production_bank_metadata(self):
        cases = (('halfband', 57, True, 'halfband-57'),
                 ('master64', 117, False, 'master64-256-117'),
                 ('master128', 153, False, 'master128-153'),
                 ('wideband', 257, False, 'wideband-257'))
        for bank, taps, halfband, name in cases:
            for kind in ('single', 'block'):
                with self.subTest(bank=bank, kind=kind):
                    row = self.bench('scalar', f'fir-{bank}-{kind}')
                    self.assertEqual((row['taps'], row['halfband'], row['stride']),
                                     (taps, halfband, 2))
                    self.assertEqual(row['coefficient_bank'], name)
                    self.assertEqual(row['frame_unit'], 'FIR output')
                    self.assertFalse(row['guards_active'])
                    self.assertTrue(math.isfinite(row['cpu_ns_per_frame']))
                    self.assertGreater(row['cpu_ns_per_frame'], 0)

    def test_original_workloads_remain_explicitly_synthetic(self):
        single = self.bench('scalar', 'fir-single')
        block = self.bench('scalar', 'fir-block')
        for row in (single, block):
            self.assertEqual((row['taps'], row['stride'], row['halfband']), (153, 1, False))
            self.assertEqual(row['coefficient_bank'], 'synthetic-dense-153')
        self.assertEqual(single['checksum'], block['checksum'])
        row = self.bench('scalar', 'sdm')
        self.assertEqual(row['state_bounds'], 'synthetic 1e18')
        self.assertTrue(row['guards_active'] and row['monitor_active'])
        self.assertEqual(row['frame_unit'], 'native SDM output')

    def test_single_and_block_checksums_for_production_banks(self):
        for bank in ('halfband', 'master64', 'master128', 'wideband'):
            ref = self.bench('scalar', f'fir-{bank}-single')['checksum']
            for tier in profile.TIERS:
                for kind in ('single', 'block'):
                    with self.subTest(bank=bank, tier=tier, kind=kind):
                        row = self.bench(tier, f'fir-{bank}-{kind}')
                        if row is not None:
                            self.assertTrue(math.isclose(ref, row['checksum'],
                                rel_tol=1e-12, abs_tol=1e-13), row)

    def test_invalid_benchmark_shape_rejected(self):
        for mode, frames in (('fir-no-such-case', 16384), ('fir-halfband-single', 0),
                             ('fir-halfband-single', 40000001)):
            cp = subprocess.run([str(UNIT), '--bench', 'scalar', mode, str(frames)],
                                capture_output=True, timeout=30)
            self.assertEqual(cp.returncode, 3)

    def test_python_driver_records_selected_modes_and_all_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp = subprocess.run([sys.executable, str(ROOT / 'tests/dsd/bench_p11.py'),
                '--unit', str(UNIT), '--results', tmp, '--repetitions', '1',
                '--frames', '16384', '--tiers', 'scalar', '--modes',
                'fir-halfband-single', 'fir-master64-block'], capture_output=True,
                text=True, timeout=30)
            self.assertEqual(cp.returncode, 0, cp.stderr)
            data = json.loads((Path(tmp) / 'kernel-timing.json').read_text())
            self.assertEqual(data['status'], 'PASS')
            self.assertEqual(set(data['summary']), {'fir-halfband-single', 'fir-master64-block'})
            self.assertIn('src/dsd_kernels_avx512.c', data['source_sha256'])
            self.assertIn('src/dsd_coeffs.h', data['source_sha256'])
            self.assertEqual(len(data['raw']), 2)

    def test_duplicate_driver_modes_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp = subprocess.run([sys.executable, str(ROOT / 'tests/dsd/bench_p11.py'),
                '--unit', str(UNIT), '--results', tmp, '--modes', 'fir-single', 'fir-single'],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(cp.returncode, 2)
            self.assertFalse((Path(tmp) / 'kernel-timing.json').exists())

    def test_host_without_hypervisor_flag_is_not_certified_or_called_virtual(self):
        row = matrix.host_observation('vendor_id : AuthenticAMD\nmodel name : 7970X\nflags : sse2 avx2\n')
        self.assertFalse(row['hypervisor_flag_observed'])
        self.assertEqual(row['cpu_model'], '7970X')
        self.assertIn('not established', row['virtualization'])
        self.assertNotIn('virtualized', row['virtualization'])
        self.assertEqual(row['hardware_qualification'], 'not assessed by this timing runner')

    def test_host_with_hypervisor_flag_and_unavailable_cpuinfo(self):
        self.assertTrue(matrix.host_observation('flags: avx hypervisor\n')['hypervisor_flag_observed'])
        self.assertIsNone(matrix.host_observation('')['hypervisor_flag_observed'])

    def test_fixture_against_existing_bit_chronology_oracle(self):
        with tempfile.TemporaryDirectory() as tmp:
            for channels in (1, 2, 6):
                for frames in (1, 33, 32769):
                    with self.subTest(channels=channels, frames=frames):
                        path = Path(tmp) / 'fixture.dsf'
                        profile.make_fixture(path, profile.RATES[0], channels, frames)
                        rng = random.Random(profile.SEED)
                        timelines = [bytearray() for _ in range(channels)]
                        for start in range(0, frames, 32768):
                            count = min(32768, frames-start)
                            for c in range(channels):
                                packed = rng.getrandbits(32768).to_bytes(4096, 'little')
                                timelines[c].extend((packed[i//8] >> (i % 8)) & 1 for i in range(count))
                        expected = fixtures.make_dsf(tuple(map(bytes, timelines)))
                        self.assertEqual(path.read_bytes(), expected)
                        self.assertFalse(path.with_name(path.name + '.tmp').exists())

    def test_fixture_rejects_invalid_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            for rate, channels, frames in ((1, 2, 33), (2822400, 0, 33), (2822400, 2, 0)):
                with self.assertRaises(ValueError):
                    profile.make_fixture(Path(tmp) / 'bad.dsf', rate, channels, frames)

    def test_profile_parser_retains_correct_denominator(self):
        text = ('Each sample counts as 0.01 seconds.\n'
                ' 66.67 0.02 0.02 symbol_a\n 33.33 0.03 0.01 symbol_b\n')
        parsed = profile.parse_flat_profile(text)
        self.assertAlmostEqual(parsed['sampled_executable_seconds'], .03)
        self.assertEqual(parsed['sample_period_seconds'], .01)
        self.assertIn('not total wall time', parsed['denominator'])
        with self.assertRaises(ValueError):
            profile.parse_flat_profile('no time accumulated')

    def test_blocking_runner_captures_files_and_enforces_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with (directory / 'out').open('w') as out, (directory / 'err').open('w') as err:
                status, expired = profile.run_bounded([sys.executable, '-c',
                    'import sys; print("output"); print("diagnostic", file=sys.stderr)'],
                    cwd=directory, env=dict(os.environ), stdout=out, stderr=err, timeout=5)
            self.assertEqual((status, expired), (0, False))
            self.assertEqual((directory / 'out').read_text(), 'output\n')
            self.assertEqual((directory / 'err').read_text(), 'diagnostic\n')
            with (directory / 'out').open('w') as out, (directory / 'err').open('w') as err:
                status, expired = profile.run_bounded([sys.executable, '-c',
                    'import time; time.sleep(30)'], cwd=directory, env=dict(os.environ),
                    stdout=out, stderr=err, timeout=.1)
            self.assertTrue(expired)
            self.assertNotEqual(status, 0)

    def test_existing_evidence_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'prior.json'
            path.write_text('retained\n')
            cp = subprocess.run([sys.executable, str(ROOT / 'tests/dsd/profile_decode.py'),
                '--sox', str(ROOT / 'src/sox'), '--profile-sox', str(ROOT / 'src/sox'),
                '--results', tmp], capture_output=True, text=True, timeout=30)
            self.assertEqual(cp.returncode, 2)
            self.assertEqual(path.read_text(), 'retained\n')


if __name__ == '__main__':
    unittest.main()

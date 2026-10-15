"""Small, independent regression checks for P15 re-adjudication decisions.

No historical evidence file is written by these tests. Fault injection always
uses a temporary copy, not the source archive's measured receipts.
"""
from __future__ import annotations

from pathlib import Path
import re
import shutil
import tempfile
import unittest

import p15_readjudication as judge


class TestReadjudication(unittest.TestCase):
    def test_native_soak_snapshot_chain_and_one_missing_state_refused(self):
        src = judge.SOAKS / 'scalar'
        with tempfile.TemporaryDirectory() as directory:
            dst = Path(directory) / 'scalar'
            dst.mkdir()
            for f in src.glob('soak-2822400-*'):
                if f.is_file():
                    shutil.copy2(f, dst / f.name)
            bounds = judge.read_json(judge.ROOT / 'tests/dsd/reference/p10_guards.json')
            good = judge.inspect_soak_run(dst, 2822400, bounds)
            self.assertEqual(good['snapshots_verified'], 61)
            (dst / 'soak-2822400-0033.state').unlink()
            with self.assertRaisesRegex(judge.EvidenceError, 'continuation snapshot'):
                judge.inspect_soak_run(dst, 2822400, bounds)

    def test_truncated_and_nonfinite_state_refused(self):
        original = judge.SOAKS / 'scalar' / 'soak-2822400-0001.state'
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'state'
            data = original.read_text()
            for corrupt in (data.rsplit('\n', 2)[0],
                            re.sub(r'state0_0=[^\n]*', 'state0_0=nan', data)):
                file.write_text(corrupt)
                with self.assertRaises(judge.EvidenceError):
                    judge.check_state(file)

    def test_repeated_timing_values_and_ci_are_recomputed(self):
        obj = judge.read_json(judge.R2 / 'dsd256-2x.json')
        result = judge.inspect_benchmark(obj)
        self.assertEqual(result['disposition'], 'OPEN-CONTROL-NOT-BANDWIDTH-MATCHED')
        self.assertTrue(all(not row['actual_bandwidth_matched_control_verified']
                            for row in result['output_rates'].values()))
        self.assertTrue(all(row['direct_reference_median_speedup'] > 3.7
                            for row in result['output_rates'].values()))

    def test_timing_corruption_refused(self):
        obj = judge.read_json(judge.R2 / 'dsd256-2x.json')
        obj['rows']['176400']['decoder']['repetitions'][5] *= 2
        with self.assertRaisesRegex(judge.EvidenceError, 'timing summary'):
            judge.inspect_benchmark(obj)

    def test_faked_staged_cutoff_refused_until_readjudicated(self):
        obj = judge.read_json(judge.R2 / 'dsd256-2x.json')
        obj['rows']['176400']['legacy_staged_matched']['command'][-3] = '-40000'
        with self.assertRaisesRegex(judge.EvidenceError, 'unreviewed staged'):
            judge.inspect_benchmark(obj)

    def test_intel_amendment_never_claims_pass(self):
        obj = judge.inspect_amendment()
        self.assertEqual(obj['physical_test_execution'], 'UNRUN')
        self.assertIn('EXEMPT', obj['disposition'])

    def test_adjudication_writer_is_idempotent_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'review.json'
            original = {'schema': 'test', 'qualified': False}
            judge.write_new(path, original)
            first = path.read_bytes()
            judge.write_new(path, original)
            self.assertEqual(path.read_bytes(), first)
            with self.assertRaisesRegex(judge.EvidenceError, 'differs'):
                judge.write_new(path, {'schema': 'test', 'qualified': True})
            self.assertEqual(path.read_bytes(), first)


if __name__ == '__main__':
    unittest.main()

"""Adversarial executable recovery tests; require the compiled P15 C exporter.

Run:
  P15_SRC_STAGE_EXPORTER=/build/test/dsd_test_p15_src_stage_export \
    python3 -m unittest discover -s tests/dsd -p test_operator_rebind_recovery.py -v
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from recover_p15_src_operator_rebind import (DEFAULT, DEFAULT_AUDIT,
                                             UnboundOperator, recover)


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exporter = Path(os.environ.get('P15_SRC_STAGE_EXPORTER',
                               str(ROOT / 'test/dsd_test_p15_src_stage_export')))
        if not cls.exporter.is_file():
            raise unittest.SkipTest('compiled source-specific C exporter not present')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='p15-recovery-test-')
        self.addCleanup(self.temp.cleanup)
        self.active = Path(self.temp.name) / 'active'
        shutil.copytree(DEFAULT, self.active)

    def test_interrupted_publication_is_read_only_then_resumable_and_idempotent(self):
        for pair in ('176400-192000', '352800-48000', '88200-96000'):
            old = (DEFAULT_AUDIT / 'previous_bindings' / (pair + '.json')).read_bytes()
            (self.active / pair / 'operator-binding.json').write_bytes(old)
        old_summary = (DEFAULT_AUDIT / 'preimages' / 'tests/dsd/results'
                       / 'P15_SRC_STAGE_BOUND_OPT_2026-10-17/SUMMARY.json').read_bytes()
        (self.active / 'SUMMARY.json').write_bytes(old_summary)
        check = recover(self.exporter, DEFAULT_AUDIT, False, self.active)
        self.assertEqual(check['replacements_needed'], 3)
        self.assertFalse(check['summary_already_current'])
        self.assertEqual((self.active/'SUMMARY.json').read_bytes(), old_summary)
        commit = recover(self.exporter, DEFAULT_AUDIT, True, self.active)
        self.assertEqual(commit['replacements_needed'], 3)
        again = recover(self.exporter, DEFAULT_AUDIT, True, self.active)
        self.assertEqual(again['replacements_needed'], 0)
        self.assertTrue(again['summary_already_current'])
        self.assertEqual((self.active/'SUMMARY.json').read_bytes(),
                         (DEFAULT/'SUMMARY.json').read_bytes())
        for pair in ('176400-192000', '352800-48000', '88200-96000'):
            self.assertEqual((self.active/pair/'operator-binding.json').read_bytes(),
                             (DEFAULT/pair/'operator-binding.json').read_bytes())

    def test_changed_stage_snapshot_refused_before_any_commit(self):
        stage = self.active/'88200-96000/stage-snapshot.json'
        stage.write_bytes(stage.read_bytes() + b'\n')
        with self.assertRaisesRegex(UnboundOperator, 'operator changed'):
            recover(self.exporter, DEFAULT_AUDIT, True, self.active)

    def test_nonhistorical_noncurrent_receipt_refused(self):
        binding = self.active/'352800-96000/operator-binding.json'
        binding.write_bytes(binding.read_bytes() + b'\n')
        with self.assertRaisesRegex(UnboundOperator, 'neither archived original'):
            recover(self.exporter, DEFAULT_AUDIT, True, self.active)


if __name__ == '__main__':
    unittest.main()

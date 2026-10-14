#!/usr/bin/env python3
"""Fail-closed regression checks of P15 closeout evidence adjudication."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p15_closeout_review as review


class CloseoutReviewTests(unittest.TestCase):
    def test_complete_bounded_audit_stays_blocked(self):
        item = review.report()
        self.assertEqual(item['release_status'], 'BLOCKED')
        self.assertFalse(item['default_promotion_authorized'])
        self.assertFalse(item['p16_authorized'])
        self.assertEqual(len(item['mandatory_unclosed']), 4)
        self.assertEqual(item['evidence']['matrix']['equal_binary64_forced_pairs'], 0)
        self.assertEqual(item['evidence']['matrix']['forced_isa_jobs'], 270)
        self.assertEqual(item['evidence']['matrix']['missing_npz_vectors'], 324)
        self.assertEqual(item['evidence']['soaks']['complete_61_state_snapshot_sets'], 0)
        self.assertEqual(item['evidence']['soaks']['execution_receipts_present_for'], 0)
        self.assertEqual(item['evidence']['older_avx']['repetitions_per_case'], 15)

    def test_corrupt_cell_digest_blocks_adjudication(self):
        real = review.digest
        target = review.MATRIX / 'scalar-full/cells/dsd64.mastering.pcm44100.json'
        def corrupt(path):
            return '0'*64 if path == target else real(path)
        with patch.object(review, 'digest', side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, 'matrix cell digest mismatch'):
                review.matrix_review()

    def test_invalid_soak_guard_blocks_adjudication(self):
        real = review.load
        target = review.SOAKS / 'scalar/soak-2822400-result.json'
        def corrupt(path):
            obj = real(path)
            if path == target:
                obj['max_abs_state'][0] = float('inf')
            return obj
        with patch.object(review, 'load', side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, 'soak guard limit exceeded'):
                review.soaks_review()

    def test_require_qualified_exit_two_and_repeatable_json(self):
        with tempfile.TemporaryDirectory() as temp:
            result = Path(temp)/'review.json'
            cmd = [sys.executable,str(Path(review.__file__).resolve()),
                   '--output',str(result),'--require-qualified']
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode, 2)
            a = result.read_bytes()
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode, 2)
            self.assertEqual(a,result.read_bytes())
            item = json.loads(a)
            self.assertEqual(item['release_status'],'BLOCKED')
            self.assertNotIn(str(Path(temp).resolve()),a.decode())


if __name__ == '__main__':
    unittest.main()

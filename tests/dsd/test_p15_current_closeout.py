"""Scoped, source-only regressions for the dated P15 closeout inventory."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import p15_current_closeout as review
from p15_readjudication import write_new, EvidenceError


class P15CurrentCloseoutTests(unittest.TestCase):
    def test_current_source_counts_are_not_release_certificates(self):
        result = review.report()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertFalse(result['p16_authorized'])
        self.assertFalse(result['default_promotion_authorized'])
        # Was 2. The DSD256 bandwidth-matched gate has since been supplied
        # with its evidence and its status is derived from that evidence
        # rather than hardcoded, so it is no longer open. The composite SRC
        # gate remains, and BLOCKED above does not move with either.
        self.assertEqual(result['substantive_open_gates'],
                         ['P15-v1-and-v2-composite-SRC-acceptance'])
        dsd256 = next(g for g in result['gates']
                      if g['id'] == 'P15-DSD256-direct-2x-and-matched-comparator')
        self.assertEqual(dsd256['status'], 'PASS-SCOPED')
        self.assertEqual(dsd256['measured']['comparisons_meeting_2x_at_ci_lower_bound'], 8)
        self.assertEqual(dsd256['measured']['control_bandwidth_match'],
                         'CONTROL-BANDWIDTH-MATCH-VERIFIED')
        # The superseded R2 receipt is still reviewed and still fails.
        self.assertEqual(result['benchmark_r2_status'],
                         'OPEN-CONTROL-NOT-BANDWIDTH-MATCHED')
        self.assertEqual(result['p10_lineage']['byte_identical'], 30)
        self.assertEqual(result['p10_lineage']['later_executable_source_changes'], 4)
        self.assertEqual(result['p10_lineage']['reviewed_design_changes'], 1)
        self.assertEqual(result['src_numerical_disposition']['fractional_diagnostic_cases_disposed'], 36)
        self.assertEqual(result['src_numerical_disposition']['integer_ratio_additional_src_cells'], 36)
        self.assertGreaterEqual(result['transport']['inventory_entries'], 11124 + 5)
        # Written against the stripped 23 MB snapshot we sent, where 3508 bulk
        # payloads were absent: 945 arrays/*.npz + 1807 *.state + 756 graph-raw.
        # On the full branch those files are present, so the reviewer correctly
        # reports 0 missing and full_raw_replay_possible True. Accept either the
        # complete tree or the known stripped count; requiring 3508 would mean
        # asserting our evidence is incomplete.
        missing = sum(result['transport']['missing_expected_bulk_payloads'].values())
        self.assertIn(missing, (0, 3508))
        if missing == 0:
            self.assertTrue(result['transport']['full_raw_replay_possible'])
        self.assertEqual((result['matrices']['v1']['scalar_cells'],
                          result['matrices']['v2']['scalar_cells']), (54, 27))
        self.assertEqual((result['matrices']['v1']['forced_isa_jobs'],
                          result['matrices']['v2']['forced_isa_jobs']), (216, 108))
        self.assertEqual((result['matrices']['v1']['detailed_isa_jobs'],
                          result['matrices']['v2']['detailed_isa_jobs']), (96, 48))
        self.assertEqual((result['matrices']['v1']['src_active_cells'],
                          result['matrices']['v2']['src_active_cells']), (48, 24))
        self.assertFalse(result['matrices']['v1']['full_raw_replay_completed'])
        self.assertEqual(result['v2_native_fir_certificate']['three_new_banks'], 3)
        self.assertEqual(result['v2_native_fir_certificate']['three_profiles'], 3)

    def test_p10_document_exception_is_exact_current_revision_only(self):
        with patch.object(review, 'REVIEWED_DESIGN_SHA256', 'f'*64):
            with self.assertRaisesRegex(review.InvalidEvidence, 'unreviewed operative'):
                review.lineage()

    def test_false_current_source_pin_refused(self):
        original = review.digest
        def corrupted(path):
            if str(path) == 'src/dsd_decode.c':
                return '0'*64
            return original(path)
        with patch.object(review, 'digest', side_effect=corrupted):
            with self.assertRaisesRegex(review.InvalidEvidence, 'source hash drift'):
                review.matrix(review.V2, 'v2')

    def test_cell_incorrectly_qualified_refused(self):
        original = review.load
        def corrupted(path):
            row = original(path)
            if str(path).endswith('/cells/dsd64.mastering_v2.pcm44100.json'):
                row['qualified'] = True
            return row
        with patch.object(review, 'load', side_effect=corrupted):
            with self.assertRaisesRegex(review.InvalidEvidence, 'cell status/count mismatch'):
                review.matrix(review.V2, 'v2')

    def test_immutable_result_idempotent_and_conflict_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'review.json'
            first = {'status': 'BLOCKED', 'qualified': False}
            write_new(path, first)
            original_bytes = path.read_bytes()
            write_new(path, first)
            self.assertEqual(path.read_bytes(), original_bytes)
            with self.assertRaisesRegex(EvidenceError, 'existing result differs'):
                write_new(path, {'status': 'READY', 'qualified': True})
            self.assertEqual(path.read_bytes(), original_bytes)


if __name__ == '__main__':
    unittest.main()

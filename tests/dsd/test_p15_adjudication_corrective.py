"""Adversarial, immutable-evidence tests for the 2026-10-16 re-adjudication."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import verify_dsd256_control_match as verifier

import p15_readjudication as original
from p15_intel_receipt_review import review as intel_review, InvalidIntelReceipt, BASE


class CorrectiveTests(unittest.TestCase):
    def test_full_passband_is_mandatory_and_historical_result_is_preserved(self):
        before = (original.PER_PROFILE / 'dsd256-control-match.json').read_bytes()
        verdict = original.inspect_control_match()
        self.assertEqual(verdict['disposition'], 'CONTROL-EDGE-MISMATCH')
        self.assertFalse(verdict['all_full_passbands_matched'])
        self.assertFalse(verdict['cells']['decode.mastering.v2.dsd256@352800']
                         ['full_passband_match'])
        self.assertEqual(before,
                         (original.PER_PROFILE / 'dsd256-control-match.json').read_bytes())

    def test_reject_a_widened_crop_and_false_edge_verdict(self):
        baseline = original.read_json(original.PER_PROFILE / 'dsd256-control-match.json')
        bad = copy.deepcopy(baseline)
        bad['rows']['decode.mastering.v2.dsd256']['rates']['352800'][
            'transition_excluded_fraction'] = .25
        with self.assertRaisesRegex(original.EvidenceError, 'exclusion'):
            original.inspect_control_match(bad)
        bad = copy.deepcopy(baseline)
        bad['rows']['decode.mastering.v2.dsd256']['rates']['352800'][
            'full_passband_max_abs_difference_db'] = -1
        with self.assertRaisesRegex(original.EvidenceError, 'full-passband'):
            original.inspect_control_match(bad)
        bad = copy.deepcopy(baseline)
        bad['rows']['decode.mastering.v2.dsd256']['rates']['352800']['matched'] = False
        with self.assertRaisesRegex(original.EvidenceError, 'cropped verdict'):
            original.inspect_control_match(bad)

    def test_new_spectral_comparator_cannot_hide_upper_passband_mismatch(self):
        # Ground truth at 65 kHz disagrees; a 95%-crop would incorrectly PASS.
        freq = np.linspace(0, 88200, 4097)
        decoder = np.full(len(freq), -25.0)
        control = decoder + np.where(freq >= 63500, 6.0, 0.0)
        with patch.object(verifier, 'spectrum', side_effect=[
            (352800, freq, decoder), (352800, freq, control)]):
            got = verifier.compare(Path('decoder.wav'), Path('control.wav'), 66000)
        self.assertEqual(got['transition_excluded_fraction'], 0.0)
        self.assertFalse(got['matched'])
        self.assertAlmostEqual(got['max_abs_difference_db'], 6.0)

    def test_full_benchmark_retains_timing_but_is_not_matched(self):
        x = original.inspect_per_profile_benchmark()
        self.assertEqual(x['comparisons_meeting_2x_at_ci_lower_bound'], 8)
        self.assertEqual(x['timed_direct_2x_observation'], 'PASS-SCOPED')
        self.assertEqual(x['timed_matched_control_observation'], 'MEASURED-NOT-MATCHED')
        self.assertEqual(x['disposition'], 'DIRECT-2X-MEASURED-CONTROL-EDGE-MISMATCH')

    def test_intel_raw_recomputed_without_preference(self):
        x = intel_review()
        self.assertEqual(x['status'], 'MEASURED-SCOPED')
        self.assertEqual(x['historical_policy_status'], 'UNRUN-SCOPE-EXEMPT')
        self.assertAlmostEqual(x['kernel_speedups']['fir-block'], 1.914901, places=6)
        self.assertTrue(x['conversion_speedup_range'][1] < 1.02)
        self.assertFalse(x['intel_preference_authorized'])

    def test_intel_source_identity_mutation_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = Path(folder)
            with self.assertRaisesRegex(InvalidIntelReceipt, 'measured Intel source'):
                intel_review(root=fake, base=BASE)


if __name__ == '__main__':
    unittest.main()

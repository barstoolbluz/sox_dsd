#!/usr/bin/env python3
"""Adversarial scalar readjudication tests; no synthetic receipt is published."""
from copy import deepcopy
import math
from pathlib import Path
import unittest

import readjudicate_displayed_bounds as r


ROOT = Path(__file__).resolve().parents[5]


class NormativeReadjudication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles = r.exact.load(ROOT/'tests/dsd/reference/p06_coefficients.json')['profiles']
        cls.profiles.update(r.exact.load(ROOT/'tests/dsd/reference/p15_r3_coefficients.json')['profiles'])
        cls.local = r.exact.load(ROOT/r.THIRD/'master256-176400-384000-pass-0-1000.json')
        cls.binding, _ = r.exact.dependencies(ROOT)

    def test_real_third_pass_local_and_all_fields(self):
        result, margins = r.assess(self.local, self.profiles)
        self.assertEqual(result['normative_envelope_status'], 'EXACT_NORMATIVE_ENVELOPE_VERIFIED')
        self.assertEqual(result['job']['cell_id'], r.exact.CELL)
        self.assertEqual(len(margins), 3)
        self.assertTrue(all(x > 0 for x in margins.values()))

    def test_old_pass_status_cannot_admit_upper_threshold_sliver(self):
        doc = deepcopy(self.local)
        doc['max_total_transfer_upper'] = math.nextafter(float(r.exact.GAIN_PLUS[1]), math.inf)
        result, margins = r.assess(doc, self.profiles)
        self.assertEqual(result['normative_envelope_status'], 'DISPLAY_INEQUALITY_UNPROVED')
        self.assertIsNone(margins)
        self.assertEqual(doc['status'], 'PASS-LOCAL-BAND')

    def test_old_pass_status_cannot_admit_lower_threshold_sliver(self):
        doc = deepcopy(self.local)
        doc['min_wanted_transfer_lower'] = math.nextafter(float(r.exact.GAIN_MINUS[0]), -math.inf)
        result, _ = r.assess(doc, self.profiles)
        self.assertEqual(result['normative_envelope_status'], 'DISPLAY_INEQUALITY_UNPROVED')

    def test_missing_display_field_is_not_readjudicable(self):
        doc = deepcopy(self.local)
        del doc['max_total_transfer_upper']
        result, _ = r.assess(doc, self.profiles)
        self.assertEqual(result['normative_envelope_status'], 'INSUFFICIENT_FIELDS')

    def test_normative_policy_substitution_is_invalid(self):
        doc = deepcopy(self.local)
        doc['limits']['passband_db'] = '0.001'
        result, _ = r.assess(doc, self.profiles)
        self.assertEqual(result['normative_envelope_status'], 'INVALID')

    def test_source_binding_is_separate_from_scalar_result(self):
        doc = deepcopy(self.local)
        doc['source_sha256']['src/rate.c'] = 'f'*64
        result, _ = r.assess(doc, self.profiles)
        self.assertEqual(result['normative_envelope_status'], 'EXACT_NORMATIVE_ENVELOPE_VERIFIED')
        _, source = r.provenance(doc, self.binding,
            lambda _a, _b: (doc['stage_snapshot_sha256'], doc['verified_operator_binding_sha256']))
        self.assertEqual(source['source_binding_status'], 'SOURCE_BINDING_MISMATCH')


if __name__ == '__main__':
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Independent topology and evidence-accounting checks for the high-rate census.

The slow reference is the pre-existing literal inverse-path enumeration. These
tests neither evaluate spectral magnitudes nor qualify release behavior.
"""
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest

import p15_high_rate_census as census
from p15_src_capture_matrix import DEFAULT, verify_pair
from p15_src_complete_aliases import all_active_cells
from p15_src_stagewise_continuum import BranchBoundary, complete_paths


class LatticeArithmetic(unittest.TestCase):
    def test_exact_rational_endpoints_and_one_sided_interiors(self):
        self.assertEqual(census.lattice_points(Fraction(1, 3), Fraction(2, 3),
                                              Fraction(1, 3), Fraction(7, 3)),
                         (Fraction(1), Fraction(5, 3)))
        self.assertEqual(census.lattice_points(Fraction(1, 3), Fraction(2, 3),
                                              Fraction(1, 3), Fraction(7, 3),
                                              endpoints=True),
                         (Fraction(1, 3), Fraction(1), Fraction(5, 3), Fraction(7, 3)))

    def test_native_stop_membership_is_distinct_from_routing(self):
        crossings = sorted({q for sign in (-1, 1)
                            for q in census.lattice_points(sign * 80000, 1200, 0, 1000)})
        self.assertEqual(crossings, [Fraction(400), Fraction(800)])
        self.assertEqual(census.lattice_points(0, 600, 0, 1000), (Fraction(600),))

    def test_zero_width_has_no_interior_event(self):
        self.assertEqual(census.lattice_points(0, 600, 0, 0), ())
        self.assertEqual(census.lattice_points(0, 600, 0, 0, endpoints=True), (Fraction(0),))

    def test_bad_period_is_rejected(self):
        for period in (0, -1):
            with self.assertRaises(ValueError):
                census.lattice_points(0, period, 0, 1)


class LiteralPathReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cells = {c['id']: c for c in all_active_cells()}
        cls.operators = {}

    def check_intervals(self, cell_id, intervals, expected_paths, expected_families):
        cell = self.cells[cell_id]
        key = (cell['intermediate_hz'], cell['output_hz'])
        if key not in self.operators:
            self.operators[key] = verify_pair(DEFAULT / f'{key[0]}-{key[1]}', *key)[1]
        op = self.operators[key]
        topology = census.rate_topology(cell, op)
        self.assertEqual(topology['complete_path_count'], expected_paths)
        self.assertEqual(topology['primitive_source_family_count'], expected_families)
        predicted = [Fraction(q) for q in topology['exact_routing_transition_points_hz']]
        for lo, hi in intervals:
            with self.subTest(cell=cell_id, lo=lo, hi=hi):
                pending = [(Fraction(lo), Fraction(hi))]
                boundaries = set()
                leaves = 0
                while pending:
                    left, right = pending.pop()
                    actual = complete_paths(cell['profile'], op, left, right,
                                            max_paths=20000, require_direct=False)
                    if isinstance(actual, BranchBoundary):
                        self.assertLess(left, actual.at)
                        self.assertLess(actual.at, right)
                        boundaries.add(actual.at)
                        pending.extend(((left, actual.at), (actual.at, right)))
                    else:
                        leaves += 1
                        counts = Counter(p.upstream_shift for p in actual)
                        self.assertEqual(len(actual), expected_paths)
                        self.assertEqual(len(counts), expected_families)
                        self.assertEqual(set(counts.values()), {expected_paths // expected_families})
                        self.assertLessEqual(leaves, 16)
                self.assertEqual(boundaries, {q for q in predicted if lo < q < hi})

    def test_dsd256_mastering_384k_full_population(self):
        self.check_intervals('dsd256.mastering.pcm384000',
                             [(0, 1000), (39000, 40000), (191000, 192000)], 9408, 9408)

    def test_dsd256_wideband_384k_large_passband(self):
        self.check_intervals('dsd256.wideband.pcm384000',
                             [(0, 1000), (140000, 141120), (191000, 192000)], 4704, 4704)

    def test_dsd256_wideband_192k_collision_multiplicity(self):
        self.check_intervals('dsd256.wideband.pcm192000',
                             [(0, 1000), (91000, 91200), (95000, 96000)], 9408, 4704)

    def test_dsd64_384k_three_src_stages(self):
        self.check_intervals('dsd64.mastering.pcm384000',
                             [(0, 1000), (19000, 20000), (191000, 192000)], 4704, 4704)


class EvidenceAccounting(unittest.TestCase):
    def test_idempotent_publication_and_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'receipt.json'
            census.publish(target, b'first\n')
            census.publish(target, b'first\n')
            with self.assertRaises(ValueError):
                census.publish(target, b'changed\n')
            self.assertEqual(target.read_bytes(), b'first\n')

    def test_linked_output_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'original'
            target.write_bytes(b'bytes')
            link = Path(directory) / 'link'
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                census.publish(link, b'bytes')

    def test_historical_timeout_is_never_inferred_failure(self):
        result = census.state_classification(
            dict(status='OPEN', reason='interval_wall_clock_budget_exhausted'), {})
        self.assertEqual(result, ['historical_budget_exhaustion', 'current_run_unmeasured'])

    def test_current_pass_does_not_relabel_original_open(self):
        original = dict(status='OPEN', reason='operator_path_precondition:old-count')
        result = census.state_classification(original,
            {'candidate': [dict(status='PASS-LOCAL-BAND')]})
        self.assertEqual(original['status'], 'OPEN')
        self.assertEqual(result, ['historical_operator_precondition', 'candidate:observed_local_pass'])

    def test_overlay_cannot_change_band_or_source_identity(self):
        job = dict(cell_id='synthetic', profile='master256', intermediate_hz=176400,
                   output_hz=384000, mode='pass', lo='0', hi='1000',
                   effective_p='40000', source_s=80000)
        binding = dict(design='design', source={'src/file': 'source'})
        certificate = dict(status='PASS-LOCAL-BAND', qualified_release=False,
            profile='master256', certified_hz=['0', '1000'], band_kind='pass',
            input_hz=176400, output_hz=384000, governing_passband_hz=40000)
        doc = dict(job=job, binding=binding, certificate=certificate, qualified_release=False)
        by_hash = {census.digest(job): job}
        self.assertEqual(census.validate_overlay(doc, by_hash, binding), census.digest(job))
        for mutate in ('source', 'band', 'scope', 'release'):
            damaged = json.loads(json.dumps(doc))
            if mutate == 'source':
                damaged['binding']['source']['src/file'] = 'other'
            elif mutate == 'band':
                damaged['certificate']['status'] = 'PASS-LOCAL-STOP-SOURCE'
            elif mutate == 'scope':
                damaged['certificate']['certified_hz'] = ['0', '999']
            else:
                damaged['qualified_release'] = True
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                census.validate_overlay(damaged, by_hash, binding)


if __name__ == '__main__':
    unittest.main()

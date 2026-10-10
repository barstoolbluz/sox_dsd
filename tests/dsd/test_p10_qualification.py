#!/usr/bin/env python3
"""Fail-closed qualification accounting tests, using the retained P10 evidence.

Mutations operate on temporary copies only. They never amend a failed scientific
record, the training corpus, the frozen guards, or a promotion decision.
"""
from __future__ import annotations
import contextlib
import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import qualify_p10 as q


class QualificationAccounting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads((q.ROOT/'tests/dsd/results/P10/numeric/qualification.json').read_text())
        if len(cls.original['rows']) != len(q.jobs(q.configurations())):
            raise RuntimeError('complete retained numeric evidence is required for accounting tests')

    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='p10-accounting-')
        self.addCleanup(self.work.cleanup)
        self.args = SimpleNamespace(results=Path(self.work.name)/'numeric',
            unit=q.ROOT/'test/dsd_test_p10', freeze_training_bounds=False)
        self.args.results.mkdir()
        self.report = copy.deepcopy(self.original)
        self.row = next(r for r in self.report['rows'] if r['control']=='mastering'
            and r['source']['name']=='tone-997--6')

    def summarize(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code = q.summarize(self.args, self.report)
        self.assertFalse(self.report['qualified'])
        return code

    def test_complete_numeric_is_not_qualification(self):
        self.assertEqual(self.summarize(), 2)
        for key in ('complete_numeric_coverage','nominal_pipeline',
                'heldout_state_bounds','dsd64_windows28','lowlevel_spurs',
                'residual_comparison','expected_overload'):
            self.assertEqual(self.report['gates'][key]['status'], 'PASS', key)
        self.assertEqual(self.report['status'], 'INCOMPLETE')

    def test_missing_case_fails(self):
        self.report['rows'].pop()
        self.assertEqual(self.summarize(), 1)
        self.assertEqual(self.report['gates']['complete_numeric_coverage']['status'], 'FAIL')

    def test_duplicate_case_fails(self):
        self.report['rows'].append(copy.deepcopy(self.row))
        self.assertEqual(self.summarize(), 1)

    def test_missing_legacy_measurement_fails(self):
        old = next(r for r in self.report['rows'] if r['control']=='legacy' and r['source']==self.row['source'])
        old.pop('analysis')
        self.assertEqual(self.summarize(), 1)
        self.assertEqual(self.report['gates']['residual_comparison']['status'], 'FAIL')

    def test_finite_state_above_guard_fails(self):
        self.row['render']['max_abs_state'][7] = 1e300
        self.assertEqual(self.summarize(), 1)
        self.assertEqual(self.report['gates']['heldout_state_bounds']['status'], 'FAIL')

    def test_nonfinite_state_fails(self):
        self.row['render']['max_abs_state'][0] = float('nan')
        # atomic JSON correctly refuses NaN as well. The evidence must not be
        # silently written as a nominal success by either layer.
        with self.assertRaises(ValueError):
            self.summarize()

    def test_success_with_short_output_fails(self):
        self.row['render']['committed_native_frames'] -= 1
        self.assertEqual(self.summarize(), 1)

    def test_success_with_failure_marker_fails(self):
        self.row['render']['failure'] = 4
        self.assertEqual(self.summarize(), 1)

    def test_window_excursion_fails(self):
        self.row['render']['excursions28'] = 1
        self.assertEqual(self.summarize(), 1)
        self.assertEqual(self.report['gates']['dsd64_windows28']['status'], 'FAIL')

    def test_low_level_spur_fails(self):
        row = next(r for r in self.report['rows'] if r['control']=='mastering'
            and r['source']['name']=='tone-997--90')
        row['spectral_peak']['line_dbfs'] = -90.
        self.assertEqual(self.summarize(), 1)
        self.assertEqual(self.report['gates']['lowlevel_spurs']['status'], 'FAIL')

    def test_failed_soak_blocks(self):
        p = self.args.results.parent/'soak/soak.json'
        q.atomic(p, {'status':'FAIL'})
        self.assertEqual(self.summarize(), 1)
        self.assertEqual(self.report['gates']['release_30min_per_rate']['status'], 'FAIL')

    def test_resume_rejects_changed_implementation_without_render(self):
        self.report['implementation'] = {'different':'source'}
        q.atomic(self.args.results/'qualification.json', self.report)
        with patch.object(q, 'render', side_effect=AssertionError('must not execute')):
            with self.assertRaisesRegex(RuntimeError, 'implementation differs'):
                q.evaluate(self.args)

    def test_resume_rejects_duplicates_without_render(self):
        self.report['implementation'] = q.implementation_identity()
        self.report['rows'].append(copy.deepcopy(self.row))
        q.atomic(self.args.results/'qualification.json', self.report)
        with patch.object(q, 'render', side_effect=AssertionError('must not execute')):
            with self.assertRaisesRegex(RuntimeError, 'duplicate cached'):
                q.evaluate(self.args)

    def test_training_cannot_be_regenerated_in_new_directory(self):
        before = q.digest(q.ROOT/'tests/dsd/reference/p10_guards.json')
        with patch.object(q, 'render', side_effect=AssertionError('must not execute')):
            with self.assertRaisesRegex(RuntimeError, 'refusing to overwrite'):
                q.train(self.args)
        self.assertEqual(before, q.digest(q.ROOT/'tests/dsd/reference/p10_guards.json'))


if __name__ == '__main__':
    unittest.main(verbosity=2)

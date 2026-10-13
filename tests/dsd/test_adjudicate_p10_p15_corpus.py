#!/usr/bin/env python3
"""Independent mutations for the recorded P10/P15 corpus adjudicator.

All tests operate on six manifest copies in a temporary directory. The
historical P10 and P15 measurements are never modified by this suite.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

import adjudicate_p10_p15_corpus as audit


class CorpusAdjudicationMutations(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.p10, self.p15 = root / 'P10', root / 'P15'
        for src, dst in ((audit.DEFAULT_OLD, self.p10),
                         (audit.DEFAULT_NEW, self.p15)):
            dst.mkdir()
            for filename, _ in audit.ARMS.values():
                shutil.copyfile(src / filename, dst / filename)

    def comparison(self) -> dict:
        return audit.run(self.p10, self.p15)

    def modify(self, arm: str, predicate, modifier, *, baseline=False) -> None:
        directory = self.p10 if baseline else self.p15
        path = directory / audit.ARMS[arm][0]
        rows = json.loads(path.read_text(encoding='utf-8'))
        matches = [row for row in rows if predicate(row)]
        self.assertTrue(matches)
        modifier(matches[0])
        path.write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')

    def assert_rejected(self) -> None:
        result = self.comparison()
        self.assertEqual(result['status'], 'FAIL')
        self.assertGreater(result['summary']['errors'], 0)

    def test_real_corpus_manifest_scope(self) -> None:
        result = self.comparison()
        self.assertEqual(result['status'], 'PASS-BOUNDED-DRIFT')
        self.assertEqual(result['summary'], {
            'records_compared': 40,
            'source_rate_identities': 18,
            'changed_numeric_fields': 6,
            'arm_source_pairs_with_changed_extrema': 4,
            'sources_with_changed_extrema': 3,
            'ladder_trial_scope_differences': 4,
            'errors': 0,
        })
        self.assertEqual(result, self.comparison())

    def test_mutate_source_digest_fails(self) -> None:
        self.modify('unity', lambda row: row['admitted'],
                    lambda row: row.__setitem__('excerpt_sha256', '0' * 64))
        self.assert_rejected()

    def test_mutate_admission_fails(self) -> None:
        self.modify('unity', lambda row: row['admitted'],
                    lambda row: row.__setitem__('admitted', False))
        self.assert_rejected()

    def test_mutate_output_size_fails(self) -> None:
        self.modify('unity', lambda row: row['admitted'],
                    lambda row: row.__setitem__('output_bytes', row['output_bytes'] + 1))
        self.assert_rejected()

    def test_mutate_frame_count_fails(self) -> None:
        self.modify('unity', lambda row: row['admitted'],
                    lambda row: row.__setitem__('output_frames', row['output_frames'] - 1))
        self.assert_rejected()

    def test_mutate_window_population_violating_four_to_24_fails(self) -> None:
        def bad(row):
            row['per_channel'][0]['min_ones'] = 3
            row['min_ones28'] = 3
        self.modify('unity', lambda row: row['admitted'], bad)
        self.assert_rejected()

    def test_mutate_channel_ones_fraction_fails(self) -> None:
        self.modify('unity', lambda row: row['admitted'],
                    lambda row: row['per_channel'][0].__setitem__('ones_fraction', 0.1))
        self.assert_rejected()

    def test_mutate_large_but_in_bounds_extrema_fails(self) -> None:
        def bad(row):
            row['per_channel'][0]['min_ones'] = 10
            row['min_ones28'] = min(c['min_ones'] for c in row['per_channel'])
        self.modify('attenuated',
                    lambda row: row['source'] == '01 - Cantata BWV 110_ 1. Chorus.dsf',
                    bad)
        self.assert_rejected()

    def test_mutate_ladder_admitting_gain_fails(self) -> None:
        self.modify('ladder', lambda row: row['source'] == '01 - Bone Machine.dsf',
                    lambda row: row.__setitem__('admitting_gain_db', -0.9))
        self.assert_rejected()

    def test_mutate_ladder_trial_verdict_fails(self) -> None:
        def bad(row):
            row['ladder_attempts'][-1]['admitted'] = not row['ladder_attempts'][-1]['admitted']
        self.modify('ladder', lambda row: row['source'] == '01 - Bone Machine.dsf', bad)
        self.assert_rejected()

    def test_mutate_level_metric_fails(self) -> None:
        self.modify('attenuated', lambda row: row['admitted'],
                    lambda row: row.__setitem__('peak_delta_db', 300))
        self.assert_rejected()

    def test_missing_manifest_raises(self) -> None:
        (self.p15 / 'corpus-unity.json').unlink()
        with self.assertRaises(OSError):
            self.comparison()


if __name__ == '__main__':
    unittest.main(verbosity=2)

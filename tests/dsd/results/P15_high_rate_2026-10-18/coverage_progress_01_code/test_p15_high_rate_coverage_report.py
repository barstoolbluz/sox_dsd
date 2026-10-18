#!/usr/bin/env python3
"""Cheap adversarial checks of coverage accounting and matched measurements."""
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

import p15_high_rate_coverage_report as report
from p15_full_band_campaign import digest


def jobs():
    base = dict(cell_id='fixture', profile='master256', output_hz=8,
                intermediate_hz=16, effective_p='3', source_s=4)
    return [dict(base, mode='pass', lo='0', hi='1'),
            dict(base, mode='pass', lo='1', hi='3'),
            dict(base, mode='stop', lo='0', hi='4')]


def timing(status='PASS-LOCAL-BAND', elapsed=2):
    identity = dict(job={'job': 1}, binding={'source': 'fixed'},
        stage_snapshot_sha256='snapshot', verified_operator_binding_sha256='operator',
        resources={'seconds': 60, 'cpu': 1}, harness_sha256='harness', profiling_enabled=False)
    environment = dict(python='python', executable='python', platform='platform',
                       mpmath='1.3', numpy='2.3', affinity=[1], openblas_num_threads='1')
    doc = dict(job={'job': 1}, experiment_identity=identity,
               certificate={'status': status}, measurement=dict(elapsed_s=elapsed,
               cpu_s=elapsed, peak_rss_kib=100, environment=environment))
    return dict(doc=doc, reference={'path': 'fixture', 'sha256': 'sha'})


class CanonicalCoverage(unittest.TestCase):
    def test_all_intervals_and_exact_endpoints_are_required(self):
        work = jobs()
        witnesses = {digest(j): {'sha256': str(i)} for i, j in enumerate(work)}
        cover = report.complete_cover(work, witnesses)
        self.assertEqual(cover['pass']['canonical_intervals'], 2)
        self.assertEqual(cover['pass']['upper_hz'], '3')
        self.assertEqual(cover['stop']['upper_hz'], '4')
        witnesses.pop(digest(work[1]))
        self.assertIsNone(report.complete_cover(work, witnesses))

    def test_gap_overlap_and_nyquist_shortfall_are_rejected(self):
        for defect in ('gap', 'overlap', 'short_stop'):
            work = jobs()
            if defect == 'gap':
                work[1]['lo'] = '2'
            elif defect == 'overlap':
                work[1]['lo'] = '1/2'
            else:
                work[2]['hi'] = '3'
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                report.complete_cover(work, {digest(j): {} for j in work})

    def test_unmeasured_and_open_remain_distinct(self):
        self.assertEqual(report.observed_state([]), 'UNMEASURED')
        self.assertEqual(report.observed_state([timing('OPEN')]), 'OPEN')
        self.assertEqual(report.observed_state([timing('OPEN'), timing()]), 'PASS')


class PerformanceAndProofIdentity(unittest.TestCase):
    def test_only_pass_pairs_have_a_speedup(self):
        result = report.matched_pair(timing(elapsed=4), timing(elapsed=2))
        self.assertEqual(result['speedup_if_both_pass'], 2)
        result = report.matched_pair(timing('OPEN', elapsed=60), timing(elapsed=2))
        self.assertIsNone(result['speedup_if_both_pass'])
        self.assertIsNone(result['baseline']['counters']['alias_population_operations'])

    def test_source_budget_and_execution_environment_must_match(self):
        for target, key in (('experiment_identity', 'binding'),
                            ('experiment_identity', 'resources'),
                            ('experiment_identity', 'harness_sha256'),
                            ('environment', 'affinity'), ('environment', 'numpy')):
            baseline, candidate = timing(), timing()
            selected = (candidate['doc']['measurement']['environment'] if target == 'environment'
                        else candidate['doc'][target])
            selected[key] = 'different'
            with self.subTest(target=target, key=key), self.assertRaises(ValueError):
                report.matched_pair(baseline, candidate)

    def test_full_frozen_snapshot_is_checked_against_bytes(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name)
            module = path / 'p15_fixture.py'
            module.write_bytes(b'VALUE=1\n')
            code = {'p15_fixture.py': sha256(module.read_bytes()).hexdigest()}
            (path / 'IDENTITY.json').write_text(json.dumps({'prover_code_sha256': code}))
            self.assertEqual(report.proof_snapshot(path)['prover_code_sha256'], code)
            module.write_bytes(b'VALUE=2\n')
            with self.assertRaises(ValueError):
                report.proof_snapshot(path)


if __name__ == '__main__':
    unittest.main()

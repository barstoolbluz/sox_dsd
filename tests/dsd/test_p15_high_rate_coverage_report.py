#!/usr/bin/env python3
"""Cheap adversarial checks of coverage accounting and matched measurements."""
from hashlib import sha256
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
        resources={'seconds': 60, 'cpu': 1, 'max_nodes': 128, 'max_paths': 20000},
        prover_code_sha256={'p15_fixture.py': 'code'},
        harness_sha256='harness', profiling_enabled=False)
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
    def test_larger_budget_does_not_credit_a_changed_proof(self):
        short, long = timing('OPEN', 60), timing(elapsed=90)
        long['doc']['experiment_identity']['resources']['seconds'] = 180
        long['doc']['experiment_identity']['resources']['cpu'] = 7
        self.assertEqual(len(report.larger_budget_evidence([short, long])), 1)
        for key, changed in [('prover_code_sha256', {'p15_fixture.py': 'new-code'}),
                             ('profiling_enabled', True)]:
            old = long['doc']['experiment_identity'][key]
            long['doc']['experiment_identity'][key] = changed
            self.assertEqual(report.larger_budget_evidence([short, long]), [])
            long['doc']['experiment_identity'][key] = old
        long['doc']['experiment_identity']['resources']['max_nodes'] = 256
        self.assertEqual(report.larger_budget_evidence([short, long]), [])

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


class ExactBoundaryAudit(unittest.TestCase):
    def test_point_coverage_does_not_imply_either_neighborhood(self):
        q = Fraction(1, 3)
        event = report.event_coverage([q], [(q, q)], Fraction(1))['events'][0]
        self.assertTrue(event['point'])
        self.assertFalse(event['left_neighborhood'])
        self.assertFalse(event['right_neighborhood'])
        self.assertFalse(event['all_applicable_sides'])
        full = report.event_coverage([q], [(Fraction(0), q), (q, Fraction(1))], 1)
        self.assertEqual(full['with_both_sides'], 1)
        left = report.event_coverage([q], [(Fraction(0), q)], 1)
        self.assertEqual(left['with_all_applicable_sides'], 0)

    def test_dc_and_nyquist_only_require_the_in_domain_side(self):
        result = report.event_coverage([0, 1], [(Fraction(0), Fraction(1))], 1)
        self.assertEqual(result['with_all_applicable_sides'], 2)
        self.assertEqual(result['with_both_sides'], 0)
        with self.assertRaises(ValueError):
            report.event_coverage([2], [(Fraction(0), Fraction(2))], 1)

    def test_native_nyquist_is_an_alias_event_not_an_output_endpoint(self):
        meta = dict(id='fixture', native_hz=24, output_hz=18,
            effective_P_hz='6', declared_S_hz=8,
            topology=dict(primitive_frequency_spacing_hz='6', complete_path_count=4,
                primitive_source_family_count=4,
                exact_stage_transition_lattices=[dict(residue_hz='0', period_hz='3')]))
        work = [dict(cell_id='fixture', mode='pass', lo='0', hi='6'),
                dict(cell_id='fixture', mode='stop', lo='0', hi='6'),
                dict(cell_id='fixture', mode='stop', lo='6', hi='9')]
        rows = [dict(job=job, work_sha256=digest(job)) for job in work]
        selected = {row['work_sha256'] for row in rows}
        audit = report.boundary_scope(rows, {'fixture': meta}, selected, 'plan')
        cell = audit['cells'][0]
        self.assertEqual(cell['native_nyquist_hz'], '12')
        events = cell['bands']['stop']['source_nyquist_alias_relabeling']['events']
        self.assertEqual([event['hz'] for event in events], ['0', '6'])
        self.assertTrue(events[1]['left_neighborhood'] and events[1]['right_neighborhood'])
        self.assertTrue(cell['bands']['stop']['upper_normative_edge_and_left_limit'])
        self.assertTrue(cell['bands']['pass']['dc_and_arbitrarily_near_zero'])
        selected.remove(rows[-1]['work_sha256'])
        partial = report.boundary_scope(rows, {'fixture': meta}, selected, 'plan')['cells'][0]
        self.assertFalse(partial['bands']['stop']['upper_normative_edge_and_left_limit'])
        self.assertEqual(partial['bands']['stop']['source_nyquist_alias_relabeling']['with_both_sides'], 0)
        with self.assertRaises(ValueError):
            report.boundary_scope(rows, {'fixture': meta}, selected | {'missing'}, 'plan')


class StrictNormativeReadjudication(unittest.TestCase):
    def fixture(self, root):
        (root / 'receipt.json').write_bytes(b'{"bound":"exact"}\n')
        receipt_hash = sha256((root / 'receipt.json').read_bytes()).hexdigest()
        (root / 'read.py').write_bytes(b'# independent verifier fixture\n')
        binding = {'source': {'pinned.c': 'source'}, 'design': 'design'}
        row = dict(receipt_path='receipt.json', receipt_sha256=receipt_hash,
            canonical_work_sha256='work', normative_envelope_status='EXACT_NORMATIVE_ENVELOPE_VERIFIED',
            source_binding_status='CURRENT_SOURCE_AND_DESIGN_PINS_MATCH',
            recorded_source_binding_sha256=digest(binding))
        doc = dict(schema='P15/exact-normative-envelope-readjudication/1', qualified_release=False,
            numerical_proof_replayed=False, receipts=[row],
            recorded_source_bindings={digest(binding): binding},
            implementation_sha256={'read.py': sha256((root / 'read.py').read_bytes()).hexdigest()})
        return doc, {('receipt.json', receipt_hash): 'work'}, binding

    def publish_fixture(self, root, doc):
        path = root / 'verification.json'
        path.write_text(json.dumps(doc))
        (root / 'SHA256SUMS').write_text(''.join(
            f'{sha256((root / name).read_bytes()).hexdigest()}  {name}\n'
            for name in ('read.py', 'verification.json')))
        return path

    def test_exact_receipt_hash_and_work_are_required(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            doc, required, binding = self.fixture(root)
            path = self.publish_fixture(root, doc)
            with patch.object(report, 'ROOT', root):
                result = report.require_strict_readjudication(path, required, binding)
                self.assertEqual(result['contributing_pass_receipts'], 1)
                self.assertFalse(result['numerical_proof_replayed'])
                original = json.loads(json.dumps(doc))
                for key, value in [('normative_envelope_status', 'DISPLAY_INEQUALITY_UNPROVED'),
                                   ('canonical_work_sha256', 'other'),
                                   ('receipt_sha256', 'other'),
                                   ('source_binding_status', 'MISSING_SOURCE_BINDING'),
                                   ('recorded_source_binding_sha256', 'other')]:
                    changed = json.loads(json.dumps(original))
                    changed['receipts'][0][key] = value
                    with self.subTest(key=key), self.assertRaises(ValueError):
                        report.require_strict_readjudication(self.publish_fixture(root, changed), required, binding)
                self.publish_fixture(root, original)
                (root / 'receipt.json').write_bytes(b'changed receipt')
                with self.assertRaises(ValueError):
                    report.require_strict_readjudication(path, required, binding)

    def test_missing_readjudication_and_changed_verifier_are_rejected(self):
        with self.assertRaises(ValueError):
            report.require_strict_readjudication(None, {}, {})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            doc, required, binding = self.fixture(root)
            path = self.publish_fixture(root, doc)
            (root / 'read.py').write_bytes(b'changed verifier')
            with patch.object(report, 'ROOT', root), self.assertRaises(ValueError):
                report.require_strict_readjudication(path, required, binding)


if __name__ == '__main__':
    unittest.main()

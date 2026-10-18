#!/usr/bin/env python3
"""Aggregation adversaries only; synthetic receipts are temporary, not proofs."""
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
spec = importlib.util.spec_from_file_location('independent_cell_verifier', HERE / 'verify_complete_cell.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class CompleteCellAggregation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binding, cls.files = v.dependencies(ROOT)
        cls.selected = v.reconstruct_plan(ROOT)
        first_index, first_job = cls.selected[0]
        path = ROOT / 'tests/dsd/results/P15_high_rate_2026-10-18/campaign_candidate_60s' / (v.digest(first_job) + '.json')
        cls.real = v.load(path)
        v.validate_receipt(cls.real, first_index, first_job, cls.binding)

    def synthetic(self, index, job):
        doc = deepcopy(self.real)
        doc['canonical_work_index'] = index
        doc['job'] = deepcopy(job)
        doc['experiment_identity']['job'] = deepcopy(job)
        cert = doc['certificate']
        cert['band_kind'] = job['mode']
        cert['certified_hz'] = [job['lo'], job['hi']]
        if job['mode'] == 'stop':
            cert['status'] = 'PASS-LOCAL-STOP-SOURCE'
            cert['max_native_stop_source_transfer_upper'] = 9e-9
            cert['max_coherent_alias_upper'] = None
            cert['min_wanted_transfer_lower'] = None
            cert['max_total_transfer_upper'] = None
        return doc

    def check_rejected(self, edit):
        doc = deepcopy(self.real)
        edit(doc)
        with self.assertRaises(v.Invalid):
            v.validate_receipt(doc, *self.selected[0], self.binding)

    def test_plan_and_closed_endpoint_populations(self):
        self.assertEqual(len(self.selected), 232)
        self.assertEqual(v.digest([job for _, job in self.selected]), v.CELL_PLAN_SHA)
        self.assertEqual(self.selected[0][1]['lo'], '0')
        self.assertEqual(self.selected[39][1]['hi'], '40000')
        self.assertEqual(self.selected[40][1]['lo'], '0')
        self.assertEqual(self.selected[-1][1]['hi'], '192000')

    def test_real_receipt_display_inequalities(self):
        checked = v.validate_receipt(self.real, *self.selected[0], self.binding)
        self.assertEqual(len(checked), 3)

    def test_exact_log_bound_independent_decimal_reference(self):
        with localcontext() as ctx:
            ctx.prec = 120
            decimal_ln10 = Decimal(10).ln()
            lo, hi = [Decimal(q.numerator)/Decimal(q.denominator) for q in v.LN10]
            self.assertLess(lo, decimal_ln10)
            self.assertLess(decimal_ln10, hi)
            for q in (Fraction(1), Fraction(999999, 1000000), Fraction(1000001, 1000000)):
                a, b = v.log_enclosure(q, 8)
                wanted = (Decimal(q.numerator)/Decimal(q.denominator)).ln()
                self.assertLessEqual(Decimal(a.numerator)/Decimal(a.denominator), wanted)
                self.assertLessEqual(wanted, Decimal(b.numerator)/Decimal(b.denominator))

    def test_gain_and_alias_boundaries_fail_closed(self):
        for change in (
            {'max_coherent_alias_upper': 1e-8},
            {'max_coherent_alias_upper': math.nextafter(1e-8, math.inf)},
            {'min_wanted_transfer_lower': 0.99998},
            {'max_total_transfer_upper': 1.00002},
            {'min_wanted_transfer_lower': True},
            {'max_coherent_alias_upper': float('nan')},
            {'max_coherent_alias_upper': float('inf')},
            {'max_coherent_alias_upper': -1e-9},
        ):
            with self.subTest(change=change):
                self.check_rejected(lambda doc: doc['certificate'].update(change))
        near = deepcopy(self.real['certificate'])
        near['max_coherent_alias_upper'] = math.nextafter(1e-8, 0.0)
        v.check_inequalities(near, 'pass')
        self.assertLess(Fraction(near['max_coherent_alias_upper']), Fraction(1, 100000000))

    def test_status_mode_endpoints_limits_and_missing_fields(self):
        for change in (
            {'status': 'OPEN'}, {'status': 'PASS-LOCAL-STOP-SOURCE'},
            {'band_kind': 'stop'}, {'certified_hz': ['0', '999']},
            {'governing_passband_hz': 39000}, {'governing_stopband_hz': 81000},
            {'native_hz': 5644800}, {'qualified_release': True},
            {'limits': {'passband_db': '0.001', 'coherent_alias_db': '-160'}},
        ):
            with self.subTest(change=change):
                self.check_rejected(lambda doc: doc['certificate'].update(change))
        self.check_rejected(lambda doc: doc['certificate'].pop('max_native_stop_source_transfer_upper'))

    def test_source_proof_harness_and_operator_binding_mismatch(self):
        for key in ('stage_snapshot_sha256', 'verified_operator_binding_sha256'):
            with self.subTest(key=key):
                self.check_rejected(lambda doc: doc.update({key: '0'*64}))
        self.check_rejected(lambda doc: doc['binding']['source'].update({'src/rate.c': '0'*64}))
        self.check_rejected(lambda doc: doc['prover_code_sha256'].pop('p15_src_halfband_majorant.py'))
        self.check_rejected(lambda doc: doc['experiment_identity'].update({'harness_sha256': '0'*64}))
        self.check_rejected(lambda doc: doc['experiment_identity']['job'].update({'hi': '999'}))
        self.check_rejected(lambda doc: doc.update({'canonical_work_index': 5598}))
        self.check_rejected(lambda doc: doc['measurement']['environment'].update({'mpmath': 'unknown'}))

    def test_incomplete_tree_and_alias_population(self):
        for change in (
            {'nodes_examined': 0}, {'fully_proven_subintervals': 0},
            {'exact_branch_splits': 999}, {'exact_path_enumerations': 0},
            {'max_alias_path_population': 9407}, {'interval_subdivisions': True},
        ):
            with self.subTest(change=change):
                self.check_rejected(lambda doc: doc['certificate'].update(change))

    def test_strict_json_duplicate_keys_nonfinite_and_missing_directory(self):
        for data in (b'{"status":"OPEN","status":"PASS"}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.subTest(data=data), self.assertRaises(v.Invalid):
                v.strict_json(data)
        with tempfile.TemporaryDirectory() as temp:
            result = v.verify_receipts(Path(temp), self.selected, self.binding)
            self.assertEqual(result['status'], 'OPEN')
            self.assertEqual(len(result['missing_intervals']), 232)

    def test_aggregation_complete_missing_open_and_invented_work(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for index, job in self.selected:
                (directory / (v.digest(job)+'.json')).write_bytes(v.encoded(self.synthetic(index, job)))
            self.assertEqual(v.verify_receipts(directory, self.selected, self.binding)['status'],
                             'COMPLETE_CANONICAL_RECEIPT_COVERAGE_VERIFIED')
            last = directory / (v.digest(self.selected[-1][1])+'.json')
            raw = last.read_bytes()
            last.unlink()
            result = v.verify_receipts(directory, self.selected, self.binding)
            self.assertEqual(result['status'], 'OPEN')
            self.assertEqual(len(result['missing_intervals']), 1)
            doc = v.strict_json(raw)
            doc['certificate']['status'] = 'OPEN'
            last.write_bytes(v.encoded(doc))
            result = v.verify_receipts(directory, self.selected, self.binding)
            self.assertEqual(result['status'], 'OPEN')
            self.assertEqual(len(result['invalid_receipts']), 1)
            last.write_bytes(raw)
            (directory/'invented.json').write_bytes(raw)
            self.assertEqual(v.verify_receipts(directory, self.selected, self.binding)['status'], 'OPEN')

    def test_publication_is_idempotent_and_immutable(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'receipt.json'
            v.publish(path, b'one\n')
            v.publish(path, b'one\n')
            with self.assertRaises(v.Invalid):
                v.publish(path, b'two\n')
            self.assertEqual(path.read_bytes(), b'one\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)

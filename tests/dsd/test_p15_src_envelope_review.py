"""Offline regression tests for the normative P15 SRC comparator disposition."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import p15_src_envelope_review as src
from p15_readjudication import write_new, EvidenceError


class SRCDispositions(unittest.TestCase):
    def test_all_source_bound_cells_and_comparators_are_classified(self):
        outcome=src.report()
        self.assertEqual(outcome['release_status'],'BLOCKED')
        self.assertEqual(outcome['fractional_diagnostic_cases_disposed'],36)
        self.assertEqual(outcome['integer_ratio_additional_src_cells'],36)
        self.assertEqual(outcome['source_bound_scalar_cells'],81)
        self.assertEqual(outcome['identity_fir_numerical_cases_accepted_scoped'],9)
        self.assertEqual(outcome['cross_isa_observations_inspected'],324)
        self.assertEqual(sum(x['src_active_cells'] for x in outcome['matrices'].values()),72)
        self.assertFalse(outcome['default_promotion_authorized'])
        self.assertFalse(outcome['p16_authorized'])
        self.assertEqual([outcome['matrices'][r]['native_fractional_diagnostic_cells']
                          for r in ('v1','v2')],[24,12])
        self.assertEqual([outcome['matrices'][r]['integer_native_pcm_ratio_but_src_active']
                          for r in ('v1','v2')],[24,12])
        for r in ('v1','v2'):
            rows=outcome['matrices'][r]['cells']
            self.assertTrue(all(not row['status'].startswith('PASS')
                                for row in rows if row['src_active']))
            self.assertTrue(all('DIFFERENT_TRANSFER' in row['status']
                                for row in rows if row['native_pcm_fractional']))

    def test_fir_bound_is_not_reused_for_different_src_transfer(self):
        folder=Path('tests/dsd/results/P15_v2_matrix_2026-10-15')
        p=folder/'scalar/cells/dsd128.mastering_v2.pcm48000.json'
        row=src.read(p)
        self.assertGreater(row['scalar_program']['metric']['max_abs'],
                           row['isolated_fir']['roundoff_bound'])
        self.assertNotEqual(row['intermediate_hz'],row['pcm_hz'])
        # Exceeded FIR epsilon is not declared a failure for unlike transfers.
        self.assertEqual(row['src_reference']['type'],src.REFERENCE)
        self.assertEqual(row['properties']['combined_fractional_src_error'],
                         'MEASURED_REQUIRES_ADJUDICATED_ENVELOPE')

    def test_invalid_metric_fails_closed(self):
        good=dict(first_abs=0.01,last_abs=0.02,interior_max_abs=0.02,
                  max_abs=0.02,rms_abs=0.01,ref_peak=1.0,frames=100)
        self.assertEqual(src.metric(good,'case')['max_abs'],0.02)
        for k,v in [('max_abs',float('nan')),('rms_abs',float('inf')),
                    ('frames',-1),('first_abs',0.1),('ref_peak',-1.)]:
            row=dict(good);row[k]=v
            with self.subTest(k=k),self.assertRaises(src.InvalidEvidence):
                src.metric(row,'case')

    def test_audited_formula_applies_a_priori_bound_not_empirical_epsilon(self):
        result=src.same_operator_threshold(n_ops=2,weighted_input_abs=1.,
                 coefficient_error_abs=0.,other_error_abs=0.,
                 native_fir_propagated_abs=1e-12)
        u=2**-53
        self.assertAlmostEqual(result,1e-12+(2*u/(1-2*u)))
        for bad in (None,-1,float('nan'),float('inf')):
            with self.subTest(bad=bad),self.assertRaises(src.InvalidEvidence):
                src.same_operator_threshold(n_ops=2,weighted_input_abs=1,
                     coefficient_error_abs=bad, other_error_abs=0,
                     native_fir_propagated_abs=0)
        with self.assertRaises(src.InvalidEvidence):
            src.same_operator_threshold(n_ops=2**54,weighted_input_abs=1.,
                 coefficient_error_abs=0.,other_error_abs=0.,
                 native_fir_propagated_abs=0.)

    def test_record_status_laundering_and_hash_swap_refused(self):
        orig=src.read
        target='dsd128.mastering_v2.pcm48000.json'
        def swapped(path):
            row=orig(path)
            if str(path).endswith('/scalar/cells/'+target):
                row=copy.deepcopy(row)
                row['qualified']=True
            return row
        with patch.object(src,'read',side_effect=swapped),self.assertRaisesRegex(
                 src.InvalidEvidence,'identity/status'):
            src.report()
        hash_orig=src.sha
        def forged(path):
            if str(path).endswith('/scalar/cells/'+target):
                return '0'*64
            return hash_orig(path)
        with patch.object(src,'sha',side_effect=forged),self.assertRaisesRegex(
                 src.InvalidEvidence,'hash mismatch'):
            src.report()

    def test_legacy_reviewers_opt_into_current_evidence_and_block_release(self):
        scripts = [
            ('p15_release_manifest.py', '--current-output'),
            ('p15_closeout_review.py', '--output'),
        ]
        with tempfile.TemporaryDirectory() as name:
            for script, output_flag in scripts:
                with self.subTest(script=script):
                    output = Path(name) / (script + '.json')
                    run = subprocess.run(
                        [sys.executable, str(src.ROOT / 'tests/dsd' / script),
                         '--current-evidence', output_flag, str(output), '--require-qualified'],
                        cwd=src.ROOT, text=True, capture_output=True)
                    self.assertEqual(run.returncode, 2, run.stderr)
                    got = json.loads(output.read_text())
                    self.assertEqual(got['status'], 'BLOCKED')
                    self.assertEqual(len(got['substantive_open_gates']), 2)
                    self.assertEqual(got['src_numerical_disposition']
                                      ['fractional_diagnostic_cases_disposed'],36)
                    before = output.read_bytes()
                    again = subprocess.run(
                        [sys.executable, str(src.ROOT / 'tests/dsd' / script),
                         '--current-evidence', output_flag, str(output), '--require-qualified'],
                        cwd=src.ROOT, text=True, capture_output=True)
                    self.assertEqual(again.returncode, 2, again.stderr)
                    self.assertEqual(output.read_bytes(), before)

    def test_numeric_cli_blocked_with_idempotent_receipt(self):
        with tempfile.TemporaryDirectory() as name:
            out=Path(name)/'receipt.json'
            args=[sys.executable, str(src.ROOT/'tests/dsd/p15_src_envelope_review.py'),
                  '--output',str(out),'--require-qualified']
            first=subprocess.run(args,cwd=src.ROOT,text=True,capture_output=True)
            self.assertEqual(first.returncode, 2, first.stderr)
            data=json.loads(out.read_text())
            self.assertEqual(data['fractional_diagnostic_cases_disposed'],36)
            original=out.read_bytes()
            second=subprocess.run(args,cwd=src.ROOT,text=True,capture_output=True)
            self.assertEqual(second.returncode,2,second.stderr)
            self.assertEqual(out.read_bytes(),original)

    def test_historical_result_write_is_idempotent_not_overwritten(self):
        with tempfile.TemporaryDirectory() as name:
            file=Path(name)/'receipt.json'
            row={'release_status':'BLOCKED','numeric_status':'OPEN'}
            write_new(file,row)
            frozen=file.read_bytes()
            write_new(file,row)
            self.assertEqual(file.read_bytes(),frozen)
            with self.assertRaises(EvidenceError):
                write_new(file,{'release_status':'READY','numeric_status':'PASS'})
            self.assertEqual(file.read_bytes(),frozen)


if __name__ == '__main__':
    unittest.main()

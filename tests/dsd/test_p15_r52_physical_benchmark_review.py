"""R5.2 retrospective benchmark evidence: verified arithmetic, not promotion."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from p15_r52_physical_benchmark_review import ROOT,HISTORIC,Refusal,audit

class HistoricPhysicalReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline=audit()
    def test_original_eight_measured_ratios(self):
        r=self.baseline
        self.assertEqual(r['historical_evidence']['comparisons_recomputed'],8)
        self.assertEqual(r['historical_evidence']['lower_95_percent_over_2x'],8)
        self.assertTrue(r['historical_evidence']['captured_eight_source_files_match_current'])
        self.assertFalse(r['historical_evidence']['complete_release_source_dependency_closure'])
        self.assertEqual(r['physical_2x_gate'],'OPEN')
        self.assertEqual(r['historical_evidence']['spectral_audio']['full_payload_integrity'],False)
        self.assertEqual(r['historical_evidence']['bench_audio']['full_payload_integrity'],False)
    def modify_and_reject(self, file, modifier):
        with tempfile.TemporaryDirectory() as d:
            h=Path(d)/'historic'
            shutil.copytree(HISTORIC,h)
            p=h/file
            doc=json.loads(p.read_text());modifier(doc)
            p.write_text(json.dumps(doc))
            with self.assertRaises((Refusal,ValueError,KeyError,TypeError)):
                audit(ROOT,h)
    def test_control_cutoff_tamper_rejected(self):
        def change(d):
            cell=next(iter(d['rows'].values()))
            cell['commands']['legacy_ps_matched'][-3]='-20000'
        self.modify_and_reject('bench/RECEIPT.json',change)
    def test_confidence_interval_tamper_rejected(self):
        def change(d):
            cell=next(iter(d['rows'].values()))
            cell['comparisons']['legacy_direct']['ci95'][0]=99.0
        self.modify_and_reject('bench/RECEIPT.json',change)
    def test_source_binding_tamper_rejected(self):
        def change(d):
            d['source_sha256']['src/rate.c']='0'*64
        self.modify_and_reject('bench/RECEIPT.json',change)
    def test_spectral_edge_exclusion_tamper_rejected(self):
        def change(d):
            d['rows'][0]['verification']['transition_excluded_fraction']=.05
        self.modify_and_reject('comparator/RECEIPT.json',change)
    def test_missing_cell_rejected(self):
        def change(d):
            d['rows'].pop(next(iter(d['rows'])))
        self.modify_and_reject('bench/RECEIPT.json',change)
    def test_reported_host_vm_rejected(self):
        def change(d):
            d['host']['hypervisor']=True
        self.modify_and_reject('bench/RECEIPT.json',change)

if __name__ == '__main__':unittest.main()

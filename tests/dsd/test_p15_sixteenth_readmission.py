#!/usr/bin/env python3
"""Adversarial source-only checks for the exact sixteenth P15 readmission.

These tests do not mint new P15 certificates or impersonate real binaries:
patched hashes model the recording-host precondition *only* for verifying the
retained comparator's payload verification behavior.
"""
from __future__ import annotations

from copy import deepcopy
import json
import shutil
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

THIS = Path(__file__).resolve().parent
ROOT = THIS.parents[1]
SCRIPTS = ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(THIS) not in sys.path:
    sys.path.insert(0, str(THIS))

import verify_p15_sixteenth_readmission as admission
import p16_dev_input_drift as p16
import p15_dsd256_comparator_2026 as comparator
import test_p15_remaining_math as pending


class ReadmissionTests(unittest.TestCase):
    def test_frozen_chain_and_32_admissions(self):
        chain = admission.verify_chain(ROOT)
        self.assertEqual(chain['admitted_entries'], 32)
        self.assertEqual(chain['changed_entries'], 1)
        current = admission.verify_current(ROOT)
        self.assertEqual(current['matched_current_revision_files'], 32)
        self.assertFalse(current['release_qualified'])

    def test_original_index_and_preimage_unchanged(self):
        baseline = admission.original_manifest(ROOT)
        self.assertEqual(baseline[admission.TEST], admission.TEST_P00_SHA)
        archived = admission.file_at(ROOT, admission.REBOUND + '/preimages/' + admission.TEST)
        self.assertEqual(admission.file_hash(archived), admission.TEST_P00_SHA)

    def test_corrupted_test_revision_cannot_pass_current_gate(self):
        real = admission.file_hash
        def corrupt(path):
            if path == ROOT / admission.TEST:
                return '0' * 64
            return real(path)
        with patch.object(admission, 'file_hash', side_effect=corrupt):
            self.assertEqual(admission.verify_chain(ROOT)['changed_entries'], 1)
            with self.assertRaisesRegex(admission.EvidenceError, 'unexpected SHA-256'):
                admission.verify_current(ROOT)

    def test_non_target_admission_mutation_refused(self):
        real = admission.read_json
        def tampered(root, relative, expected_sha=None):
            result = real(root, relative, expected_sha)
            if relative == admission.REBOUND + '/ADMISSION.json':
                result = deepcopy(result)
                target = next(n for n in result['revisions'] if n != admission.TEST)
                result['revisions'][target]['current_sha256'] = '0' * 64
            return result
        with patch.object(admission, 'read_json', side_effect=tampered):
            with self.assertRaisesRegex(admission.EvidenceError, 'unreviewed admission revision'):
                admission.verify_chain(ROOT)

    def test_amendment_tampering_refused(self):
        real = admission.file_hash
        def corrupt(path):
            if path == ROOT / admission.FOLLOWON / 'READMISSION.json':
                return '0' * 64
            return real(path)
        with patch.object(admission, 'file_hash', side_effect=corrupt):
            with self.assertRaisesRegex(admission.EvidenceError, 'unexpected SHA-256'):
                admission.verify_chain(ROOT)

    def test_p16_dev_only_drift_does_not_self_approve(self):
        baseline = p16.report(ROOT)
        self.assertEqual(baseline['drift_count'], 0)
        self.assertFalse(baseline['certified'])
        real = p16.file_hash
        def changed(path):
            if path == ROOT / admission.TEST:
                return 'f' * 64
            return real(path)
        with patch.object(p16, 'file_hash', side_effect=changed):
            drift = p16.report(ROOT)
        self.assertEqual(drift['drift_count'], 1)
        self.assertEqual(drift['p00_indexed_drift'][0]['path'], admission.TEST)
        self.assertEqual(drift['p00_indexed_drift'][0]['status'], 'MODIFIED')
        self.assertFalse(drift['historical_p15_source_qualified'])

    def test_off_host_with_local_binaries_skips_not_error(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            for p in ('src/sox', 'test/sox_p10_candidate'):
                target = work / p
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'locally built but not recording-host binary')
            with patch.object(pending, 'ROOT', work), \
                 patch.object(pending, 'verify_match', side_effect=AssertionError('must not replay')):
                with self.assertRaisesRegex(unittest.SkipTest, 'not the ones'):
                    pending.ComparatorTests('test_replay_matched_and_wrong_control').test_replay_matched_and_wrong_control()

    def test_original_comparator_with_matching_hash_precondition(self):
        # Model the two exact binary hashes without claiming the fake
        # executables are actually the measured recording-host binaries.
        folder = THIS / 'results/P15_REMAINING_PROOF_2026-10-16'
        record = json.loads((folder / 'ps-matched-comparator/RECEIPT.json').read_text())
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            binaries = (work / 'sox', work / 'candidate')
            for f in binaries:
                f.write_bytes(b'not a recorded binary')
            orig_sha = comparator.file_sha
            def binary_hash(path):
                if Path(path) == binaries[0]:
                    return record['executable_sha256']['sox']
                if Path(path) == binaries[1]:
                    return record['executable_sha256']['candidate']
                return orig_sha(path)
            with patch.object(comparator, 'file_sha', side_effect=binary_hash):
                a = comparator.verify(folder / 'ps-matched-comparator', *binaries)
                b = comparator.verify(folder / 'ps-matched-comparator-negative-selftest',
                                      *binaries, allow_wrong=True)
                self.assertTrue(a['spectrally_matched_on_fixture'])
                self.assertFalse(b['spectrally_matched_on_fixture'])
                self.assertEqual((len(a['rows']), len(b['rows'])), (4, 4))
                fake = work / 'tampered'
                fake.mkdir()
                for f in (folder / 'ps-matched-comparator').iterdir():
                    if f.name == 'RECEIPT.json':
                        doc = json.loads(f.read_text())
                        first = next(iter(doc['file_sha256']))
                        doc['file_sha256'][first] = '0' * 64
                        (fake / f.name).write_text(json.dumps(doc))
                    else:
                        # Hardlinks need one filesystem. A tempdir on another
                        # device is ordinary, so fall back to a copy: this
                        # fixture only needs identical bytes.
                        try:
                            (fake / f.name).hardlink_to(f)
                        except OSError:
                            shutil.copy2(f, fake / f.name)
                with self.assertRaisesRegex(comparator.InvalidReceipt,
                                            'missing/extra/modified receipt payload'):
                    comparator.verify(fake, *binaries)


if __name__ == '__main__':
    unittest.main()

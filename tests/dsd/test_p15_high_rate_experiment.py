#!/usr/bin/env python3
"""Cheap fresh-process tests of experiment isolation and evidence binding.

Synthetic prover trees exercise the real harness import/publication path; no
spectral arithmetic or high-rate campaign runs are required. Their campaign
stub checks the same job/band/source invariants used by the real dispatcher.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


HARNESS = Path(__file__).resolve().with_name('p15_high_rate_experiment.py')

CAMPAIGN = r'''
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCHEMA='P15/full-frequency-cover-campaign/1'
class IntervalBudgetExpired(TimeoutError): pass
def canonical_plan():
    return [dict(cell_id='fixture.pass',profile='master256',intermediate_hz=176400,
                 output_hz=384000,mode='pass',lo='39000',hi='40000',
                 effective_p='40000',source_s=80000),
            dict(cell_id='fixture.stop',profile='master256',intermediate_hz=176400,
                 output_hz=384000,mode='stop',lo='191000',hi='192000',
                 effective_p='40000',source_s=80000)]
def bindings():
    return dict(source={'source.txt':sha256((ROOT/'source.txt').read_bytes()).hexdigest()},
                design=sha256((ROOT/'design.txt').read_bytes()).hexdigest())
def receipt_path(output,job):
    digest=sha256(json.dumps(job,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return output/(digest+'.json')
def check_one(output,job,binding):
    doc=json.loads(receipt_path(output,job).read_text())
    if doc.get('schema')!=SCHEMA or doc.get('job')!=job or doc.get('binding')!=binding:
        raise ValueError('fixture canonical/source binding mismatch')
    if doc.get('qualified_release') is not False:
        raise ValueError('fixture release mismatch')
    cert=doc['certificate']
    expected='PASS-LOCAL-BAND' if job['mode']=='pass' else 'PASS-LOCAL-STOP-SOURCE'
    if cert['status'] not in ('OPEN',expected):
        raise ValueError('fixture band status mismatch')
    if cert['status']!='OPEN' and (
        cert['certified_hz']!=[job['lo'],job['hi']] or
        cert['band_kind']!=job['mode'] or cert['input_hz']!=job['intermediate_hz'] or
        cert['output_hz']!=job['output_hz'] or cert['governing_passband_hz']!=40000):
        raise ValueError('fixture certificate scope mismatch')
    return doc
@contextmanager
def interval_deadline(seconds):
    yield
'''

CAPTURE = r'''
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]
DEFAULT=ROOT/'tests/dsd/captures'
def verify_pair(pair,input_hz,output_hz):
    action=(ROOT/'action.txt').read_text()
    if action=='proof_during_verify':
        file=Path(__file__).with_name('p15_src_stagewise_continuum.py')
        file.write_text(file.read_text().replace("VARIANT = 'baseline'", "VARIANT = 'rebound'"))
    elif action=='snapshot_during_verify':
        (pair/'stage-snapshot.json').write_text('changed during verify\n')
    elif action=='source_during_verify':
        (ROOT/'source.txt').write_text('changed during verify\n')
    return {},SimpleNamespace(input_hz=input_hz,output_hz=output_hz)
'''

PROVER = r'''
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
VARIANT = 'baseline'
def certificate(profile,operator,lo,hi,mode='pass',**kwargs):
    action=(ROOT/'action.txt').read_text()
    pair=ROOT/'tests/dsd/captures/176400-384000'
    if action=='proof':
        file=Path(__file__)
        file.write_text(file.read_text()+'\n# proof changed during evaluation\n')
    elif action=='source':
        (ROOT/'source.txt').write_text('changed during evaluation\n')
    elif action=='snapshot':
        (pair/'stage-snapshot.json').write_text('changed during evaluation\n')
    elif action=='operator_binding':
        (pair/'operator-binding.json').write_text('changed during evaluation\n')
    elif action=='harness':
        file=Path(os.environ['P15_TEST_HARNESS_MUTATION_TARGET'])
        file.write_text(file.read_text()+'\n# harness changed during evaluation\n')
    elif action=='late_import':
        import p15_lazy_dependency
    return dict(status='PASS-LOCAL-BAND' if mode=='pass' else 'PASS-LOCAL-STOP-SOURCE',
                qualified_release=False,profile=profile,input_hz=operator.input_hz,
                output_hz=operator.output_hz,band_kind=mode,certified_hz=[lo,hi],
                governing_passband_hz=40000,diagnostic_fixture_variant=VARIANT)
'''


class ExperimentHarness(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def tree(self, name, variant='baseline'):
        root = self.directory / name
        base = root / 'tests/dsd'
        base.mkdir(parents=True)
        for filename, contents in (
            ('p15_full_band_campaign.py', CAMPAIGN),
            ('p15_src_capture_matrix.py', CAPTURE),
            ('p15_src_stagewise_continuum.py', PROVER.replace("VARIANT = 'baseline'", f"VARIANT = '{variant}'")),
            ('p15_lazy_dependency.py', 'VALUE=1\n'),
        ):
            (base / filename).write_text(textwrap.dedent(contents))
        pair = base / 'captures/176400-384000'
        pair.mkdir(parents=True)
        (pair / 'stage-snapshot.json').write_text('{"snapshot":"fixed"}\n')
        (pair / 'operator-binding.json').write_text('{"operator":"fixed"}\n')
        (root / 'source.txt').write_text('fixed source\n')
        (root / 'design.txt').write_text('fixed design\n')
        (root / 'action.txt').write_text('none')
        return root

    def run_harness(self, root, output, *, harness=HARNESS, label='test', index=0,
                    seconds=2, extra=(), env=None):
        environment = os.environ.copy()
        environment['OPENBLAS_NUM_THREADS'] = '1'
        if env:
            environment.update(env)
        command = [sys.executable, str(harness), '--source-root', str(root),
                   '--job-index', str(index), '--label', label, '--output', str(output),
                   '--seconds', str(seconds), *extra]
        return subprocess.run(command, capture_output=True, text=True,
                              env=environment, timeout=15, cwd=self.directory)

    def read_receipt(self, output):
        files = list(output.glob('*.json'))
        self.assertEqual(len(files), 1)
        return files[0], json.loads(files[0].read_text())

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_actual_baseline_candidate_module_isolation(self):
        baseline = self.tree('baseline', 'baseline')
        candidate = self.tree('candidate', 'candidate')
        identities = []
        for name, root in [('baseline', baseline), ('candidate', candidate)]:
            output = self.directory / ('receipts-' + name)
            result = self.run_harness(root, output, label=name)
            self.assert_success(result)
            _, receipt = self.read_receipt(output)
            self.assertEqual(receipt['certificate']['diagnostic_fixture_variant'], name)
            self.assertEqual(receipt['measurement']['environment']['imported_prover'],
                             str(root / 'tests/dsd/p15_src_stagewise_continuum.py'))
            code = receipt['experiment_identity']['prover_code_sha256']
            self.assertEqual(code['p15_src_stagewise_continuum.py'], sha256(
                (root / 'tests/dsd/p15_src_stagewise_continuum.py').read_bytes()).hexdigest())
            identities.append(code['p15_src_stagewise_continuum.py'])
        self.assertNotEqual(*identities)

    def test_idempotent_resume_does_not_reexecute_or_overwrite(self):
        root = self.tree('baseline')
        output = self.directory / 'receipts'
        self.assert_success(self.run_harness(root, output))
        file, _ = self.read_receipt(output)
        original = file.read_bytes()
        # This action would reject execution if resume called the prover.
        (root / 'action.txt').write_text('late_import')
        result = self.run_harness(root, output)
        self.assert_success(result)
        self.assertEqual(json.loads(result.stdout)['action'], 'SKIP')
        self.assertEqual(file.read_bytes(), original)

    def test_changed_budget_and_code_are_refused_without_overwrite(self):
        for mutation in ('budget', 'code', 'source', 'label', 'harness'):
            with self.subTest(mutation=mutation):
                root = self.tree('tree-' + mutation)
                output = self.directory / ('receipts-' + mutation)
                self.assert_success(self.run_harness(root, output))
                file, _ = self.read_receipt(output)
                original = file.read_bytes()
                kwargs = {}
                if mutation == 'budget':
                    kwargs['seconds'] = 3
                elif mutation == 'code':
                    proof = root / 'tests/dsd/p15_src_stagewise_continuum.py'
                    proof.write_text(proof.read_text() + '\n# new prover version\n')
                elif mutation == 'source':
                    (root / 'source.txt').write_text('new source version\n')
                elif mutation == 'label':
                    kwargs['label'] = 'different'
                else:
                    copy = self.directory / 'changed_harness.py'
                    copy.write_text(HARNESS.read_text() + '\n# new harness version\n')
                    kwargs['harness'] = copy
                result = self.run_harness(root, output, **kwargs)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('different inputs/code/budget', result.stderr)
                self.assertEqual(file.read_bytes(), original)

    def test_canonical_index_selects_exact_job_and_band(self):
        root = self.tree('baseline')
        output = self.directory / 'stop'
        self.assert_success(self.run_harness(root, output, index=1))
        _, receipt = self.read_receipt(output)
        self.assertEqual(receipt['canonical_work_index'], 1)
        self.assertEqual(receipt['job']['cell_id'], 'fixture.stop')
        self.assertEqual(receipt['job']['mode'], 'stop')
        self.assertEqual(receipt['certificate']['certified_hz'], ['191000', '192000'])
        self.assertEqual(receipt['experiment_identity']['job'], receipt['job'])
        result = self.run_harness(root, self.directory / 'invalid', index=2)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('canonical job index out of range', result.stderr)

    def test_foreign_numerical_module_is_rejected(self):
        root = self.tree('baseline')
        foreign = self.directory / 'foreign'
        foreign.mkdir()
        (foreign / 'p15_foreign_dependency.py').write_text('VALUE=1\n')
        capture = root / 'tests/dsd/p15_src_capture_matrix.py'
        capture.write_text(capture.read_text() + '\nimport sys\nsys.path.insert(0,' +
                           repr(str(foreign)) + ')\nimport p15_foreign_dependency\n')
        output = self.directory / 'receipts'
        result = self.run_harness(root, output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('mixed prover implementations', result.stderr)
        self.assertFalse(list(output.glob('*.json')))

    def test_numerical_or_source_mutation_during_evaluation_is_rejected(self):
        for action in ('proof', 'source', 'late_import'):
            with self.subTest(action=action):
                root = self.tree('tree-' + action)
                output = self.directory / ('receipts-' + action)
                (root / 'action.txt').write_text(action)
                result = self.run_harness(root, output)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(list(output.glob('*.json')))

    def test_snapshot_operator_and_harness_mutation_are_rejected(self):
        for action in ('snapshot', 'operator_binding', 'harness'):
            with self.subTest(action=action):
                root = self.tree('tree-' + action)
                output = self.directory / ('receipts-' + action)
                (root / 'action.txt').write_text(action)
                copy = self.directory / ('harness-' + action + '.py')
                shutil.copyfile(HARNESS, copy)
                result = self.run_harness(root, output, harness=copy,
                    env={'P15_TEST_HARNESS_MUTATION_TARGET': str(copy)})
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(list(output.glob('*.json')))

    def test_loaded_proof_or_snapshot_cannot_rebind_during_verify(self):
        for action in ('proof_during_verify', 'snapshot_during_verify'):
            with self.subTest(action=action):
                root = self.tree('tree-' + action)
                output = self.directory / ('receipts-' + action)
                (root / 'action.txt').write_text(action)
                result = self.run_harness(root, output)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(list(output.glob('*.json')))

    def test_resume_rechecks_inputs_after_operator_verification(self):
        for action in ('snapshot_during_verify', 'source_during_verify'):
            with self.subTest(action=action):
                root = self.tree('tree-' + action)
                output = self.directory / ('receipts-' + action)
                self.assert_success(self.run_harness(root, output))
                file, _ = self.read_receipt(output)
                original = file.read_bytes()
                (root / 'action.txt').write_text(action)
                result = self.run_harness(root, output)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(file.read_bytes(), original)

    def test_invalid_resource_budget_and_linked_receipt_are_rejected(self):
        root = self.tree('baseline')
        for seconds in ('nan', 'inf', '0', '-1', '3601'):
            result = self.run_harness(root, self.directory / 'invalid', seconds=seconds)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('invalid bounded experiment resources', result.stderr)
        output = self.directory / 'receipts'
        self.assert_success(self.run_harness(root, output))
        file, _ = self.read_receipt(output)
        saved = self.directory / 'saved.json'
        file.rename(saved)
        file.symlink_to(saved)
        result = self.run_harness(root, output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unsafe existing experiment receipt', result.stderr)


if __name__ == '__main__':
    unittest.main()

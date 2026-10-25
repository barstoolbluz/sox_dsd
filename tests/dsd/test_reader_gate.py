"""Fault injection and fail-closed qualification checks (no licensed PCM)."""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

# In the review bundle the modules sat in a sibling 'code' directory; in
# the repository they live beside this file. Accept either.
_here = Path(__file__).resolve().parent
CODE = _here if (_here / 'p21_independent_reader.py').is_file() else \
       _here.parent / 'code'
sys.path.insert(0, str(CODE))
import p21_independent_reader as gate
import p17_media_qualification as collector


def audio(tmp_path, seconds=1.0):
    sr = 176400
    n = int(sr * seconds)
    t = np.arange(n) / sr
    reference = np.stack((0.4*np.sin(2*np.pi*331*t)+0.12*np.sin(2*np.pi*1993*t),
                          0.34*np.sin(2*np.pi*383*t)+0.1*np.sin(2*np.pi*1733*t)),axis=1)
    control = np.stack((.4*np.sin(2*np.pi*227*t),.34*np.sin(2*np.pi*503*t)),axis=1)
    ref_path, ours_path, control_path = (tmp_path / f'{n}.ref.f64',
                                        tmp_path / f'{n}.ours.f64',
                                        tmp_path / f'{n}.control.f64')
    reference.astype('<f8').tofile(ref_path)
    control.astype('<f8').tofile(control_path)
    return sr, reference, (ours_path, ref_path, control_path)


def compare(data, paths, sr, seconds):
    data.astype('<f8').tofile(paths[0])
    return gate.compare(*paths, sr, seconds)


def test_clean_stereo_passes(tmp_path):
    hz, reference, paths = audio(tmp_path)
    metrics, why = compare(reference, paths, hz, 1)
    assert why is None
    assert gate.judge(metrics) == (True, [])


@pytest.mark.parametrize('fault', ['swap','gain','shift','noise','truncation','missing-control',
                                  'odd-frame','nonfinite'])
def test_faults_fail_closed(tmp_path, fault):
    hz, reference, paths = audio(tmp_path)
    bad = reference.copy()
    if fault == 'swap':
        bad = bad[:, ::-1]
    elif fault == 'gain':
        bad *= 1.05
    elif fault == 'shift':
        bad = np.roll(bad, 64, axis=0)
    elif fault == 'noise':
        bad = np.random.default_rng(3).normal(0, bad.std(), bad.shape)
    elif fault == 'truncation':
        bad = bad[:hz//2 + 200]
    elif fault == 'nonfinite':
        bad[1000,0] = float('nan')
    metrics, why = compare(bad, paths, hz, 1)
    if fault == 'missing-control':
        paths[2].unlink()
        metrics, why = gate.compare(*paths, hz, 1)
    elif fault == 'odd-frame':
        with paths[0].open('ab') as f:
            f.write(b'12345678')
        metrics, why = gate.compare(*paths, hz, 1)
    if why is not None:
        assert metrics is None
    else:
        passed, reasons = gate.judge(metrics)
        assert not passed, fault
        assert reasons


def test_short_drop_is_caught_locally_even_if_global_r_passes(tmp_path):
    hz, reference, paths = audio(tmp_path, 10)
    bad = reference.copy()
    bad[5*hz:5*hz+hz//100] = 0
    metrics, why = compare(bad, paths, hz, 10)
    assert why is None
    assert all(c['pearson_r'] >= gate.MIN_PEARSON for c in metrics['channels'])
    assert all(abs(c['level_delta_db']) <= gate.MAX_LEVEL_DELTA_DB
               for c in metrics['channels'])
    passed, reasons = gate.judge(metrics)
    assert not passed
    assert any('local residual' in reason for reason in reasons)


def test_zero_or_nan_control_fails(tmp_path):
    hz, reference, paths = audio(tmp_path)
    reference.astype('<f8').tofile(paths[0])
    copy = gate.compare(*paths, hz, 1)[0]
    for control in (None, [float('nan'), 0.0], [1.0, 1.0], [float('inf'), 0.0]):
        changed = dict(copy)
        changed['control_pearson_r'] = control
        assert not gate.judge(changed)[0]




def test_mutation_shim_forwards_probes_and_mutates_only_decode(tmp_path):
    sox, _, media = make_fake_environment(tmp_path)
    shim = CODE / 'mutation-shim.py'
    env = dict(os.environ, SOX_REAL=str(sox), MUTATION='gain')
    source = next(media.glob('*.dsf'))
    probe = subprocess.run([sys.executable, str(shim), '--i', '-r', str(source)],
                           env=env, capture_output=True, text=True, timeout=15)
    assert probe.returncode == 0 and probe.stdout.strip() == '22579200'
    ref = tmp_path / 'clean.f64'
    altered = tmp_path / 'altered.f64'
    cmd = ['--dsd-layout-loss', 'warn', '-D', str(source), '-t', 'f64',
           '-r', '176400', '-c', '2', str(ref), 'trim', '0', '1']
    subprocess.run([str(sox), *cmd], check=True, timeout=15)
    cmd[cmd.index('trim')-1] = str(altered)
    subprocess.run([sys.executable, str(shim), *cmd], env=env, check=True, timeout=15)
    clean = np.fromfile(ref, dtype='<f8')
    mutated = np.fromfile(altered, dtype='<f8')
    assert np.allclose(mutated, clean * 1.05)
    assert mutated.size == clean.size


def test_dropout_shim_fails_at_shortest_comparison_interval(tmp_path):
    sox, _, media = make_fake_environment(tmp_path)
    first, second = sorted(media.glob('*.dsf'))
    shim = CODE / 'mutation-shim.py'
    clean, mutated, control = (tmp_path / f'{name}.f64'
                               for name in ('clean', 'mutated', 'control'))
    cmd = ['--dsd-layout-loss', 'warn', '-D', str(first), '-t', 'f64',
           '-r', '176400', '-c', '2', str(clean), 'trim', '0', '.5']
    subprocess.run([str(sox), *cmd], check=True, timeout=15)
    cmd[cmd.index('trim') - 1] = str(mutated)
    subprocess.run([sys.executable, str(shim), *cmd], check=True, timeout=15,
                   env=dict(os.environ, SOX_REAL=str(sox), MUTATION='dropout'))
    cmd[cmd.index('-D') + 1] = str(second)
    cmd[cmd.index('trim') - 1] = str(control)
    subprocess.run([str(sox), *cmd], check=True, timeout=15)
    unmodified = np.fromfile(clean, dtype='<f8').reshape(-1, 2)
    changed = np.fromfile(mutated, dtype='<f8').reshape(-1, 2)
    start = len(changed) // 2
    assert np.array_equal(changed[:start], unmodified[:start])
    assert np.array_equal(changed[start:start + 1764], np.zeros((1764, 2)))
    assert np.array_equal(changed[start + 1764:], unmodified[start + 1764:])
    metrics, error = gate.compare(mutated, clean, control, 176400, 0.5)
    assert error is None
    assert not gate.judge(metrics)[0]


def test_native_dsd_clock_is_read_from_both_container_headers(tmp_path):
    spec = importlib.util.spec_from_file_location(
        'fake_encoder', Path(__file__).with_name('fake_decoder.py'))
    fake = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fake)
    raw = tmp_path / 'audio.f64'
    raw.write_bytes(b'pcm data')
    for container in ('dsf', 'dff'):
        for rate in gate.SELF_RATES:
            path = tmp_path / f'{rate}.{container}'
            fake.encode_fake_dsd(path, raw, rate)
            assert gate.native_dsd_rate(path, container) == rate
    invalid = tmp_path / 'invalid.dff'
    invalid.write_bytes(b'FRM8' + b'\0' * 32)
    with pytest.raises(ValueError):
        gate.native_dsd_rate(invalid, 'dff')


@pytest.mark.parametrize('field,value', [
    ('packed_expanded_equal', False), ('pcm_frames', 0),
    ('pcm_frames', None), ('native_frames', 0), ('rate_hz', 0),
])
def test_p17_refuses_reuse_with_contradictory_decoder_receipt(tmp_path, field, value):
    _, _, media = make_fake_environment(tmp_path)
    probe = tmp_path / 'p17-probe'
    probe.write_bytes(Path(__file__).with_name('fake_p17_probe.py').read_bytes())
    probe.chmod(0o755)
    output = tmp_path / 'p17-results'
    cmd = [sys.executable, str(CODE / 'p17_media_qualification.py'),
           '--probe', str(probe), '--media-root', str(media),
           '--results', str(output), '--expected-dsd512-tracks', '2',
           '--require-media', '--independent-reader-evidence',
           str(tmp_path / 'unavailable-reader.json')]
    first = subprocess.run(cmd, text=True, capture_output=True, timeout=20)
    assert first.returncode == 0, first.stderr
    again = subprocess.run(cmd, text=True, capture_output=True, timeout=20)
    assert again.returncode == 0 and again.stdout.count('REUSE') == 4
    receipt = next((output / 'full_file').glob('*.json'))
    changed = json.loads(receipt.read_text())
    changed['decoder'][field] = value
    receipt.write_text(json.dumps(changed))
    rejected = subprocess.run(cmd, text=True, capture_output=True, timeout=20)
    assert rejected.returncode != 0
    assert 'refusing stale/mismatched media receipt overwrite' in rejected.stderr


def test_p17_rejects_invalid_cached_identity_and_preserves_receipt_index(tmp_path):
    _, _, media = make_fake_environment(tmp_path)
    probe = tmp_path / 'p17-probe'
    probe.write_bytes(Path(__file__).with_name('fake_p17_probe.py').read_bytes())
    probe.chmod(0o755)
    output = tmp_path / 'p17-results'
    cmd = [sys.executable, str(CODE / 'p17_media_qualification.py'),
           '--probe', str(probe), '--media-root', str(media),
           '--results', str(output), '--expected-dsd512-tracks', '2',
           '--require-media', '--independent-reader-evidence',
           str(tmp_path / 'unavailable-reader.json')]
    first = subprocess.run(cmd, text=True, capture_output=True, timeout=20)
    assert first.returncode == 0, first.stderr
    report_path = output / 'commercial-decode-evidence.json'
    original_index = json.loads(report_path.read_text())['case_receipts']
    assert len(original_index) == 4
    assert all((output / rel).is_file() for rel in original_index)
    reused = subprocess.run(cmd, text=True, capture_output=True, timeout=20)
    assert reused.returncode == 0 and reused.stdout.count('REUSE') == 4

    receipt = output / next(iter(original_index))
    original_receipt = receipt.read_text()
    for field, value in (('schema', 'P17/unknown/0'),
                         ('source_id', 'bogus-casereceipt-id'),
                         ('source_bytes', -1), ('source_bytes', 1000000),
                         ('source_bytes', None)):
        changed = json.loads(original_receipt)
        changed[field] = value
        try:
            receipt.write_text(json.dumps(changed))
            rejected = subprocess.run(cmd, text=True, capture_output=True, timeout=20)
            assert rejected.returncode != 0, field
            assert 'refusing stale/mismatched media receipt overwrite' in rejected.stderr
            assert json.loads(report_path.read_text())['case_receipts'] == original_index
        finally:
            receipt.write_text(original_receipt)
    assert all((output / rel).is_file() for rel in original_index)
    valid = subprocess.run(cmd, text=True, capture_output=True, timeout=20)
    assert valid.returncode == 0 and valid.stdout.count('REUSE') == 4
    assert json.loads(report_path.read_text())['case_receipts'] == original_index


def test_p17_uses_same_acceptance_rules_for_new_and_reused_decodes():
    sample = {'status': 'PASS_FUNCTIONAL_ONLY', 'packed_expanded_equal': True,
              'rate_hz': 22579200, 'channels': 2, 'profile': 'mastering',
              'destination_hz': 176400, 'kernel': 'scalar',
              'native_frames': 22579200, 'pcm_frames': 176400}
    assert collector.functional_decode_pass(sample, 0, 'mastering', 176400, 'scalar')
    for key, value in (('native_frames', True), ('native_frames', 'bad'),
                       ('pcm_frames', 176399), ('pcm_frames', None)):
        changed = dict(sample, **{key: value})
        assert not collector.functional_decode_pass(
            changed, 0, 'mastering', 176400, 'scalar')
    assert not collector.functional_decode_pass(sample, 1, 'mastering', 176400, 'scalar')


def test_licensed_path_redacted_from_decoder_errors(tmp_path):
    source = tmp_path / 'secret-title.dsf'
    raw = f'cannot decode {source} or {source.name}'
    assert 'secret-title.dsf' not in gate.sanitized(raw, source)
    assert 'secret-title.dsf' not in collector.sanitized(raw, source)


def test_incomplete_profile_set_cannot_qualify_row():
    c = {'source_sha256': 'a'*64, 'media_provenance': 'self-encoded',
         'capability_row': 'dff-read-45158400', 'profile_id': 'decode.mastering.v1',
         'status': 'PASS'}
    cases = [c, {**c, 'source_sha256': 'b'*64}]
    rows, _, _, _ = gate.summarize_cases(cases)
    assert rows['dff-read-45158400'] is False


@pytest.mark.parametrize('env,expected', [
    ({'FAKE_EXTRACT_FAIL': '1'}, 'licensed PCM extraction failed'),
    ({'FAKE_WRONG_CLOCK': '1'}, 'wrong native DSD clock'),
])
def test_self_encoded_inputs_fail_closed_on_provenance_or_clock(tmp_path, env, expected):
    proc, _, _, _, results = run_gate(tmp_path, env)
    assert proc.returncode != 0
    assert expected in proc.stderr
    assert not (results / 'independent-reader-evidence.json').exists()


@pytest.mark.slow
def test_duplicate_self_encoded_source_does_not_overwrite_a_receipt(tmp_path):
    proc, _, _, _, results = run_gate(tmp_path, {'FAKE_COLLIDE_SOURCES': '1'})
    assert proc.returncode != 0
    assert 'duplicate reader case receipt' in proc.stderr
    assert not (results / 'independent-reader-evidence.json').exists()


def make_fake_environment(tmp_path):
    src = Path(__file__).with_name('fake_decoder.py')
    sox, ref = tmp_path / 'sox', tmp_path / 'ffmpeg'
    sox.write_bytes(src.read_bytes()); ref.write_bytes(src.read_bytes())
    sox.chmod(0o755); ref.chmod(0o755)
    media = tmp_path / 'licensed'
    media.mkdir()
    for i in range(2):
        (media/f'commercial-{i}.dsf').write_bytes(f'commercial-track-{i}'.encode())
    return sox, ref, media


def run_gate(tmp_path, env_override=None, with_self=True):
    sox, ref, media = make_fake_environment(tmp_path)
    results = tmp_path / 'out'
    env = dict(os.environ, FAKE_DECODER='sox')
    if env_override:
        env.update(env_override)
    args = [sys.executable, str(CODE / 'p21_independent_reader.py'),
            '--sox', str(sox), '--reference', str(ref), '--media-root', str(media),
            '--results', str(results), '--scratch', str(tmp_path / 'scratch'),
            '--start-seconds', '0', '--seconds', '1',
            '--timeout', '30', '--require-media']
    if with_self:
        args += ['--self-encoded']
    # The outer budget covers all 30 high-rate cases; --timeout remains the
    # 30-second limit for each individual decoder process in the test double.
    proc = subprocess.run(args, capture_output=True, text=True, env=env,
                          timeout=420)
    return proc, sox, ref, media, results


@pytest.fixture(scope='module')
def full_run(tmp_path_factory):
    return run_gate(tmp_path_factory.mktemp('full-reader'))


@pytest.mark.slow
def test_end_to_end_and_collector_validation(full_run):
    proc, sox, ref, media, results = full_run
    assert proc.returncode == 0, proc.stdout[-2000:] + '\n' + proc.stderr[-2000:]
    report_path = results / 'independent-reader-evidence.json'
    report = json.loads(report_path.read_text())
    assert report['independent_reader_and_audio_reference_gate'] == 'PASS'
    assert report['case_count'] == 30
    assert not list((results.parent / 'scratch').iterdir())  # no retained PCM
    assert all((results / rel).is_file() for rel in report['case_receipts'])
    assert report['rows_qualified'] == {r: True for r in gate.EXPECTED_ROWS}
    assert report['rows_qualified_commercial']['dsf-read-22579200'] is True
    commercial = {gate.sha(path) for path in media.glob('*.dsf')}
    loaded, rows, cr, profiles = collector.validate_reader_evidence(report_path, commercial, sox, ref)
    assert loaded == report and cr['dsf-read-22579200']
    assert profiles['dsf-read-22579200']['decode.mastering.v1']

    # A summary-only forgery must not turn an incomplete case set into a PASS.
    wrong = copy.deepcopy(report)
    wrong['case_receipts'].pop(next(iter(wrong['case_receipts'])))
    report_path.write_text(json.dumps(wrong))
    with pytest.raises(ValueError):
        collector.validate_reader_evidence(report_path, commercial, sox, ref)
    report_path.write_text(json.dumps(report))

    case_name = next(iter(report['case_receipts']))
    case_path = results / case_name
    original = case_path.read_text()
    case_path.unlink()
    with pytest.raises(ValueError, match='missing reader receipt'):
        collector.validate_reader_evidence(report_path, commercial, sox, ref)
    case_path.write_text(original)

    with pytest.raises(ValueError, match='commercial source hashes differ'):
        collector.validate_reader_evidence(report_path, {'0'*64}, sox, ref)
    assert collector.validate_reader_evidence(report_path, commercial, sox, ref)[0] == report

    altered = json.loads(original)
    altered['metrics']['channels'][0]['pearson_r'] = .3
    case_path.write_text(json.dumps(altered))
    with pytest.raises(ValueError, match='invalid stored reader metrics'):
        collector.validate_reader_evidence(report_path, commercial, sox, ref)
    case_path.write_text(original)

    altered = json.loads(original)
    altered['media_provenance'] = 'commercial' if altered['media_provenance'] == 'self-encoded' else 'self-encoded'
    case_path.write_text(json.dumps(altered))
    with pytest.raises(ValueError):
        collector.validate_reader_evidence(report_path, commercial, sox, ref)
    case_path.write_text(original)

    # Different runner/binary or a schema-v1 report are not current evidence.
    bad_report = copy.deepcopy(report)
    bad_report['runner_sha256'] = '1'*64
    report_path.write_text(json.dumps(bad_report))
    with pytest.raises(ValueError, match='code changed'):
        collector.validate_reader_evidence(report_path, commercial, sox, ref)
    report_path.write_text(json.dumps(report))

    bad_report['schema'] = 'P21/independent-reader-evidence/1'
    bad_report['runner_sha256'] = report['runner_sha256']
    report_path.write_text(json.dumps(bad_report))
    with pytest.raises(ValueError, match='unsupported'):
        collector.validate_reader_evidence(report_path, commercial, sox, ref)
    report_path.write_text(json.dumps(report))



@pytest.mark.slow
def test_p17_refuses_unlicensed_stimulus_origin(full_run):
    proc, sox, ref, media, results = full_run
    assert proc.returncode == 0, proc.stderr
    path = results / 'independent-reader-evidence.json'
    report = json.loads(path.read_text())
    case = next(results / rel for rel in report['case_receipts']
                if 'self' in json.loads((results / rel).read_text())['media_provenance'])
    prior = case.read_bytes()
    altered = json.loads(prior)
    altered['stimulus_origin'] = 'synthetic'
    try:
        case.write_text(json.dumps(altered))
        with pytest.raises(ValueError, match='provenance not qualified'):
            collector.validate_reader_evidence(
                path, {gate.sha(p) for p in media.glob('*.dsf')}, sox, ref)
    finally:
        case.write_bytes(prior)



@pytest.mark.slow
def test_failed_decode_has_nonzero_exit(tmp_path):
    proc, _, _, _, results = run_gate(tmp_path, {'FAKE_MUTATION': 'gain'}, with_self=False)
    assert proc.returncode != 0
    assert json.loads((results / 'independent-reader-evidence.json').read_text())[
        'independent_reader_and_audio_reference_gate'] == 'FAIL'

@pytest.mark.slow
def test_p17_collector_fail_closed_and_profile_scope(tmp_path, full_run):
    # Use the one complete, synthetic P21 run, then independently exercise
    # the collector's case/provenance validation and profile mapping.
    proc, sox, ref, media, results = full_run
    assert proc.returncode == 0, proc.stdout[-2000:] + '\n' + proc.stderr[-2000:]
    probe = tmp_path / 'p17-probe'
    probe.write_bytes(Path(__file__).with_name('fake_p17_probe.py').read_bytes())
    probe.chmod(0o755)
    def collect(label, reader):
        output = tmp_path / f'p17-{label}'
        args = [sys.executable, str(CODE/'p17_media_qualification.py'),
                '--probe', str(probe), '--reader-sox', str(sox),
                '--reader-reference', str(ref),
                '--media-root', str(media), '--results', str(output),
                '--expected-dsd512-tracks', '2', '--require-media',
                '--independent-reader-evidence', str(reader)]
        cp = subprocess.run(args, capture_output=True, text=True, timeout=30)
        assert cp.returncode == 0, cp.stderr
        return json.loads((output / 'commercial-decode-evidence.json').read_text())

    report_path = results / 'independent-reader-evidence.json'
    good = collect('good', report_path)
    assert good['full_file_functional_gate'] == 'PASS'
    assert good['independent_reader_and_audio_reference_gate'] == 'PASS'
    q = good['decoder_profile_qualified']
    assert q['decode.mastering.v1.dsd512']
    assert q['decode.mastering.v2.dsd512']
    assert q['decode.wideband.v1.dsd512']
    assert not q['decode.wideband.v2.dsd512']
    assert not any(v for k, v in q.items() if k.endswith('.dsd1024'))
    missing = collect('missing', tmp_path / 'reader-missing.json')
    assert missing['independent_reader_and_audio_reference_gate'] == 'UNRUN'
    assert not any(missing['decoder_profile_qualified'].values())

    legacy = tmp_path / 'reader-v1.json'
    r = json.loads(report_path.read_text())
    r['schema'] = 'P21/independent-reader-evidence/1'
    legacy.write_text(json.dumps(r))
    invalid = collect('invalid', legacy)
    assert invalid['independent_reader_and_audio_reference_gate'] == 'INVALID'
    assert not any(invalid['decoder_profile_qualified'].values())


@pytest.mark.slow
def test_negative_control_decode_failure_fails_run(tmp_path):
    proc, _, _, _, results = run_gate(tmp_path, {'FAKE_CONTROL_ERROR': '1'}, with_self=False)
    assert proc.returncode != 0
    report = json.loads((results / 'independent-reader-evidence.json').read_text())
    assert report['independent_reader_and_audio_reference_gate'] == 'FAIL'
    assert any('negative_control=9' in reason for path in (results/'cases').glob('*.json')
               for reason in json.loads(path.read_text())['failure_reasons'])

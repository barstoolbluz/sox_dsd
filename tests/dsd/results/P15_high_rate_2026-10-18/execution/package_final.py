#!/usr/bin/env python3
"""Package the completed high-rate work without rewriting inherited payloads.

The original submitted tar is the authoritative source of every unchanged
inherited file. Only the four validated integration preimages may be replaced.
New evidence and source files are copied from the completed working tree.
This is a delivery utility, not part of the numerical proof.
"""
from __future__ import annotations

import argparse
import copy
import gzip
from hashlib import sha256
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile


INPUT_SHA256 = 'd0bd8a65a149f4267a4d33bb8763aa56faa937ae78009a9796a9b31bcd2e04c4'
EVIDENCE = Path('tests/dsd/results/P15_high_rate_2026-10-18')
MODIFIED = {
    'tests/dsd/p15_src_branch_bound.py',
    'tests/dsd/p15_src_continuum_bounds.py',
    'tests/dsd/p15_src_stagewise_continuum.py',
    'tests/dsd/test_p15_prover_second_pass.py',
}


def digest_file(path):
    h = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def is_cache(relative):
    path = PurePosixPath(relative)
    return '__pycache__' in path.parts or path.suffix in ('.pyc', '.pyo')


def add_bytes(archive, name, payload, mode=0o644):
    entry = tarfile.TarInfo(name)
    entry.size = len(payload)
    entry.mode = mode
    entry.mtime = 0
    archive.addfile(entry, io.BytesIO(payload))


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')


def working_inventory(root):
    files = {}
    for path in sorted(root.rglob('*')):
        relative = str(path.relative_to(root))
        if is_cache(relative):
            continue
        if path.is_symlink():
            raise ValueError('unexpected working-tree symbolic link: ' + relative)
        if path.is_file():
            files[relative] = digest_file(path)
    return files


def verify_manifest(directory, basename_only=False, manifest_name='SHA256SUMS', payload_root=None):
    payload_root = directory if payload_root is None else payload_root
    entries = {}
    for line in (directory / manifest_name).read_text().splitlines():
        expected, name = line.split('  ', 1)
        relative = PurePosixPath(name)
        if (relative.is_absolute() or '..' in relative.parts or name in entries
                or (basename_only and relative.name != name)
                or len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected)):
            raise ValueError('invalid delivery manifest entry: ' + name)
        if digest_file(payload_root / name) != expected:
            raise ValueError('delivery manifest mismatch: ' + name)
        entries[name] = expected
    if not entries:
        raise ValueError('empty delivery manifest')
    return entries


def verify_completed_reports(root, evidence, coverage, aggregation_config):
    report_dir, census_dir = evidence / 'coverage_final_01', evidence / 'census_final_01'
    report_manifest = verify_manifest(report_dir, basename_only=True)
    census_manifest = verify_manifest(census_dir, basename_only=True)
    required = {'SUMMARY.json', 'CELL_COVERAGE.json', 'COMPLETE_CELL_WITNESSES.json',
        'MATCHED_BENCHMARKS.json', 'BOUNDARY_COVERAGE.json',
        'STRICT_NORMATIVE_READJUDICATION.json', 'CLASSIFICATION.jsonl', 'COVERAGE_REPORT.md'}
    if set(report_manifest) != required or 'summary.json' not in census_manifest:
        raise ValueError('incomplete final report manifest')
    census = json.loads((census_dir / 'summary.json').read_text())
    adjudication = EVIDENCE / 'complete_cell/normative_readjudication_02/verification.json'
    if (coverage['report_code_sha256'] != digest_file(root / 'tests/dsd/p15_high_rate_coverage_report.py')
            or coverage['census_summary_sha256'] != digest_file(census_dir / 'summary.json')
            or census['census_code_sha256'] != digest_file(root / 'tests/dsd/p15_high_rate_census.py')
            or coverage['strict_readjudication']['path'] != str(adjudication)
            or coverage['strict_readjudication']['sha256'] != digest_file(root / adjudication)
            or coverage['source_binding'] != {'source': census['source_identity'], 'design': census['design_sha256']}):
        raise ValueError('final report code/source/readjudication identity mismatch')
    for name, expected in coverage['source_binding']['source'].items():
        if digest_file(root / name) != expected:
            raise ValueError('final report source pin mismatch: ' + name)
    if digest_file(root / 'docs/dsd/DSD_DESIGN.md') != coverage['source_binding']['design']:
        raise ValueError('final report normative design mismatch')
    config = json.loads(aggregation_config.read_text())
    labels = {m['label'] for m in config['measurements']}
    if (set(coverage['plans']) != labels or set(coverage['proof_snapshots']) != labels
            or set(coverage['candidate_labels']) != {m['label'] for m in config['measurements'] if m['role'] == 'candidate'}):
        raise ValueError('final report measurement label mismatch')
    for measurement in config['measurements']:
        label, plan_path = measurement['label'], measurement['plan']
        plan = json.loads((root / plan_path).read_text())
        reported = coverage['plans'][label]
        if (reported['plan'] != plan_path or reported['plan_sha256'] != digest_file(root / plan_path)
                or reported['expected'] != len(plan['job_indices'])
                or reported['observed'] != len(plan['job_indices'])
                or reported['missing_work_sha256'] or reported['unexpected_work_sha256']):
            raise ValueError('final report plan mismatch: ' + label)
        snapshot_path = measurement['proof_snapshot']
        identity_path = root / snapshot_path / 'IDENTITY.json'
        snapshot = coverage['proof_snapshots'][label]
        identity = json.loads(identity_path.read_text())
        if (snapshot['directory'] != snapshot_path or snapshot['identity_sha256'] != digest_file(identity_path)
                or snapshot['prover_code_sha256'] != identity['prover_code_sha256']):
            raise ValueError('final report proof snapshot mismatch: ' + label)
    independent = {
        'dsd256.mastering.pcm384000': ('master256_384000_v1_complete', 232),
        'dsd256.wideband.pcm384000': ('wide256_384000_final_complete', 334),
        'dsd256.mastering_v2.pcm384000': ('mastering_v2_256_384000_final_complete', 258),
        'dsd256.wideband.pcm192000': ('wide256_192000_final_complete', 188),
    }
    for cell in coverage['complete_candidate_cells']:
        name, count = independent[cell]
        directory = evidence / 'complete_cell' / name
        verify_manifest(directory)
        verify_manifest(directory, manifest_name='receipt_sha256.txt', payload_root=root)
        verify_manifest(directory, manifest_name='all_attempt_sha256.txt', payload_root=root)
        doc = json.loads((directory / 'verification.json').read_text())
        if (doc['status'] != 'COMPLETE_CANONICAL_RECEIPT_COVERAGE_VERIFIED'
                or doc['cell_id'] != cell or doc['expected_intervals'] != count
                or doc['verified_intervals'] != count or doc['invalid_receipts'] or doc['missing_intervals']):
            raise ValueError('independent complete-cell verification mismatch: ' + cell)


class HashingReader:
    def __init__(self, stream):
        self.stream = stream
        self.hash = sha256()

    def read(self, size=-1):
        block = self.stream.read(size)
        self.hash.update(block)
        return block


def inspect_archive(path):
    files, links = {}, {}
    with tarfile.open(path, 'r:gz') as archive:
        names = set()
        for entry in archive:
            if entry.name in names:
                raise ValueError('duplicate archive member: ' + entry.name)
            names.add(entry.name)
            if entry.isfile():
                reader = HashingReader(archive.extractfile(entry))
                while reader.read(1024 * 1024):
                    pass
                files[entry.name] = reader.hash.hexdigest()
            elif entry.issym() or entry.islnk():
                links[entry.name] = dict(type=entry.type.decode('ascii'), target=entry.linkname)
    return files, links


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--aggregation-config', type=Path,
                        help='Versioned final aggregation config; defaults to the initial config')
    parser.add_argument('--cpu', type=int, default=7)
    args = parser.parse_args()
    if args.cpu not in os.sched_getaffinity(0):
        raise ValueError('requested packaging CPU unavailable')
    os.sched_setaffinity(0, {args.cpu})
    os.nice(15)
    root = args.root.resolve(strict=True)
    original = args.original.resolve(strict=True)
    output = args.output.resolve()
    if output == root or root in output.parents:
        raise ValueError('output must be outside the source repository')
    output.mkdir(parents=True, exist_ok=False)
    if digest_file(original) != INPUT_SHA256:
        raise ValueError('submitted baseline archive digest mismatch')
    evidence = root / EVIDENCE
    integration = evidence / 'integration'
    aggregation_config = (args.aggregation_config or
        evidence / 'execution/FINAL_AGGREGATION_CONFIG.json').resolve(strict=True)
    if not aggregation_config.is_file() or not aggregation_config.is_relative_to(evidence):
        raise ValueError('aggregation config must be a packaged evidence file')
    if not (evidence / 'P15_high_rate_continuation_2026-10-18.md').is_file():
        raise ValueError('completed continuation document missing')
    if not (evidence / 'coverage_final_01/SUMMARY.json').is_file():
        raise ValueError('completed coverage report missing')
    coverage = json.loads((evidence / 'coverage_final_01/SUMMARY.json').read_text())
    if coverage.get('status') != 'SELECTED_PLANS_RECORDED':
        raise ValueError('coverage plans are incomplete')
    if not (evidence / 'complete_cell/normative_readjudication_02/verification.json').is_file():
        raise ValueError('final exact-normative readjudication missing')
    preflight_command = [sys.executable, str(evidence / 'execution/aggregate_final.py'),
        '--config', str(aggregation_config),
        '--readjudication', str(evidence / 'complete_cell/normative_readjudication_02/verification.json'),
        '--check-only']
    preflight = subprocess.run(preflight_command, cwd=root, capture_output=True,
                               text=True, timeout=120, check=True)
    verify_completed_reports(root, evidence, coverage, aggregation_config)

    # Freeze the complete non-cache working payload inventory before writing.
    working = working_inventory(root)
    changed = json.loads((integration / 'CHANGED_FILES.json').read_text())
    if changed.get('baseline_archive_sha256') != INPUT_SHA256:
        raise ValueError('integration baseline identity mismatch')
    integration_files = {item['path']: item for item in changed['files']}
    application = json.loads((integration / 'applicability/RESULT.json').read_text())
    patch_hash = digest_file(integration / 'P15_high_rate.patch')
    if (patch_hash != changed['patch_sha256'] or patch_hash != application['patch_sha256']
            or application.get('status') != 'PASS' or not application.get('exact_postimages')
            or not application.get('baseline_unchanged')
            or application.get('specification_sha256') != digest_file(integration / 'CHANGED_FILES.json')
            or application.get('postimage_sha256') != {
                name: item['candidate_sha256'] for name, item in integration_files.items()}):
        raise ValueError('integration patch/application evidence mismatch')
    if {name for name, item in integration_files.items()
            if item['status'] == 'MODIFIED'} != MODIFIED:
        raise ValueError('integration modification set mismatch')
    for relative, item in integration_files.items():
        if working.get(relative) != item['candidate_sha256']:
            raise ValueError('integration postimage differs from source: ' + relative)
    final_proof = json.loads((evidence / 'reference_high_rate_final_code/IDENTITY.json').read_text())
    for name, expected in final_proof['prover_code_sha256'].items():
        if working.get('tests/dsd/' + name) != expected:
            raise ValueError('final source differs from frozen proof map: ' + name)
    original_names, inherited, replacements, preserved_links = set(), {}, {}, {}
    source_files = {}
    archive_path = output / 'sox_ng_P15_high_rate_FULL_SOURCE_2026-10-18.tar.gz'
    with archive_path.open('xb') as raw, gzip.GzipFile(fileobj=raw, mode='wb',
             filename='', mtime=0, compresslevel=6) as compressed, \
             tarfile.open(fileobj=compressed, mode='w') as target, \
             tarfile.open(original, 'r:gz') as source:
        for entry in source:
            parts = PurePosixPath(entry.name).parts
            if not parts or parts[0] != 'sox_ng' or '..' in parts:
                raise ValueError('unexpected original archive path')
            relative = str(PurePosixPath(*parts[1:])) if len(parts) > 1 else '.'
            if relative in original_names:
                raise ValueError('duplicate original archive member: ' + relative)
            original_names.add(relative)
            if entry.isfile():
                reader = HashingReader(source.extractfile(entry))
                if relative in MODIFIED:
                    while reader.read(1024 * 1024):
                        pass
                    payload = (root / relative).read_bytes()
                    replacement = copy.copy(entry)
                    replacement.size = len(payload)
                    replacement.mtime = 0
                    target.addfile(replacement, io.BytesIO(payload))
                    final_hash = sha256(payload).hexdigest()
                    if final_hash != working[relative]:
                        raise ValueError('source changed while packaging: ' + relative)
                    replacements[relative] = dict(before=reader.hash.hexdigest(), after=final_hash)
                    if reader.hash.hexdigest() != integration_files[relative]['baseline_sha256']:
                        raise ValueError('integration preimage differs from original: ' + relative)
                else:
                    target.addfile(entry, reader)
                    final_hash = reader.hash.hexdigest()
                    if not is_cache(relative) and working.get(relative) != final_hash:
                        raise ValueError('unexpected inherited working modification: ' + relative)
                inherited[relative] = reader.hash.hexdigest()
                source_files[entry.name] = final_hash
            else:
                target.addfile(entry)
                if entry.issym() or entry.islnk():
                    preserved_links[entry.name] = dict(type=entry.type.decode('ascii'), target=entry.linkname)
        if set(replacements) != MODIFIED:
            raise ValueError('unexpected replacement file set')
        additions = sorted(set(working) - original_names)
        non_evidence_additions = {name for name in additions
                                 if not name.startswith(str(EVIDENCE) + '/')}
        expected_additions = {name for name, item in integration_files.items()
                              if item['status'] == 'ADDED'}
        if non_evidence_additions != expected_additions:
            raise ValueError('unexpected non-evidence source additions')
        for relative in additions:
            payload = (root / relative).read_bytes()
            if sha256(payload).hexdigest() != working[relative]:
                raise ValueError('new file changed while packaging: ' + relative)
            name = 'sox_ng/' + relative
            add_bytes(target, name, payload, (root / relative).stat().st_mode & 0o777)
            source_files[name] = working[relative]
        source_manifest = dict(
            schema='P15/high-rate-source-delivery/1', original_archive_sha256=INPUT_SHA256,
            unchanged_inherited_files=len(inherited) - len(replacements),
            modified_inherited_files=replacements, added_files=additions,
            original_file_sha256=inherited, final_file_sha256=source_files,
            preserved_links=preserved_links,
            manifest_self_hash_omitted=True, qualified_release=False)
        payload = json_bytes(source_manifest)
        manifest_name = 'sox_ng/P15_HIGH_RATE_SOURCE_MANIFEST.json'
        add_bytes(target, manifest_name, payload)
        source_files[manifest_name] = sha256(payload).hexdigest()
        (output / 'P15_high_rate_source_manifest_2026-10-18.json').write_bytes(payload)

    # Re-read the completed archive independently; compare every payload/link.
    actual_files, actual_links = inspect_archive(archive_path)
    if actual_files != source_files or actual_links != preserved_links:
        raise ValueError('complete archive payload verification failed')

    compact_files = {}
    for directory, prefix in ((integration, 'integration'), (evidence, 'evidence/' + str(EVIDENCE))):
        for path in sorted(directory.rglob('*')):
            if path.is_file() and not path.is_symlink() and not is_cache(str(path.relative_to(directory))):
                name = prefix + '/' + str(path.relative_to(directory))
                payload = path.read_bytes()
                if sha256(payload).hexdigest() != working[str(path.relative_to(root))]:
                    raise ValueError('evidence changed after full source packaging')
                compact_files[name] = payload
    compact_files['README.md'] = (
        '# P15 high-rate implementation bundle\n\n'
        'Apply `integration/P15_high_rate.patch` to an untouched extraction of the submitted '
        'third-pass source, then copy the new directory under `evidence/tests/dsd/results/` '
        'to the corresponding previously absent repository path. Read `integration/README.md` '
        'for exact preimage/postimage checks and reproduction commands.\n\n'
        'The complete methods, coverage, benchmarks, raw receipts, independent verification, '
        'and continuation documents are under `evidence/tests/dsd/results/P15_high_rate_2026-10-18/`. '
        'P15 remains BLOCKED. This bundle changes no production DSP source or release policy.\n').encode()
    compact_hashes = {name: sha256(payload).hexdigest() for name, payload in compact_files.items()}
    compact_files['SHA256SUMS'] = ''.join(
        f'{digest}  {name}\n' for name, digest in sorted(compact_hashes.items())).encode()
    compact_hashes['SHA256SUMS'] = sha256(compact_files['SHA256SUMS']).hexdigest()
    compact_path = output / 'sox_ng_P15_high_rate_IMPLEMENTATION_2026-10-18.tar.gz'
    with compact_path.open('xb') as raw, gzip.GzipFile(fileobj=raw, mode='wb',
             filename='', mtime=0, compresslevel=6) as compressed, \
             tarfile.open(fileobj=compressed, mode='w') as target:
        for name, payload in sorted(compact_files.items()):
            add_bytes(target, 'P15_high_rate_implementation/' + name, payload)
    compact_actual, compact_links = inspect_archive(compact_path)
    expected_compact = {'P15_high_rate_implementation/' + name: digest
                        for name, digest in compact_hashes.items()}
    if compact_actual != expected_compact or compact_links:
        raise ValueError('compact archive verification failed')
    if working_inventory(root) != working:
        raise ValueError('source/evidence payload inventory changed while packaging')
    validation = dict(
        schema='P15/high-rate-delivery-validation/1', qualified_release=False,
        full_source=dict(path=archive_path.name, sha256=digest_file(archive_path),
                         bytes=archive_path.stat().st_size, files_verified=len(actual_files)),
        implementation=dict(path=compact_path.name, sha256=digest_file(compact_path),
                            bytes=compact_path.stat().st_size, files_verified=len(compact_actual)),
        unchanged_inherited_payloads=len(inherited) - len(replacements),
        modified_inherited_files=replacements, added_files=len(additions),
        archive_payloads_verified=True, original_links_preserved=True,
        completed_report_manifests_and_identities_verified=True,
        independent_complete_cell_manifests_verified=True,
        source_evidence_inventory_unchanged_during_packaging=True,
        aggregation_config_path=str(aggregation_config.relative_to(root)),
        aggregation_config_sha256=digest_file(aggregation_config),
        coverage_readjudication_preflight=dict(command=preflight_command,
            stdout=preflight.stdout, stderr=preflight.stderr, returncode=preflight.returncode),
        code_patch_application_evidence=str(EVIDENCE / 'integration/applicability/RESULT.json'))
    (output / 'P15_high_rate_delivery_validation_2026-10-18.json').write_bytes(json_bytes(validation))
    print(json.dumps(validation, indent=2, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()

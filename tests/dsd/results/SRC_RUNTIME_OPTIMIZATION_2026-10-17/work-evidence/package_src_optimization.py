#!/usr/bin/env python3
"""Audit and package the completed SRC optimization (run only after review).

Usage: python3 work-evidence/package_src_optimization.py --output /absolute/new-directory
The output directory must be empty and outside both sox_ng and work-evidence.
This writes only additive source evidence/manifests and the chosen delivery directory.
"""
import argparse
from collections import defaultdict
import difflib
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile


DATE = '2026-10-17'
STEM = 'SRC_RUNTIME_OPTIMIZATION'
EVIDENCE = f'{STEM}_{DATE}'
PRODUCTION = f'{STEM}_PRODUCTION_{DATE}.patch'
SUPPORT = f'{STEM}_SUPPORT_{DATE}.patch'
FULL_MANIFEST = f'SHA256SUMS_{STEM}_{DATE}'
EXTERNAL_MANIFEST = f'{STEM}_SHA256SUMS_{DATE}.txt'
FINAL_INDEX = 'FINAL_PACKAGING_INDEX.md'
HEADER = 'src/rate_poly_fir0.h'
FINAL_HEADER_SHA = 'c1626c26f7ba8d64f2b69752906948b527923745313d13c41f78c47046552591'
PRODUCTION_SHA = '354f6c0c824587c9a5767e544bdd139105541810b5fa45cea5de78dbb05d81e8'
NEW_TEMPORARY = ('tests/dsd/results/P15_REMAINING_PROOF_2026-10-16/'
                 'ps-matched-comparator/.control-v2-352800.wav.igYW4t')
WORK_EXCLUDED_SUFFIXES = {'.s32', '.dsf', '.wav', '.pyc', '.pyo', '.o', '.obj', '.a'}
DOCUMENTS = [f'docs/dsd/{STEM}_{DATE}.md',
             f'docs/dsd/{STEM}_PROOF_{DATE}.md',
             f'docs/dsd/{STEM}_REPRODUCE_{DATE}.md',
             f'docs/dsd/{STEM}_P15_ASSESSMENT_{DATE}.md',
             f'docs/dsd/handoffs/{STEM}_RESUME_{DATE}.md']
SUPPORT_FILES = ['tests/dsd/bench_src_optimization.py',
                 'tests/dsd/profile_src_optimization.py',
                 'tests/dsd/compare_src_optimization_operators.py',
                 'tests/dsd/summarize_src_optimization.py',
                 'tests/dsd/test_src_optimization.c',
                 'tests/dsd/reference/src_optimization/rate_poly_fir0.h',
                 'tests/dsd/reference/src_optimization/rate_half_fir.h',
                 'tests/dsd/reference/src_optimization/ORIGIN.json',
                 f'tests/dsd/results/{EVIDENCE}/agent_build/validate_existing.py',
                 'tools/build_src_optimization.py', *DOCUMENTS]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def announce(message):
    print(message, flush=True)


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def copy_verified(source, destination):
    require(source.resolve() != destination.resolve(), 'refusing a self-copy')
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    value = digest(source)
    require(digest(destination) == value, f'copy verification failed: {destination}')
    return value


def audit_originals(workspace, source, audit_path):
    audit = json.loads(audit_path.read_text())
    require(audit['original_regular_files'] == len(audit['files']) == 15498,
            'unexpected frozen original-file count')
    original, modified = {}, []
    for record in audit['files']:
        name = PurePosixPath(record['path'])
        require(not name.is_absolute() and '..' not in name.parts and name.parts[0] == source.name,
                'unsafe or unexpected original path')
        relative = PurePosixPath(*name.parts[1:]).as_posix()
        require(relative not in original, 'duplicate frozen original path')
        path = source / relative
        require(path.is_file() and not path.is_symlink(), f'original regular file missing/replaced: {relative}')
        original[relative] = record['original_sha256']
        current = digest(path)
        if current != record['original_sha256']:
            modified.append(dict(path=relative, original_sha256=record['original_sha256'], sha256=current))
    require(len(modified) == 1 and modified[0]['path'] == HEADER and
            modified[0]['sha256'] == FINAL_HEADER_SHA, 'unexpected original-source modifications')
    archive = workspace / audit['archive']
    require(digest(archive) == audit['archive_sha256'], 'original attached archive identity mismatch')
    directories, regular = set(), set()
    with tarfile.open(archive, 'r:*') as stream:
        for member in stream:
            name = PurePosixPath(member.name)
            if not name.parts:
                continue
            require(not name.is_absolute() and '..' not in name.parts and name.parts[0] == source.name,
                    'unexpected original archive namespace')
            relative = PurePosixPath(*name.parts[1:]).as_posix()
            if member.isdir():
                directories.add(relative)
                require((source / relative).is_dir() and not (source / relative).is_symlink(),
                        f'original directory missing/replaced: {relative}')
            elif member.isfile():
                require(relative not in regular, 'duplicate original archive regular file')
                regular.add(relative)
    require(regular == set(original), 'original archive and audit file lists differ')
    receipt = dict(status='PASS', original_regular_files=15498, missing=[], modified=modified,
                   original_directories=len(directories), original_archive_sha256=audit['archive_sha256'],
                   frozen_audit_sha256=digest(audit_path),
                   scope='All original regular files rehashed; only the final production header differs. Original directories remain present.')
    return original, directories, receipt


def stage_work(work, destination):
    def temporary(relative):
        return any(part.startswith('.') for part in relative.parts)
    def excluded(relative):
        return temporary(relative) or '__pycache__' in relative.parts or relative.suffix.lower() in WORK_EXCLUDED_SUFFIXES
    copied, skipped, removed = [], [], []
    transient = dict(skipped_files=0, skipped_bytes=0, removed_staging_files=0, removed_staging_bytes=0)
    destination.mkdir(parents=True, exist_ok=True)
    # Remove only excluded generated files from an earlier additive staging copy.
    # Their originals outside the source repository remain untouched.
    for path in sorted(destination.rglob('*')):
        relative = path.relative_to(destination)
        if (path.is_file() or path.is_symlink()) and excluded(relative):
            if temporary(relative):
                transient['removed_staging_files'] += 1
                transient['removed_staging_bytes'] += path.lstat().st_size
            else:
                removed.append(relative.as_posix())
            path.unlink()
    for path in sorted(work.rglob('*')):
        relative = path.relative_to(work)
        if excluded(relative):
            if path.is_file():
                if temporary(relative):
                    transient['skipped_files'] += 1
                    transient['skipped_bytes'] += path.stat().st_size
                else:
                    skipped.append(relative.as_posix())
            continue
        require(not path.is_symlink(), f'work-evidence contains a symlink; review before staging: {relative}')
        if path.is_file():
            value = copy_verified(path, destination / relative)
            copied.append(dict(path=relative.as_posix(), bytes=path.stat().st_size, sha256=value))
    return dict(copied=copied, skipped_generated=skipped, removed_generated_staging_copies=removed,
                temporary_work_payloads=transient)


def make_support_patch(source, paths, destination, original, output):
    paths = sorted(set(paths))
    expected, chunks = {}, []
    for relative in paths:
        require(relative not in original, 'support patch would touch an original file: ' + relative)
        require(re.fullmatch(r'[A-Za-z0-9_./-]+', relative) is not None, 'unsupported patch path')
        path = source / relative
        require(path.is_file() and not path.is_symlink(), 'support input missing: ' + relative)
        raw = path.read_bytes()
        require(raw, 'empty support input: ' + relative)
        executable = bool(path.stat().st_mode & 0o111)
        expected[relative] = dict(sha256=hashlib.sha256(raw).hexdigest(), executable=executable)
        chunks.extend([f'diff --git a/{relative} b/{relative}\n',
                       f'new file mode {"100755" if executable else "100644"}\n'])
        for line in difflib.unified_diff([], raw.decode('utf-8').splitlines(keepends=True),
                                         fromfile='/dev/null', tofile='b/' + relative):
            chunks.append(line if line.endswith('\n') else line + '\n\\ No newline at end of file\n')
    destination.write_text(''.join(chunks))
    require(shutil.which('git'), 'git is required to verify the additive support patch')
    commands = []
    # Keep verification outside the workspace Git repository and clear inherited
    # repository routing, so git apply operates on this empty directory alone.
    with tempfile.TemporaryDirectory(prefix='src-opt-support-', dir='/tmp') as temporary:
        environment = os.environ.copy()
        for variable in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'):
            environment.pop(variable, None)
        environment['GIT_CEILING_DIRECTORIES'] = '/tmp'
        for flags in (['--check'], []):
            command = ['git', 'apply', *flags, str(destination)]
            result = subprocess.run(command, cwd=temporary, env=environment, capture_output=True, text=True)
            commands.append(dict(command=command, exit=result.returncode, stdout=result.stdout, stderr=result.stderr))
            require(result.returncode == 0, 'support patch application failed: ' + result.stderr)
        actual = {p.relative_to(temporary).as_posix() for p in Path(temporary).rglob('*') if p.is_file()}
        require(actual == set(expected), 'support patch created an unexpected file set')
        for relative, identity in expected.items():
            path = Path(temporary) / relative
            require(digest(path) == identity['sha256'], 'support patch byte mismatch: ' + relative)
            require(bool(path.stat().st_mode & 0o111) == identity['executable'], 'support patch mode mismatch')
    return dict(status='PASS', sha256=digest(destination), files=expected, commands=commands,
                scope='Applied in an empty temporary directory; every new file byte hash and executable bit matched.')


def tree_entries(root, excluded):
    result = {}
    for path in [root, *sorted(root.rglob('*'))]:
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        if excluded(relative):
            continue
        if stat.S_ISLNK(info.st_mode):
            result[relative] = dict(kind='symlink', target=os.readlink(path))
        elif stat.S_ISDIR(info.st_mode):
            result[relative] = dict(kind='directory')
        elif stat.S_ISREG(info.st_mode):
            result[relative] = dict(kind='file', bytes=info.st_size)
        else:
            raise RuntimeError('unsupported filesystem entry: ' + str(path))
    return result


def write_manifest(path, values):
    # Standard sha256sum format. The known repository names do not require GNU escaping.
    require(all('\n' not in name and '\r' not in name and '\\' not in name for name in values),
            'a filename requires manifest escaping; review before packaging')
    path.write_text(''.join(f'{value}  {name}\n' for name, value in sorted(values.items())))


def read_manifest(path):
    values = {}
    for line in path.read_text().splitlines():
        value, name = line.split('  ', 1)
        require(re.fullmatch('[0-9a-f]{64}', value) and name not in values, 'malformed manifest')
        values[name] = value
    return values


def manifest_tree(root, manifest_name, excluded):
    entries = tree_entries(root, excluded)
    values = {name: digest(root / name) for name, entry in entries.items()
              if entry['kind'] == 'file' and name != manifest_name}
    manifest = root / manifest_name
    write_manifest(manifest, values)
    require(read_manifest(manifest) == values, 'manifest round-trip mismatch')
    entries[manifest_name] = dict(kind='file', bytes=manifest.stat().st_size)
    return entries, values


def archive_and_verify(root, archive, entries, manifest_name, level):
    temporary = archive.with_name(archive.name + '.partial')
    with temporary.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, compresslevel=level, mtime=0) as compressed:
            with tarfile.open(mode='w|', fileobj=compressed, format=tarfile.PAX_FORMAT, dereference=False) as output:
                for name in sorted(entries, key=lambda name: (len(PurePosixPath(name).parts), name)):
                    arcname = root.name if name == '.' else root.name + '/' + name
                    output.add(root / name, arcname=arcname, recursive=False)
    values = read_manifest(root / manifest_name)
    values[manifest_name] = digest(root / manifest_name)
    seen, hardlinks = set(), 0
    with tarfile.open(temporary, 'r:gz') as stream:
        for member in stream:
            name = PurePosixPath(member.name)
            require(name.parts and name.parts[0] == root.name and '..' not in name.parts and not name.is_absolute(),
                    'unexpected archive namespace')
            relative = PurePosixPath(*name.parts[1:]).as_posix()
            require(relative in entries and relative not in seen, 'extra or duplicate archive entry')
            seen.add(relative)
            expected = entries[relative]
            if member.isfile() or member.islnk():
                require(expected['kind'] == 'file', 'archive entry type mismatch')
                value, size = hashlib.sha256(), 0
                with stream.extractfile(member) as contents:
                    for block in iter(lambda: contents.read(1024 * 1024), b''):
                        value.update(block)
                        size += len(block)
                require(value.hexdigest() == values[relative] and size == expected['bytes'],
                        'archived bytes differ from manifest: ' + relative)
                hardlinks += int(member.islnk())
            elif member.isdir():
                require(expected['kind'] == 'directory', 'archive directory mismatch')
            elif member.issym():
                require(expected['kind'] == 'symlink' and member.linkname == expected['target'],
                        'archive symlink mismatch')
            else:
                raise RuntimeError('unsupported archive member type')
    require(seen == set(entries), 'archive is missing entries')
    temporary.replace(archive)
    return dict(status='PASS', bytes=archive.stat().st_size, sha256=digest(archive), entries=len(entries),
                regular_files=len(values), directories=sum(e['kind'] == 'directory' for e in entries.values()),
                symlinks=sum(e['kind'] == 'symlink' for e in entries.values()), hardlinks_verified=hardlinks,
                manifest=manifest_name, manifest_sha256=digest(root / manifest_name),
                scope='Every archive entry checked; every regular-file payload hashed against the internal manifest, including a separate hash for the manifest itself.')


def final_index(evidence, staged, workspace, excluded):
    groups = defaultdict(lambda: [0, 0])
    for name, entry in tree_entries(evidence, excluded).items():
        if entry['kind'] == 'file' and name not in (FINAL_INDEX, 'SHA256SUMS'):
            group = name.split('/', 1)[0] if '/' in name else '(root files)'
            groups[group][0] += 1
            groups[group][1] += entry['bytes']
    rows = '\n'.join(f'| `{name}` | {count:,} | {size:,} |' for name, (count, size) in sorted(groups.items()))
    (evidence / FINAL_INDEX).write_text(
        '# Final packaging index\n\n'
        'This index describes the final staged payload. The earlier `BUILD_EVIDENCE.md` and '
        '`agent_build/STAGED_MANIFEST.json` remain unchanged as historical staging records.\n\n'
        f'Original workspace prefix: `{workspace}/`. Staged directory names retain their workspace suffixes. '
        'In particular, original `work-evidence/` paths map to `work-evidence/` here. JSON paths and commands '
        'retain their original spelling; derived primary observations resolve logs against their explicit parent directory.\n\n'
        f'Final work-evidence copy: {len(staged["copied"]):,} files, '
        f'{sum(item["bytes"] for item in staged["copied"]):,} bytes. '
        'Temporary work payloads, generated audio, Python cache files and object/archive intermediates were omitted from that new copy. '
        'Original files in the attached repository, including original audio and build artifacts, remain in the full source archive.\n\n'
        '| Staged group | Regular files | Bytes |\n|---|---:|---:|\n' + rows + '\n\n'
        'These group counts exclude this final index and `SHA256SUMS`. The standard `SHA256SUMS` file binds '
        'the final evidence payload while excluding itself. The full repository has a separate internal manifest, '
        'which includes the evidence manifest and excludes only itself. External archive/patch/report hashes are '
        'recorded outside both archives, avoiding circular hashes.\n\n'
        'The support patch contains only new tests, helpers, documentation, references and selected reproducibility '
        'scripts/corpora. Its empty-directory application and byte comparison are recorded in '
        '`support-patch-verification.json`. The final frozen-source audit is '
        '`FROZEN_SOURCE_PACKAGING_AUDIT.json`. The primary incomplete receipt, extracted 48-case subset, recovery '
        'case, failed control receipt, revised controls and diagnostic repeats remain identifiable separately.\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compression-level', type=int, choices=range(1, 10), default=6)
    args = parser.parse_args()
    workspace, output = args.workspace.resolve(), args.output.resolve()
    source, work = workspace / 'sox_ng', workspace / 'work-evidence'
    evidence = source / 'tests/dsd/results' / EVIDENCE
    require(not output.is_relative_to(source) and not output.is_relative_to(work), 'output would cause recursive packaging')
    require(not output.exists() or output.is_dir() and not any(output.iterdir()), 'output directory must be empty')
    for relative in SUPPORT_FILES:
        require((source / relative).is_file(), 'required final source/document missing: ' + relative)
    for relative in DOCUMENTS:
        require(not re.search(r'\{\{[A-Z_]+\}\}', (source / relative).read_text()), 'unfilled final-document placeholder')
    summary_path, tables_path = evidence / 'benchmark-summary.json', evidence / 'BENCHMARK_TABLES.md'
    summary = json.loads(summary_path.read_text())
    require(summary['status'] == 'PASS' and summary['schema'] == 'sox/src-runtime-optimization-summary/1',
            'completed consolidated summary required')
    require(digest(summary_path) in tables_path.read_text(), 'tables are not bound to the current summary')
    require(digest(workspace / PRODUCTION) == PRODUCTION_SHA, 'verified production patch changed')
    announce('Auditing the frozen original files and original archive directories.')
    original, original_dirs, audit = audit_originals(workspace, source, work / 'frozen-archive-audit.json')
    require(NEW_TEMPORARY not in original and FULL_MANIFEST not in original, 'an exclusion/manifest conflicts with an original file')
    output.mkdir(parents=True, exist_ok=True)
    announce('Staging final work-evidence; retained original measurements are not modified.')
    staged = stage_work(work, evidence / 'work-evidence')
    for record in summary['measurements']:
        path = Path(record['path'])
        path = path if path.is_absolute() else workspace / path
        require(path.is_relative_to(workspace), 'summary measurement lies outside the recorded workspace')
        require(digest(path) == record['sha256'], 'summary refers to changed measurements')
        require(digest(evidence / path.relative_to(workspace)) == record['sha256'], 'staged measurement mismatch')
    evidence_relative = evidence.relative_to(source)
    support_paths = list(SUPPORT_FILES)
    for path in sorted(work.glob('*')):
        if path.is_file() and (path.suffix == '.py' or path.match('*cases*.json') or
                              path.name in {'repeat-policy.json', 'controls-corpus-revision.json',
                                            'continuity-control-rationale.json', 'primary-last-case.json'}):
            support_paths.append((evidence_relative / 'work-evidence' / path.name).as_posix())
    announce('Creating and applying the additive support patch in an empty temporary directory.')
    support = make_support_patch(source, support_paths, output / SUPPORT, original, output)
    copy_verified(workspace / PRODUCTION, output / PRODUCTION)
    copy_verified(workspace / PRODUCTION, evidence / PRODUCTION)
    copy_verified(output / SUPPORT, evidence / SUPPORT)
    write_json(evidence / 'support-patch-verification.json', support)
    write_json(evidence / 'FROZEN_SOURCE_PACKAGING_AUDIT.json', audit)
    for relative in DOCUMENTS:
        copy_verified(source / relative, evidence / 'documentation' / Path(relative).name)
    exports = [(source / DOCUMENTS[0], f'{STEM}_REPORT_{DATE}.md'),
                              (source / DOCUMENTS[1], Path(DOCUMENTS[1]).name),
                              (source / DOCUMENTS[2], Path(DOCUMENTS[2]).name),
                              (source / DOCUMENTS[3], Path(DOCUMENTS[3]).name),
                              (source / DOCUMENTS[-1], f'{STEM}_RESUME_{DATE}.md'),
                              (summary_path, f'{STEM}_BENCHMARKS_{DATE}.json'),
                              (tables_path, f'{STEM}_BENCHMARK_TABLES_{DATE}.md')]
    for source_path, name in exports:
        copy_verified(source_path, output / name)
    excluded_full = lambda name: name not in original and name not in original_dirs and (
        name.endswith('.pyc') or name == NEW_TEMPORARY or
        any(part.startswith('.') for part in PurePosixPath(name).parts))
    excluded_evidence = lambda name: excluded_full((evidence_relative / name).as_posix())
    final_index(evidence, staged, workspace, excluded_evidence)
    announce('Writing the evidence manifest, followed by the full source manifest.')
    evidence_entries, evidence_values = manifest_tree(evidence, 'SHA256SUMS', excluded_evidence)
    source_entries, source_values = manifest_tree(source, FULL_MANIFEST, excluded_full)
    require(original_dirs <= {name for name, entry in source_entries.items() if entry['kind'] == 'directory'},
            'an original directory would be omitted from the full archive')
    for name, value in original.items():
        require(source_values.get(name) == (FINAL_HEADER_SHA if name == HEADER else value),
                'original bytes changed after the source audit: ' + name)
    copy_verified(evidence / 'SHA256SUMS', output / 'EVIDENCE_SHA256SUMS')
    copy_verified(source / FULL_MANIFEST, output / 'SOURCE_SHA256SUMS')
    announce('Creating and verifying the complete source archive against its internal manifest.')
    full_name = f'sox_ng_SRC_RUNTIME_OPTIMIZED_FULL_{DATE}.tar.gz'
    full = archive_and_verify(source, output / full_name, source_entries, FULL_MANIFEST, args.compression_level)
    announce('Creating and verifying the separate evidence archive against its internal manifest.')
    evidence_name = f'{STEM}_EVIDENCE_{DATE}.tar.gz'
    evidence_archive = archive_and_verify(evidence, output / evidence_name, evidence_entries, 'SHA256SUMS', args.compression_level)
    require(digest(workspace / PRODUCTION) == PRODUCTION_SHA, 'production patch changed during packaging')
    artifact_names = {PRODUCTION, SUPPORT, 'EVIDENCE_SHA256SUMS', 'SOURCE_SHA256SUMS',
                      full_name, evidence_name, *(name for _, name in exports)}
    artifacts = {name: dict(bytes=(output / name).stat().st_size, sha256=digest(output / name))
                 for name in sorted(artifact_names)}
    verification = dict(schema='production-src/final-packaging/1', status='PASS', original_audit=audit,
                        support_patch=support, staging=staged,
                        archives={full_name: full, evidence_name: evidence_archive}, artifacts=artifacts,
                        full_source_exclusions='Only new temporary work payloads, new Python bytecode and the explicitly named new temporary control WAV; no original regular files or directories excluded.',
                        excluded_temporary_path=NEW_TEMPORARY,
                        hash_order='Support patch and audit/index -> evidence manifest -> full source manifest -> archives -> this verification -> external artifact manifest. Each manifest excludes itself.',
                        external_manifest=EXTERNAL_MANIFEST,
                        packaging_script_sha256=digest(Path(__file__)))
    write_json(output / 'packaging-verification.json', verification)
    write_manifest(output / EXTERNAL_MANIFEST,
                   {name: digest(output / name) for name in artifact_names | {'packaging-verification.json'}})
    for name, value in read_manifest(output / EXTERNAL_MANIFEST).items():
        require(digest(output / name) == value, 'external artifact hash mismatch')
    announce(json.dumps(dict(status='PASS', output=str(output), original_files_verified=15498,
                             source_files=full['regular_files'], evidence_files=evidence_archive['regular_files'],
                             external_files=len(read_manifest(output / EXTERNAL_MANIFEST)),
                             source_archive=full_name, evidence_archive=evidence_name), sort_keys=True))


if __name__ == '__main__':
    main()

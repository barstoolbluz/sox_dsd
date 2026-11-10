#!/usr/bin/env python3
"""Non-destructively rewrite ALL SoX DSD refs via Git fast-export/import.

Deletes exactly the project-record paths in repo_cleanup_policy.json from
EVERY commit tree. Does not rewrite executable source or upstream-owned paths.
The exported commit graph (including merges), annotated tags and branches is
preserved. Rewrites invalidate old object IDs and signed tags (signatures are
removed). Do NOT run this against a live repository or force-push without a
verified remote backup and a coordinated maintenance window.

The output bare repository initially uses the source as an object alternate;
create the self-contained bundle with --bundle, and verify it by fresh clone.
"""
from __future__ import annotations

import argparse
import codecs
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

POLICY = Path(__file__).with_name('repo_cleanup_policy.json')


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    res = subprocess.run(['git', *args], cwd=cwd, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, check=check)
    return res.stdout.strip()


def path_from_op(line: bytes) -> str | None:
    """Parse a path from an export file operation; fail on unsafe operations."""
    if line.startswith(b'M '):
        fields = line.rstrip(b'\n').split(b' ', 3)
        if len(fields) != 4:
            raise ValueError('invalid M file operation')
        raw_path = fields[3]
    elif line.startswith(b'D '):
        raw_path = line[2:].rstrip(b'\n')
    elif line.startswith((b'R ', b'C ', b'deleteall\n')):
        # Default fast-export emits M/D; do not silently lose an entry if Git
        # changes format or someone opts into rename detection.
        raise ValueError(f'unexpected file operation: {line[:100]!r}')
    else:
        return None
    if raw_path.startswith(b'"') and raw_path.endswith(b'"'):
        try:
            return codecs.decode(raw_path[1:-1].decode('ascii'), 'unicode_escape')
        except Exception as exc:
            raise ValueError('unable to decode Git-quoted path') from exc
    return raw_path.decode('utf-8', 'surrogateescape')


def selected(path: str, policy: dict) -> bool:
    return path in policy['exact_paths'] or any(path.startswith(p) for p in policy['prefixes'])


def copy_exact(input_stream, output_stream, amount: int) -> None:
    while amount:
        chunk = input_stream.read(min(amount, 1024 * 1024))
        if not chunk:
            raise EOFError('truncated fast-export stream')
        output_stream.write(chunk)
        amount -= len(chunk)


def read_refs(repo: Path) -> dict[str, str]:
    return dict(l.split(' ', 1) for l in git('for-each-ref',
                     '--format=%(refname) %(objectname)',
                     'refs/heads', 'refs/remotes', 'refs/tags', cwd=repo).splitlines())


def read_marks(path: Path) -> dict[str, str]:
    """Map Git fast-export/fast-import marks to concrete object IDs."""
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        mark, oid = line.split(' ', 1)
        if not mark.startswith(':') or not re.fullmatch(r'[a-f0-9]{40,64}', oid):
            raise RuntimeError(f'invalid Git mark in {path}: {line!r}')
        if mark in out:
            raise RuntimeError(f'duplicate Git mark: {mark}')
        out[mark] = oid
    return out


def verify_graph(source: Path, destination: Path) -> tuple[int, dict[str, str]]:
    """Independently compare mapped commit-parent edges, not just counts."""
    original_marks = read_marks(destination / 'export.marks')
    rewritten_marks = read_marks(destination / 'import.marks')
    if original_marks.keys() != rewritten_marks.keys():
        raise RuntimeError('export/import mark sets differ; graph verification impossible')
    oid_map = {old_oid: rewritten_marks[mark]
               for mark, old_oid in original_marks.items()}

    def graph(*command: str) -> dict[str, list[str]]:
        lines = git(*command, 'log', '--all', '--format=%H %P').splitlines()
        return {fields[0]: fields[1:] for line in lines
                if (fields := line.split()) and fields[0]}

    old_graph = graph('-C', str(source))
    new_graph = graph('--git-dir', str(destination))
    if len(old_graph) != len(new_graph):
        raise RuntimeError('commit graph size differs')
    if len(oid_map) < len(old_graph):
        raise RuntimeError('not all source commits received a mark')
    for old, parents in old_graph.items():
        new = oid_map.get(old)
        if not new or new not in new_graph:
            raise RuntimeError(f'unmapped or missing commit {old}')
        expected = [oid_map.get(p) for p in parents]
        if None in expected or new_graph[new] != expected:
            raise RuntimeError(f'commit-parent relationship changed for {old}')
    return len(old_graph), oid_map


def rewrite(source: Path, destination: Path, bundle: Path | None, policy: dict) -> None:
    if destination.exists() or destination.with_name(destination.name+'.incomplete').exists():
        raise SystemExit('destination exists (or incomplete destination needs attention); refusing overwrite')
    if bundle and (bundle.exists() or bundle.with_name(bundle.name+'.incomplete').exists()):
        raise SystemExit('bundle exists; refusing overwrite')
    if not (source/'.git').is_dir():
        raise SystemExit('--source must be a regular non-bare Git checkout')
    clean = git('status','--porcelain','--untracked-files=no', cwd=source)
    if clean:
        raise SystemExit('source has uncommitted tracked changes; commit cleanup first')
    git_dir = Path(git('rev-parse','--absolute-git-dir',cwd=source))
    original = read_refs(source)
    branch = original.get('refs/heads/main')
    if not branch:
        raise SystemExit('missing main branch')
    if git('rev-parse','HEAD',cwd=source) != branch:
        raise SystemExit('source HEAD must be checked out on main')
    if subprocess.run(['git','-C',str(source),'merge-base','--is-ancestor',
                       policy['base_commit'],'main']).returncode:
        raise SystemExit('main must descend from original 1.1.1 commit')
    if not git('log','-1','--format=%s',cwd=source).startswith('chore(repo):'):
        raise SystemExit('main lacks expected committed cleanup tip')
    incomplete = destination.with_name(destination.name+'.incomplete')
    git('init','--bare','-q',str(incomplete))
    alternate = incomplete/'objects'/'info'/'alternates'
    alternate.write_text(str(git_dir/'objects')+'\n')
    bytes_total = 0
    removed = 0
    commits = 0
    try:
        export_cmd = ['git','-C',str(source),'fast-export','--no-data',
                      '--signed-tags=strip','--tag-of-filtered-object=rewrite',
                      '--export-marks='+str(incomplete/'export.marks'), '--all']
        import_cmd = ['git','--git-dir',str(incomplete),'fast-import','--force','--quiet',
                      '--export-marks='+str(incomplete/'import.marks')]
        with (incomplete/'export.stderr').open('wb') as err_out, (incomplete/'import.stderr').open('wb') as err_in:
            export = subprocess.Popen(export_cmd, stdout=subprocess.PIPE, stderr=err_out)
            imported = subprocess.Popen(import_cmd, stdin=subprocess.PIPE, stderr=err_in)
            assert export.stdout is not None and imported.stdin is not None
            try:
                while True:
                    line = export.stdout.readline()
                    if not line:
                        break
                    if line.startswith(b'data '):
                        imported.stdin.write(line)
                        length = int(line[5:].strip())
                        copy_exact(export.stdout, imported.stdin, length)
                    else:
                        path = path_from_op(line)
                        if path is not None and selected(path, policy):
                            removed += 1
                            continue
                        imported.stdin.write(line)
                        if line.startswith(b'commit '):
                            commits += 1
                    bytes_total += len(line)
            except BaseException:
                export.kill()
                imported.kill()
                raise
            finally:
                export.stdout.close()
                imported.stdin.close()
            ex_rc = export.wait()
            im_rc = imported.wait()
            if ex_rc or im_rc:
                raise RuntimeError(f'fast-export={ex_rc}, fast-import={im_rc}; see *.stderr')
        if not removed:
            raise RuntimeError('no history paths removed: policy or source mismatch')
        # Promote remote-tracking branch refs to ordinary local branches, but
        # never replace the original local main with a stale origin/main.
        refs = read_refs(incomplete)
        for remote_name, obj in sorted(refs.items()):
            if not remote_name.startswith('refs/remotes/') or remote_name.endswith('/HEAD'):
                continue
            local = 'refs/heads/' + remote_name.split('/', 3)[-1]
            if local not in refs:
                git('--git-dir',str(incomplete),'update-ref',local,obj)
            git('--git-dir',str(incomplete),'update-ref','-d',remote_name)
        if 'refs/remotes/origin/HEAD' in refs:
            git('--git-dir',str(incomplete),'update-ref','-d','refs/remotes/origin/HEAD')
        # A Git bundle cloned as a repository needs a valid default HEAD.
        # git init --bare would otherwise leave HEAD on an unborn "master".
        git('--git-dir',str(incomplete),'symbolic-ref','HEAD','refs/heads/main')
        rewritten = read_refs(incomplete)
        input_branches = {r if r.startswith('refs/heads/') else 'refs/heads/'+r.split('/',3)[-1]
                          for r in original if r.startswith('refs/heads/') or
                          (r.startswith('refs/remotes/') and not r.endswith('/HEAD'))}
        output_branches = {r for r in rewritten if r.startswith('refs/heads/')}
        input_tags = {r for r in original if r.startswith('refs/tags/')}
        output_tags = {r for r in rewritten if r.startswith('refs/tags/')}
        if input_branches != output_branches or input_tags != output_tags:
            raise RuntimeError(f'branch/tag ref mismatch: {input_branches ^ output_branches}, {input_tags ^ output_tags}')
        # Verify every original tagged and branch-tip commit remains represented
        # in rewritten ancestry and every processed ref name survives.
        old_count = int(git('rev-list','--all','--count',cwd=source))
        new_count = int(git('--git-dir',str(incomplete),'rev-list','--all','--count'))
        if new_count != old_count:
            raise RuntimeError(f'commit graph count changed {old_count} -> {new_count}')
        graph_count, commit_oid_map = verify_graph(source, incomplete)
        if graph_count != old_count:
            raise RuntimeError(f'commit graph mismatch {graph_count} != {old_count}')
        # Check both tag object kind and exact tagged commit correspondence.
        for ref in sorted(input_tags):
            original_type = git('cat-file','-t',original[ref],cwd=source)
            rewritten_type = git('--git-dir',str(incomplete),'cat-file','-t',rewritten[ref])
            if original_type != rewritten_type:
                raise RuntimeError(f'tag kind changed for {ref}: {original_type} -> {rewritten_type}')
            old_peeled = git('rev-parse',ref+'^{commit}',cwd=source)
            new_peeled = git('--git-dir',str(incomplete),'rev-parse',ref+'^{commit}')
            if commit_oid_map.get(old_peeled) != new_peeled:
                raise RuntimeError(f'tag commit mis-targeted: {ref}')
        # Source and upstream subtrees remain the original object IDs at
        # every branch and release tag, despite rewriting enclosing trees.
        for ref in sorted(output_branches | output_tags):
            source_ref = ref if ref in original else ('refs/remotes/origin/'+ref.split('refs/heads/',1)[1])
            if source_ref not in original:
                raise RuntimeError(f'unmapped source ref: {ref}')
            for subtree in ('src', 'test', 'libdolbyb', 'libebur128', 'libgsm', 'lpc10'):
                old_tree = git('rev-parse', source_ref+':'+subtree, cwd=source, check=False)
                new_tree = git('--git-dir',str(incomplete),'rev-parse', ref+':'+subtree, check=False)
                if old_tree != new_tree:
                    raise RuntimeError(f'{ref}:{subtree} changed, violates source preservation')
        git('--git-dir',str(incomplete),'fsck','--full','--no-reflogs')
        # A path inventory of all reachable objects (not just current branch
        # tips) must contain none of the archived paths.
        rev_objects = git('--git-dir',str(incomplete),'rev-list','--objects','--all')
        leaked = [line for line in rev_objects.splitlines() if ' ' in line and
                  selected(line.split(' ',1)[1],policy)]
        if leaked:
            raise RuntimeError(f'archived paths still reachable: {leaked[:3]}')
        # Unlike rev-list --objects, which may label shared blobs with only
        # one representative path, the union of all history diffs catches
        # excluded names even when the same blob exists elsewhere.
        historic_names = git('--git-dir',str(incomplete), 'log', '--all', '-m',
                             '--name-only', '--format=')
        leaked_history = [name for name in historic_names.splitlines() if selected(name, policy)]
        if leaked_history:
            raise RuntimeError(f'excluded historical modifications survived: {leaked_history[:3]}')
        if bundle:
            bundle_temp = bundle.with_name(bundle.name+'.incomplete')
            git('--git-dir',str(incomplete),'bundle','create',str(bundle_temp),'--all')
            bundle_temp.replace(bundle)
        (incomplete/'rewrite-manifest.json').write_text(json.dumps({
            'original_main':branch, 'rewritten_main':rewritten['refs/heads/main'],
            'old_commits':old_count, 'new_commits':new_count,
            'commit_parent_graph_verified':True, 'release_tag_targets_verified':True,
            'source_subtrees_identical_across_all_refs':True,
            'removed_path_operations':removed,'export_lines_bytes':bytes_total,
            'input_refs':original,'output_refs':rewritten},sort_keys=True,indent=2)+'\n')
        # Store the replayable manifest outside .git after renaming the dir.
        if (incomplete/'export.stderr').stat().st_size:
            print('fast-export emitted warnings; inspect export.stderr',file=sys.stderr)
        destination.parent.mkdir(parents=True, exist_ok=True)
        incomplete.replace(destination)
        print(json.dumps({'destination':str(destination),'bundle':str(bundle) if bundle else None,
                          'commit_count':new_count,'removed_path_operations':removed,
                          'refs':len(rewritten)},sort_keys=True))
    except BaseException:
        print('rewrite failed; incomplete bare repository retained at '+str(incomplete),file=sys.stderr)
        raise


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True,type=Path)
    p.add_argument('--destination',required=True,type=Path)
    p.add_argument('--bundle',type=Path)
    a=p.parse_args()
    rewrite(a.source.resolve(),a.destination.resolve(),
            a.bundle.resolve() if a.bundle else None,json.loads(POLICY.read_text()))


if __name__=='__main__':
    main()

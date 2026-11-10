#!/usr/bin/env python3
"""Remove only policy-selected tracked records and their Automake dist entries.

Run once on original 1.1.1 HEAD, after saving the evidence archive. Repeating
it on a cleaned tree does nothing. This is intentionally not a general-purpose
'move all results' janitor: historical records must be archived first.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess

POLICY = Path(__file__).with_name('repo_cleanup_policy.json')
ROOT = POLICY.resolve().parents[1]


def run(*args: str, capture=False):
    return subprocess.run(['git', '-C', str(ROOT), *args], check=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def selected(p: str, policy: dict) -> bool:
    return p in policy['exact_paths'] or any(p.startswith(x) for x in policy['prefixes'])


def strip_extra_dist(makefile: str, policy: dict) -> tuple[str, int]:
    lines = makefile.splitlines(keepends=True)
    updated: list[str] = []
    removed = 0
    index = 0
    while index < len(lines):
        first = lines[index]
        match = re.match(r'^(EXTRA_DIST\s*(?:\+?=))\s*(.*)$', first)
        if not match:
            updated.append(first)
            index += 1
            continue
        start = index
        block = [first]
        while block[-1].rstrip('\r\n').rstrip().endswith('\\'):
            index += 1
            if index >= len(lines):
                raise RuntimeError('unterminated Automake EXTRA_DIST continuation')
            block.append(lines[index])
        index += 1
        rest = [match.group(2)] + block[1:]
        # Backslash continuations are whitespace separators in Makefile syntax.
        raw = ' '.join(x.rstrip('\r\n').rstrip().rstrip('\\') for x in rest)
        tokens = raw.split()
        new_tokens = [tok for tok in tokens if not selected(tok, policy)]
        removed += len(tokens) - len(new_tokens)
        if tokens == new_tokens:
            updated.extend(block)
            continue
        if not new_tokens and match.group(1).endswith('+='):
            continue
        # Deterministic reflow. Preserve token order and expression syntax,
        # including Automake $(wildcard ...) terms, as whitespace is retained.
        decl = match.group(1)
        chunks = [decl]
        for tok in new_tokens:
            if len(chunks[-1]) + 1 + len(tok) > 92:
                chunks.append('  ' + tok)
            else:
                chunks[-1] += ' ' + tok
        updated.extend(c + (' \\\n' if i < len(chunks)-1 else '\n')
                       for i, c in enumerate(chunks))
    return ''.join(updated), removed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true', help='actually delete; default only describes')
    args = ap.parse_args()
    policy = json.loads(POLICY.read_text())
    paths = [p.decode('utf-8','surrogateescape') for p in
             run('ls-files','-z',capture=True).stdout.split(b'\x00') if p]
    removal = [p for p in paths if selected(p, policy)]
    makefile = ROOT / 'Makefile.am'
    revised, dropped_tokens = strip_extra_dist(makefile.read_text(), policy)
    print(f'policy selected {len(removal)} tracked paths; {dropped_tokens} EXTRA_DIST tokens')
    if not args.apply:
        print('dry run; use --apply only after producing the verified evidence archive')
        return
    if removal and run('rev-parse','HEAD',capture=True).stdout.decode().strip() != policy['base_commit']:
        raise SystemExit('refusing deletion: checked out HEAD is not the original 1.1.1 base')
    if removal:
        changed = run('diff','--name-only','-z','HEAD','--',*policy['prefixes'],
                      *[p for p in policy['exact_paths'] if (ROOT/p).exists()],capture=True).stdout
        if changed:
            raise SystemExit('refusing to delete locally edited evidence files')
        names = [p for p in policy['exact_paths'] if p in removal]
        dirs = [p.rstrip('/') for p in policy['prefixes'] if any(x.startswith(p) for x in removal)]
        run('rm','-r','-q','--ignore-unmatch','--',*dirs,*names)
    if revised != makefile.read_text():
        makefile.write_text(revised)
    print('cleanup applied (idempotent); inspect Git diff and commit deliberately')


if __name__ == '__main__':
    main()

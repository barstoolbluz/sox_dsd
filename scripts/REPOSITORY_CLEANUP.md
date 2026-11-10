# SoX DSD repository cleanup: release engineering handoff

This operation preserves the 1.1.1 program and library sources and their
upstream SoX-NG layout. It removes historical engineering paperwork and
qualification run outputs from the main repository and **every reachable
commit** while preserving each named branch and annotated tag. The new
commits, tags and branch tips necessarily receive new object IDs. A history
rewrite cannot preserve existing signed tag signatures; signatures are
stripped rather than presented as valid after changing the tag targets.

## Inputs and artifacts

- Baseline: 2026-11-09 `main` at `90fe3df68deb1b45953355646d940ca4501a45cc`, tag `sox_dsd-1.1.1`.
- Full original source/history is supplied as a Git bundle. Verify it and
  retain an **independent private backup** before any rewrite.
- `repo_cleanup_policy.json` defines the exact path exclusions. No globbed
  deletion touches `src/`, `test/`, `tests/dsd/fixtures/`,
  `tests/dsd/reference/`, `tests/dsd/release_evidence/`, or upstream files.
- `build_dsd_evidence_archive.py` builds the standalone evidence release asset
  from the **original checkout** before source deletion or history rewrite.
  It preserves both the original HEAD evidence and every distinct prior
  path/blob revision excluded from history, including files already deleted
  at the 1.1.1 baseline. `HISTORY_MANIFEST.jsonl` maps the old Git blob IDs
  to their separately redacted copies under `history/`.
- `rewrite_dsd_history.py` consumes the cleaned *committed* checkout and
  produces a new bare repository and optional, fully portable Git bundle.

## Safe sequence

1. Back up all upstream branches, tags, and unmodified objects. Save the
   original Git bundle externally. Record remote ref SHA-1 values for leases.
2. From the **cleaned** checkout, run the evidence exporter against the
   original, unmodified 1.1.1 checkout:

   ```sh
   python3 scripts/build_dsd_evidence_archive.py \
     --source /path/to/original-1.1.1-checkout \
     --output /path/to/SoX_DSD_1.1.1_Evidence_2026-11-09.tar.zst
   zstd -t /path/to/SoX_DSD_1.1.1_Evidence_2026-11-09.tar.zst
   ```

   The exporter checks the original HEAD, tracked file inventory, full reachable
   historical path/blob inventory, source types and redaction completeness. It
   does not modify its input. The asset contains `README.md`, `MANIFEST.jsonl`,
   `HISTORY_MANIFEST.jsonl`, `REDACTIONS.json`, `files/` and `history/`.
   File names are repository-relative; raw private recording material was not
   supplied. Unchanged binary evidence is copied byte-identically.
   Run `python3 scripts/test_build_dsd_evidence_archive.py` before export.
3. Apply the supplied cleanup commit to the original repository (or use the
   supplied prebuilt cleaned Git bundle). Confirm `git status --porcelain` is
   empty, then build and test the cleaned working tree; run `make dist` and
   compile/test the resulting source tarball. Check `src/` and `test/`
   remain byte-identical to 1.1.1. Do not bump the version.
4. Rewrite into a **new** destination, never in place:

   ```sh
   python3 scripts/rewrite_dsd_history.py \
      --source /path/to/committed-clean-checkout \
      --destination /path/to/sox_dsd-rewritten.git \
      --bundle /path/to/sox_dsd-rewritten.bundle
   git clone /path/to/sox_dsd-rewritten.bundle verify-clone
   git -C verify-clone fsck --full
   git -C verify-clone branch -a
   git -C verify-clone tag -l
   ```

   The rewriter keeps every commit (including formerly evidence-only
   commits, now possibly empty) and all merge parents, promotes remote
   tracking branches into local heads, verifies ref sets and commit counts,
   scans reachable Git objects for excluded paths and emits an audit manifest.
   Its new bare repository initially uses Git alternates pointing to the
   original object database; **publish only the self-contained bundle** or
   repack into an independent repository. Verify the portable bundle by
   cloning it while the original repository is unavailable.
5. Inspect every tag and branch. In a detached verification worktree, build
   1.1.1 and older tags: the archived evidence is no longer available for
   their historical evidence-reading checks, but `autoreconf -i`, configure
   and ordinary compilation must work. Also run `make dist` and tarball
   smoke tests on the new main.
6. Publish the evidence archive as a GitHub release asset, not as a Git blob.
   Coordinate a repository-wide history replacement. Remote branches and
   release tags must be updated **together** with explicit, reviewed leases.
   Do not execute an unqualified `git push --mirror` or a blind force-push:
   remote-only refs, protected branches, signed tags and collaborators need
   deliberate handling. All existing clones must re-clone or explicitly
   transplant work; old SHA-1 references cannot be assumed to remain valid.

## Acceptance

- `git diff -- src test` against 1.1.1 is empty; the program and library
  binaries built from an otherwise identical toolchain have identical sources.
- The build, `make dist`, tarball rebuild, and the listed 1.1.1 checks pass
  (with the known `INCOMPLETE` synthetic-only independent-reader campaign).
- New `main` and every rewritten branch/tag have no excluded files in any
  reachable commit; original upstream-owned files stay at upstream paths.
- All original local branch names, remote GitHub branch names and release tag
  names survive. All annotated tags remain annotated, excluding obsolete
  cryptographic signatures.
- The archive can be integrity-checked and lists every redacted current or
  historical revision with original/published SHA-256 and original Git blob
  IDs for the earlier versions. No host-private paths are republished as text.
- `nix build .#default` and `.#checked` should be run on the owner host.

The cleanup policy intentionally leaves test sources and existing fixtures in
place. Some historical research scripts refer to archival receipts and require
restoration of the evidence asset for independent replay, but this is not part
of shipping regression checks. Historical tags may have obsolete instructions
that reference files removed by the rewrite; these are not current user docs.

#!/usr/bin/env python3
"""Verify immutable inherited source/evidence against the submitted third pass.

The earlier verifier deliberately pins its older input archive. This separate
audit preserves that verifier and compares against the exact newly submitted
archive, including the inherited 16,711-file subset and all original production
sources, DSD authority documents and historical result files. New result files
are permitted; an inherited file cannot disappear or change.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
import tempfile

SUBMITTED_SHA256 = "d0bd8a65a149f4267a4d33bb8763aa56faa937ae78009a9796a9b31bcd2e04c4"
PRIOR = "tests/dsd/results/P15_prover_third_pass_2026-10-18/ORIGINAL_SOURCE_INTEGRITY.json"
PREFIXES = (
    "tests/dsd/results/P15_full_band_campaign_complete_2026-10-18/receipts/",
    "tests/dsd/results/P15_full_band_campaign_partial_2026-10-17/receipts/",
    "tests/dsd/results/P15_full_band_campaign_complete_2026-10-18/budget-sample/",
)


def digest_stream(stream):
    digest = sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def file_digest(path):
    with path.open("rb") as stream:
        return digest_stream(stream)


def publish_identical(path, data):
    """Publish once; identical replay succeeds, any conflicting result refuses."""
    if path.exists():
        if path.is_symlink() or path.read_bytes() != data:
            raise ValueError(f"refusing changed existing audit: {path}")
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != data:
                raise ValueError(f"conflicting concurrently published audit: {path}")
    finally:
        temporary.unlink()


def verify(root, submitted):
    if file_digest(submitted) != SUBMITTED_SHA256:
        raise ValueError("submitted third-pass archive SHA-256 mismatch")
    inherited = json.loads((root / PRIOR).read_text())
    pinned = inherited["current_pinned_source_identity"]
    counts, scope_counts, inventory = Counter(), Counter(), {}
    original_order = sha256()
    checked_original = set()
    with tarfile.open(submitted, mode="r|gz") as archive:
        for member in archive:
            if not member.isfile() or not member.name.startswith("sox_ng/"):
                continue
            relative = member.name[len("sox_ng/"):]
            old_tag = next((prefix for prefix in PREFIXES if relative.startswith(prefix)), None)
            if old_tag is None and relative in pinned:
                old_tag = "pinned_sources"
            scope = next((prefix for prefix in ("src/", "docs/dsd/", "tests/dsd/results/")
                          if relative.startswith(prefix)), None)
            if old_tag is None and scope is None:
                continue
            path = PurePosixPath(relative)
            if path.is_absolute() or ".." in path.parts or relative in inventory:
                raise ValueError(f"unsafe/duplicate inherited archive member: {relative}")
            current = root / relative
            if current.is_symlink() or not current.is_file() or current.stat().st_size != member.size:
                raise ValueError(f"inherited file missing or changed type/size: {relative}")
            with archive.extractfile(member) as stream:
                original_digest = digest_stream(stream)
            if file_digest(current) != original_digest:
                raise ValueError(f"inherited source/evidence changed: {relative}")
            inventory[relative] = original_digest
            scope_counts[scope or "additional_pinned_source"] += 1
            if old_tag is not None:
                checked_original.add(relative)
                counts[old_tag] += 1
                original_order.update(relative.encode() + b"\0" + original_digest.encode() + b"\n")
    expected = set(pinned)
    for prefix in PREFIXES:
        expected.update(str(path.relative_to(root)) for path in (root / prefix).glob("*.json"))
    if expected != checked_original or dict(counts) != inherited["counts"]:
        raise ValueError("inherited 16,711-file set/count differs from prior audit")
    if len(checked_original) != 16711:
        raise ValueError("wrong inherited verification population")
    current_pins = {path: inventory[path] for path in pinned}
    if current_pins != pinned:
        raise ValueError("pinned source identity disagrees with inherited audit")
    manifest = "".join(f"{inventory[path]}  {path}\n" for path in sorted(inventory)).encode()
    report = dict(
        schema="P15/high-rate-inherited-integrity/1",
        status="ALL_INHERITED_CHECKED_FILES_BYTE_IDENTICAL",
        submitted_archive_sha256=SUBMITTED_SHA256,
        inherited_audit_sha256=inventory[PRIOR],
        inherited_verified_files=len(checked_original),
        inherited_counts=dict(counts),
        inherited_inventory_digest_in_current_tar_order=original_order.hexdigest(),
        inherited_original_order_digest=inherited["original_evidence_inventory_sha256"],
        inherited_tar_order_matches_prior=(original_order.hexdigest() == inherited["original_evidence_inventory_sha256"]),
        total_files_verified=len(inventory),
        scope_counts=dict(scope_counts),
        full_sorted_sha256_manifest_sha256=sha256(manifest).hexdigest(),
        current_pinned_source_identity=current_pins,
        scope="Inherited 16,711 subset plus all original src/, docs/dsd/, and tests/dsd/results/ regular files; additions allowed.",
        release_status="BLOCKED",
    )
    return report, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--submitted", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result, manifest = verify(args.root.resolve(), args.submitted.resolve())
    args.output.mkdir(parents=True, exist_ok=True)
    publish_identical(args.output / "INHERITED_FILES.sha256", manifest)
    publish_identical(args.output / "INTEGRITY.json", (json.dumps(result, indent=2, sort_keys=True) + "\n").encode())
    print(json.dumps({key: value for key, value in result.items() if key != "current_pinned_source_identity"}, indent=2))


if __name__ == "__main__":
    main()

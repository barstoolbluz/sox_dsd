#!/usr/bin/env python3
"""Read-only audit of retained physical measurements and v2 observation scope.

This report is not release adjudication. It independently recomputes the saved
timing statistics, verifies available digests, and calls the existing matrix
receipt reviewer without pretending the omitted numerical/audio files exist.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import sys

from verify_inherited_integrity import PREFIXES, PRIOR, file_digest, publish_identical


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bootstrap_independent(control, decoder):
    """Reimplement the specified seeded 15-sample median-ratio bootstrap."""
    for values in (control, decoder):
        require(len(values) == 15 and all(type(value) in (int, float) and
                math.isfinite(value) and value > 0 for value in values),
                "invalid saved duration array")
    rng = random.Random(20261016)
    ratios = []
    for _ in range(10000):
        arm = sorted(control[rng.randrange(15)] for _ in range(15))[7]
        ref = sorted(decoder[rng.randrange(15)] for _ in range(15))[7]
        ratios.append(arm / ref)
    ratios.sort()
    return dict(point=sorted(control)[7] / sorted(decoder)[7],
                ci95=[ratios[250], ratios[9750]],
                exceeds_two_at_lower_bound=ratios[250] > 2)


def original_continuity(root, directory):
    """Reproduce the original 16,711-file inventory despite new tar ordering."""
    audit = json.loads((directory / "INTEGRITY.json").read_text())
    prior = json.loads((root / PRIOR).read_text())
    manifest = (directory / "INHERITED_FILES.sha256").read_bytes()
    require(sha256(manifest).hexdigest() == audit["full_sorted_sha256_manifest_sha256"],
            "inherited sorted manifest changed")
    require(file_digest(root / PRIOR) == audit["inherited_audit_sha256"],
            "inherited original audit changed")
    inventory = sha256()
    count = 0
    for line in manifest.decode().splitlines():
        digest, relative = line.split("  ", 1)
        if relative in prior["current_pinned_source_identity"] or relative.startswith(PREFIXES):
            inventory.update(relative.encode() + b"\0" + digest.encode() + b"\n")
            count += 1
    require(count == 16711 and inventory.hexdigest() == prior["original_evidence_inventory_sha256"],
            "original 16,711-file inventory identity not reproduced")
    return dict(status="ORIGINAL_16711_FILE_INVENTORY_DIGEST_REPRODUCED",
                verified_files=count, original_inventory_sha256=inventory.hexdigest(),
                note="The older archive enumerated the subset lexically. Recomputing in lexical order exactly reproduces its digest; the third-pass tar uses another member order.")


def physical_review(root):
    directory = root / "tests/dsd/results/P15_ps_matched_physical_2026-10-16"
    spectral_file, bench_file = directory / "comparator/RECEIPT.json", directory / "bench/RECEIPT.json"
    spectral, bench = json.loads(spectral_file.read_text()), json.loads(bench_file.read_text())
    require(spectral["status"] == "SPECTRALLY_MATCHED_DIAGNOSTIC" and
            bench["status"] == "MEASURED_PHYSICAL_UNADJUDICATED" and
            spectral["qualified_release"] is False and bench["qualified_release"] is False,
            "physical receipt scope changed")
    require(bench["spectral_receipt_sha256"] == file_digest(spectral_file) and
            spectral["source_sha256"] == bench["source_sha256"] and
            spectral["executable_sha256"] == bench["executable_sha256"],
            "physical/spectral provenance differs")
    pins = {name: file_digest(root / name) == digest for name, digest in bench["source_sha256"].items()}
    require(len(pins) == 8 and all(pins.values()), "recorded physical source pin drift")
    require(bench["repetitions"] == 15 and bench["warmups"] == 2 and
            bench["bootstrap"] == dict(iterations=10000, seed=20261016) and bench["target"] == 2,
            "recorded benchmark method differs")
    host = bench["host"]
    require(host["system"] == "Linux" and host["machine"] in ("x86_64", "aarch64") and
            host["hypervisor"] is False and bench["physical_host_admissible"] is True and
            bench["pinned_cpu"] in host["allowed_cpus"], "recorded physical admission differs")
    cells, diagnostics, missing = [], [], []
    expected_cells = {(profile, rate) for profile in ("mastering", "decode.mastering.v2.dsd256")
                      for rate in (176400, 352800)}
    require(set(bench["rows"]) == {profile + "@" + str(rate) for profile, rate in expected_cells},
            "physical timing grid incomplete")
    require({(row["profile"], row["rate"]) for row in spectral["rows"]} == expected_cells,
            "physical spectral grid incomplete")
    for name, row in sorted(bench["rows"].items()):
        require(set(row["seconds"]) == {"decoder", "legacy_direct", "legacy_ps_matched"},
                "missing timing arm")
        for arm in ("legacy_direct", "legacy_ps_matched"):
            calculated = bootstrap_independent(row["seconds"][arm], row["seconds"]["decoder"])
            require(calculated == row["comparisons"][arm], "saved bootstrap mismatch")
            cells.append(dict(cell_id=name, control=arm, **calculated))
    for row in spectral["rows"]:
        diagnostic = row["verification"]
        expected_pass = 66000 if "v2" in row["profile"] else 40000
        require(row["pass_hz"] == expected_pass and row["stop_hz"] == 80000 and
                diagnostic["comparison_band_hz"] == [1000., float(expected_pass)] and
                diagnostic["transition_excluded_fraction"] == 0 and diagnostic["matched"] is True,
                "spectral diagnostic changed passband edge or excluded transition")
        diagnostics.append(dict(profile=row["profile"], rate=row["rate"],
            comparison_band_hz=diagnostic["comparison_band_hz"],
            max_abs_difference_db=diagnostic["max_abs_difference_db"],
            transition_excluded_fraction=diagnostic["transition_excluded_fraction"]))
    for name, digest in spectral["file_sha256"].items():
        path = directory / "comparator" / name
        if path.is_file():
            require(file_digest(path) == digest, "retained comparator payload changed")
        else:
            missing.append("comparator/" + name)
    for name, key in (("input-6ch.dsf", "six_channel_native_sha256"),
                      ("input-6ch.wav", "six_channel_pcm_sha256")):
        path = directory / "bench" / name
        if path.is_file():
            require(file_digest(path) == bench[key], "retained timing fixture changed")
        else:
            missing.append("bench/" + name)
    executable_paths = sorted({row["commands"]["decoder"][0] for row in bench["rows"].values()})
    return dict(
        disposition="MEASUREMENTS_EXIST_STATISTICS_REPRODUCED_ADJUDICATION_AND_FULL_RAW_REPLAY_PENDING",
        receipt_status=bench["status"], qualified_release=False,
        bench_receipt_sha256=file_digest(bench_file), comparator_receipt_sha256=file_digest(spectral_file),
        recorded_source_pins_match=pins, recorded_binary_sha256=bench["executable_sha256"],
        recorded_command_executable_paths=executable_paths,
        recorded_executable_paths_available={path: Path(path).is_file() for path in executable_paths},
        pinned_header_coverage_limitation="Physical source_sha256 does not include rate_poly_fir0.h; the October 17 opt-in SRC build is not a new physical timing target by inheritance.",
        host=host, pinned_cpu=bench["pinned_cpu"],
        all_eight_bootstraps_exactly_reproduced=True,
        comparisons_meeting_two_at_lower_bound=sum(row["exceeds_two_at_lower_bound"] for row in cells),
        minimum_ci95_lower=min(row["ci95"][0] for row in cells),
        comparisons=cells, saved_spectral_diagnostics=diagnostics,
        missing_audio_payloads=missing, complete_audio_or_executable_replay=False,
        limitations=[
            "Saved spectral diagnostics were measured on noise over 1 kHz through the guaranteed passband edge; they are not continuous-frequency 0.0001 dB/-160 dB certificates.",
            "The old current-closeout gate still reads October 15 comparator receipts and is not a review of the October 16 measurement.",
            "Boost-disabled preparation is stated in the physical README, not encoded in the timing receipt.",
            "This source-only audit does not infer a new release authorization or rerun physical measurements.",
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root / "tests/dsd"))
    import p15_current_closeout as reviewer
    require(Path(reviewer.__file__).resolve() == root / "tests/dsd/p15_current_closeout.py",
            "imported wrong matrix reviewer")
    physical = physical_review(root)
    matrices = {name: reviewer.matrix(folder, name)
                for name, folder in (("v1", reviewer.V1), ("v2", reviewer.V2))}
    for result in matrices.values():
        result["binding_scope"] = "Only recorded source pins are verified; original executable archive is not reconstructed."
    authority_paths = [
        "docs/dsd/DSD_DESIGN.md",
        "docs/dsd/amendments/P15_SRC_ACCEPTANCE_METHOD_2026-10-15.md",
        "docs/dsd/amendments/P15_V2_DEFAULT_POLICY_2026-10-15.md",
        "docs/dsd/P15_SRC_OPT_REBIND_2026-10-17.md",
        "docs/dsd/handoffs/P15_FINAL_OBLIGATIONS_R2_2026-10-16.md",
        "tests/dsd/results/P15_ps_matched_physical_2026-10-16/README.md",
        "tests/dsd/p15_current_closeout.py",
        "tests/dsd/p15_fft_coefficient_interval.py",
    ]
    result = dict(schema="P15/high-rate-secondary-obligation-audit/1",
        release_status="BLOCKED", v2_default_promotion=False, p16_authorized=False,
        integrity_continuity=original_continuity(root, args.output),
        physical_dsd256=physical, matrix_observations=matrices,
        fft4g_arbitrary_input_execution="OPEN: coefficient-bin bounds and ideal captured-FIR transfer certificates do not bound runtime FFT4G forward/inverse butterflies, packed products, input-dependent accumulation, or nonstandard arithmetic.",
        v2_remaining_scope="Observed 27-cell coverage exists. Omitted 135 numeric arrays prevent full raw replay; 24 v2 SRC-active cells still need same-operator arithmetic and full composite spectral qualification. No new metrology policy imposed.",
        source_documents_sha256={name: file_digest(root / name) for name in authority_paths})
    args.output.mkdir(parents=True, exist_ok=True)
    publish_identical(args.output / "SECONDARY_OBLIGATIONS.json",
                      (json.dumps(result, indent=2, sort_keys=True) + "\n").encode())
    print(json.dumps(dict(release_status=result["release_status"],
        integrity_continuity=result["integrity_continuity"],
        physical_comparisons_verified=len(physical["comparisons"]),
        min_physical_ci95_lower=physical["minimum_ci95_lower"],
        v2_observed_scalar_cells=matrices["v2"]["scalar_cells"],
        v2_missing_numeric_arrays=matrices["v2"]["absent_array_payloads_in_stripped_archive"]), indent=2))


if __name__ == "__main__":
    main()

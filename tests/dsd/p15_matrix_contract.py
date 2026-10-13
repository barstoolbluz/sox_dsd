#!/usr/bin/env python3
"""Deterministic P15 decode metrology worklist; never a quality certificate.

A plan is not an instrument. Do not mark its rows PASS without independent
measured spectra, count/phase and stability receipts on the actual audio.
The project-defined thresholds remain in DSD_DESIGN, not a second policy copy.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
import os
from pathlib import Path
import tempfile

NATIVE_RATES = (2822400, 5644800, 11289600)
PCM_RATES = (44100, 48000, 88200, 96000, 176400, 192000, 352800, 384000, 705600)
PROFILES = ('mastering', 'wideband')
REQUIRED_TIERS = ('scalar', 'sse2', 'avx1', 'avx2', 'avx512')
# Each native/profile gets 44.1- and 48-family representation, high fractional
# SRC, and the maximum PCM rate. This is MINIMUM detailed cross-ISA metrology,
# not a waiver of the §10.4 full-tier release functional/phase/count grid.
CROSS_ISA_DETAIL_ENDPOINTS = (44100, 48000, 384000, 705600)


def cell_key(native_hz: int, profile: str, pcm_hz: int) -> str:
    return f'dsd{native_hz//44100}.{profile}.pcm{pcm_hz}'


def make_plan() -> dict:
    scalar = []
    tier_functional = []
    tier_metrology = []
    for native in NATIVE_RATES:
        for profile in PROFILES:
            for pcm in PCM_RATES:
                ident = cell_key(native, profile, pcm)
                integer = native % pcm == 0
                ref = ('independent-high-precision-finite-decimated-convolution'
                       if integer else 'independent-high-precision-rational-src-of-reconstruction')
                ratio = Fraction(pcm, native)
                scalar.append(dict(
                    id=ident, native_hz=native, profile=profile, pcm_hz=pcm,
                    output_per_native=f'{ratio.numerator}/{ratio.denominator}',
                    reference_type=ref,
                    decoder_math='native FIR cascade plus private SRC as needed',
                    required_evidence=(
                        'independent_transfer_envelope_and_coherent_alias_images',
                        'exact_output_count_phase_latency_and_finite_boundaries',
                        'independent_high_precision_oracle_and_roundoff',
                        'profile_bandwidth_adapt_or_strict_policy',
                        'DC_impulse_delayed_impulse_sweep_and_startup_drain',
                        'native_noise_separately_from_filter_alias_rejection',
                        'valid_one_bit_audio_gain_clipping_and_buffer_thread_invariance',
                    ),
                    status='UNRUN'))
                # Every available tier must traverse all 54 conversion choices
                # during release qualification. Unsupported tiers are UNRUN with
                # a named hardware/build reason, not recorded as PASS.
                for tier in REQUIRED_TIERS:
                    tier_functional.append(dict(cell=ident, tier=tier, status='UNRUN'))
                    if tier != 'scalar' and pcm in CROSS_ISA_DETAIL_ENDPOINTS:
                        tier_metrology.append(dict(cell=ident, tier=tier,
                                                   comparator='same-cell-scalar',
                                                   status='UNRUN'))
    return dict(
        schema='P15/decode-numerical-worklist/1',
        status='PLAN_ONLY_NOT_EXECUTED', qualified=False,
        normative_authority='docs/dsd/DSD_DESIGN.md sections 6, 8.6, 10.4 and 10.6',
        scalar_cells=scalar,
        release_forced_isa_functional=tier_functional,
        selected_cross_isa_detail=tier_metrology,
        available_kernel_tiers='must be recorded separately by each executing host',
        independent_reference_status={
            'integer_convolution': 'required in release pass; P06 finite oracles are a foundation, not all 30 cells',
            'fractional_src': 'required in release pass; P07 SciPy polyphase unit tests cover selected ratios, not 24 full-pipeline cells',
            'analysis_v1': 'frozen P09 encoder/SDM metrology only; NOT a full-band decode oracle',
        },
        threshold_policy={
            'transfer_envelope': 'DSD_DESIGN 6.1; test actual representable effective passband, never > output Nyquist',
            'fir_roundoff': 'DSD_DESIGN 8.6; pre-SRC roundoff and one-int32-LSB graph, not fractional SRC interchangeability',
            'fractional_src': 'DSD_DESIGN 10.4; independently measured combined SRC error, no borrowed FIR-only bound',
            'sdm_comparison': 'DSD_DESIGN 10.6; only for PCM-to-DSD encoder and cross-ISA SDM, not decoder FIR',
        },
        summary=dict(scalar_cells=len(scalar), integer_reference_cells=sum(
            x['reference_type'].endswith('decimated-convolution') for x in scalar),
            fractional_reference_cells=sum(
                x['reference_type'].endswith('src-of-reconstruction') for x in scalar),
            all_tier_functional_jobs=len(tier_functional),
            minimum_detailed_cross_isa_jobs=len(tier_metrology),
            independent_metrology_passed=0))


def write_json_atomic(output: Path, data: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n'
    # Atomic replace within the same filesystem; clean up on interruption.
    fd, name = tempfile.mkstemp(prefix=output.name + '.', suffix='.tmp', dir=output.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, output)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    obj = make_plan()
    write_json_atomic(args.output, obj)
    print(json.dumps({'status': obj['status'], **obj['summary']}, sort_keys=True))
    return 0  # successful planning, NOT a passing qualification


if __name__ == '__main__':
    raise SystemExit(main())

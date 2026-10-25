#!/usr/bin/env python3
"""Independent composite certificate for the two P21 high-rate v2 decode rows.

P21 added decode.mastering.v2.dsd512 and .dsd1024 by reusing the DSD256 v2
final bank behind a longer half-band cascade. The justification was an
analogy to how v1 reuses master64_256 across DSD256/512/1024, plus the
observation that the 66k/80k edges cannot usefully move while the
intermediate clock stays at 176400. The rows were then committed on a
behavioural comparison against the qualified DSD256 profile.

That is reasoning and a comparison, not a certificate. This measures the
cascade: passband ripple, stopband peak, the coherent image sum over
k=1..D-1, and the incoherent power sum, using the same independently
authored P06-derivative certifier that certifies the low-rate v2 rows, and
checks the published delay against the cascade identity.

It reads the production headers, not any generator.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/dsd'))
from certify_filters import load_coefficients, validate_composites  # noqa: E402

R3META = ROOT / 'tests/dsd/reference/p15_r3_coefficients.json'
V2HEADER = ROOT / 'src/dsd_coeffs_v2.h'

# The rows under test, taken from src/dsd.c. Reused final bank, growing cascade.
ROWS = {
    'decode.mastering.v2.dsd512':  dict(native_hz=22579200, intermediate_hz=176400,
                                        factor=128, pass_hz=66000, stop_hz=80000,
                                        halfbands=6, delay_native_frames=12132),
    'decode.mastering.v2.dsd1024': dict(native_hz=45158400, intermediate_hz=176400,
                                        factor=256, pass_hz=66000, stop_hz=80000,
                                        halfbands=7, delay_native_frames=24292),
}
FINAL_BANK = 'master256_v2'

def main():
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--results', type=Path, required=True)
    ap.add_argument('--grid', type=int, default=8192)
    args = ap.parse_args()

    r3 = json.loads(R3META.read_text())
    banks = load_coefficients()                      # v1 header: halfband etc.
    code = V2HEADER.read_text()
    for name, details in r3['banks'].items():        # v2 header, identity-checked
        m = re.search(r'\blsx_dsd_coeff_' + re.escape(name) + r'\[(\d+)\]\s*=\s*\{(.*?)\};',
                      code, re.S)
        if m is None:
            raise AssertionError('missing v2 header bank ' + name)
        h = np.array([float.fromhex(w.strip()) for w in m.group(2).split(',') if w.strip()],
                     dtype=np.float64)
        if len(h) != int(m.group(1)) or len(h) != details['length']:
            raise AssertionError(name + ' length mismatch')
        got = hashlib.sha256(('\n'.join(v.hex() for v in h) + '\n').encode('ascii')).hexdigest()
        if got != details['rounded_hex_sha256']:
            raise AssertionError(name + ' coefficient identity mismatch')
        banks[name] = h

    # Build the manifest for the rows under test and check the delay identity.
    profiles, delay_checks = {}, {}
    for ident, row in ROWS.items():
        names = ['halfband'] * row['halfbands'] + [FINAL_BANK]
        if row['native_hz'] != row['factor'] * row['intermediate_hz']:
            raise AssertionError(ident + ' clock/factor inconsistent')
        if len(names) != row['factor'].bit_length() - 1:
            raise AssertionError(ident + ' stage count does not match log2(factor)')
        G = sum((len(banks[n]) - 1) // 2 * (1 << j) for j, n in enumerate(names))
        delay_checks[ident] = dict(published=row['delay_native_frames'],
                                   cascade_identity=G,
                                   agrees=G == row['delay_native_frames'])
        # phase and discard follow from the same cascade delay, exactly as the
        # low-rate v2 manifest records them
        profiles[ident] = dict(native_hz=row['native_hz'],
                               intermediate_hz=row['intermediate_hz'],
                               factor=row['factor'], pass_hz=row['pass_hz'],
                               stop_hz=row['stop_hz'], stage_banks=names,
                               delay_native_frames=G,
                               phase_native_frames=G % row['factor'],
                               discard_output_frames=G // row['factor'])

    start = time.monotonic()
    composite = validate_composites(banks, {'profiles': profiles}, args.grid)
    # The already-certified DSD256 row, measured here too as the control the
    # reuse argument rests on: same final bank, one fewer half-band.
    control = validate_composites(banks,
        {'profiles': {k: v for k, v in r3['profiles'].items()
                      if k == 'decode.mastering.v2.dsd256'}}, args.grid)

    passed = all(v['passes'] for v in composite.values())
    delays_ok = all(v['agrees'] for v in delay_checks.values())
    report = dict(schema='sox-ng/p21-highrate-decode-certificate/1',
        source='C99 production header bytes, not generator output',
        method='independent P06-derivative composite certifier: localized adaptive '
               'extrema for passband ripple and stopband peak, full coherent image '
               'sum over k=1..D-1, separate incoherent power sum',
        rows_under_test=sorted(ROWS),
        final_bank_reused=FINAL_BANK,
        verdict='PASS' if (passed and delays_ok) else 'FAIL',
        delay_identity=delay_checks, profiles=composite,
        control_already_certified=control,
        establishes='The reused final bank behind 6 and 7 half-bands meets the same '
                    'passband, stopband and image bounds the DSD256 v2 row meets.',
        does_not_establish='Device behaviour, and the composite fractional SRC gate, '
                           'which remains separate.',
        elapsed_seconds=time.monotonic() - start)
    args.results.mkdir(parents=True, exist_ok=True)
    (args.results / 'highrate-decode-certificate.json').write_text(
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + '\n')
    print('P21 high-rate decode certificate:', report['verdict'])
    for ident, v in sorted(composite.items()):
        d = delay_checks[ident]
        print(f"  {ident}: pass {v['pass_ripple_db']} stop {v['stop_max_db']} "
              f"alias {v['coherent_alias_sum_db']} delay {d['published']}"
              f"{'' if d['agrees'] else ' MISMATCH vs ' + str(d['cascade_identity'])}"
              f" -> {'PASS' if v['passes'] else 'FAIL'}")
    for ident, v in sorted(control.items()):
        print(f"  control {ident}: pass {v['pass_ripple_db']} stop {v['stop_max_db']} "
              f"alias {v['coherent_alias_sum_db']} -> {'PASS' if v['passes'] else 'FAIL'}")
    return 0 if report['verdict'] == 'PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())

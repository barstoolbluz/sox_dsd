#!/usr/bin/env python3
"""Read-only, independent structural/hash audit of P11 QEMU and soak receipts.

This does not execute QEMU. Treat receipt execution as operator evidence; only
assert what can be checked from the delivered bytes. Run from any directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / 'tests/dsd/results'
EXPECTED_QUALIFIER = '1d126f9dc791a85845afe9799b4308fbd3d97818f7a962a7bbd31511ffb9182b'
LABELS = [
    'SandyBridge avx trap probe', 'SandyBridge avx2 trap probe',
    'SandyBridge fma trap probe', 'SandyBridge FIR and SDM unit',
    'Nehalem scalar/SSE2-only unit', 'Nehalem baseline CLI startup',
    'core2duo baseline CLI startup',
    *[f'SDM {tier} {mode}' for tier in ('scalar','sse2','avx1')
      for mode in ('emulated','native')],
    *[f'FIR {tier} {mode}' for tier in ('scalar','sse2','avx1')
      for mode in ('emulated','native')],
    'Nehalem forced FIR AVX1 rejected',
    'Nehalem forced SDM AVX1 rejected',
]
HEX64 = re.compile(r'[0-9a-f]{64}\Z')


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for buf in iter(lambda: f.read(1 << 20), b''):
            h.update(buf)
    return h.hexdigest()


def audit():
    errors = []
    def check(condition, description):
        if not condition:
            errors.append(description)

    qualifier = ROOT / 'tests/dsd/qualify_p11_avx1_emulator.py'
    actual_qualifier = digest(qualifier)
    check(actual_qualifier == EXPECTED_QUALIFIER,
          'qualifier differs from original previous-adjudication script')

    receipt_file = RESULTS / 'P11_avx1_no_avx2_replay_2026-10-11/avx1-no-avx2-replay.json'
    receipt = json.loads(receipt_file.read_text())
    rows = receipt.get('checks', [])
    check(receipt.get('schema') == 'P11/AVX1-QEMU-qualification/1', 'replay schema')
    check(receipt.get('status') == 'PASS' and not receipt.get('errors') and not receipt.get('limits'),
          'replay status/errors/limits')
    check('10.0.13' in receipt.get('qemu_version', ''), 'qemu version')
    check(len(rows) == 21 and [r.get('check') for r in rows] == LABELS,
          '21 expected checks in expected order')
    expected_rc = [0, -4, -4] + [0]*16 + [2, 2]
    check(len(expected_rc) == len(LABELS), 'internal expected count')
    for idx, row in enumerate(rows):
        exp = expected_rc[idx]
        check(row.get('status') == 'PASS' and row.get('expected') == exp and
              row.get('returncode') == exp, f'check {idx+1} status/returncode')
        command = row.get('command', [])
        check(isinstance(command, list) and all(isinstance(c, str) for c in command),
              f'check {idx+1} command format')
        if idx in (0,1,2,3,4,5,6,7,9,11,13,15,17,19,20):
            cpu = 'SandyBridge' if idx in (0,1,2,3,7,9,11,13,15,17) else ('core2duo' if idx == 6 else 'Nehalem')
            check(command[:3] == ['<qemu-x86_64>','-cpu',cpu],
                  f'check {idx+1} CPU and emulator invocation')
        if idx in (8,10,12,14,16,18):
            check(command and command[0].startswith('<tree>/'),
                  f'check {idx+1} native invocation')
    if len(rows) == 21:
        check('Illegal instruction' in rows[1].get('stderr', '') and
              'Illegal instruction' in rows[2].get('stderr', ''), 'AVX2/FMA SIGILL diagnostics')
        check('P11 host feature mask=3 (SSE2=1 AVX1=1)' in rows[3].get('stdout', '') and
              all(x in rows[3].get('stdout','') for x in (
                  'PASS FIR tier=avx1', 'PASS SDM tier=avx1',
                  'P11 kernel unit suite PASS')), 'AVX1 FIR/SDM QEMU unit execution')
        check('P11 host feature mask=1 (SSE2=1 AVX1=0)' in rows[4].get('stdout','') and
              'UNRUN tier=avx1 unavailable hardware/compiler' in rows[4].get('stdout','') and
              'PASS SDM tier=sse2' in rows[4].get('stdout',''), 'Nehalem SSE2 and AVX1 rejection')
        for i in (5,6):
            check('SoX_ng v' in rows[i].get('stdout',''),f'legacy CLI startup {i}')
        check('requested DSD FIR kernel tier is unavailable' in rows[19].get('stderr',''),
              'forced FIR diagnostic')
        check('requested DSD SDM kernel tier is unavailable' in rows[20].get('stderr',''),
              'forced SDM diagnostic')
    binaries = receipt.get('binary_sha256',{})
    check(set(binaries) == {'unit','sox','candidate'} and
          all(HEX64.fullmatch(str(value)) for value in binaries.values()),
          'recorded executable fingerprints')

    matches = 0
    digest_families = {}
    for family, start in (('SDM',7),('FIR',13)):
        family_values = {}
        for index, tier in enumerate(('scalar','sse2','avx1')):
            pair = rows[start + index*2:start + index*2 + 2]
            if len(pair) != 2:
                check(False, f'{family}/{tier} pair missing')
                continue
            values = [r.get('output_sha256') for r in pair]
            check(all(isinstance(x,str) and HEX64.fullmatch(x) for x in values),
                  f'{family}/{tier} output hash format')
            check(values[0] == values[1],f'{family}/{tier} native/QEMU mismatch')
            check('SandyBridge' in pair[0].get('command',[]), f'{family}/{tier} CPU model')
            check(pair[1].get('command',[''])[0].startswith('<tree>/'),
                  f'{family}/{tier} native command')
            if values[0] == values[1]:matches += 1
            family_values[tier] = values[0]
        digest_families[family] = family_values
    check(digest_families['SDM'].get('scalar') != digest_families['SDM'].get('avx1'),
          'SDM scalar/vector distinction absent')

    snap_root = RESULTS / 'P11_soak_per_family_2026-10-11'
    state_files = set(snap_root.rglob('*.state'))
    indexed = set()
    num_states = 0
    for tier in ('scalar','sse2','avx1'):
        folder = snap_root/tier
        j = json.loads((folder/'soak.json').read_text())
        check(j.get('status') == 'PASS' and len(j.get('profiles',[])) == 3,
              f'{tier} soak summary')
        rates = set()
        for p in j.get('profiles',[]):
            rate = p.get('configuration',{}).get('native_hz')
            rates.add(rate)
            check(p.get('status') == 'PASS' and p.get('completed_audio_seconds') == 3600.,
                  f'{tier}/{rate} complete soak')
            snaps = p.get('snapshots', [])
            check(len(snaps) == 61, f'{tier}/{rate} snapshot count')
            check((folder/p['evidence']).is_file() and
                  digest(folder/p['evidence']) == p.get('evidence_sha256'),
                  f'{tier}/{rate} result-file hash')
            last_input, last_native = -1, -1
            for entry in snaps:
                filename = entry['file']
                f = folder/filename
                if not f.is_file():
                    check(False, f'{tier}/{rate} missing {filename}')
                    continue
                check(f not in indexed, f'duplicate snapshot {f.name}')
                indexed.add(f)
                num_states += 1
                check(digest(f) == entry['sha256'], f'{tier}/{rate} SHA {filename}')
                content = f.read_text()
                check(content.startswith('P10-continuation-v1\n'),
                      f'{tier}/{rate} state schema')
                fields = dict(line.split('=',1) for line in content.splitlines() if '=' in line)
                input_n, native_n = int(fields['input']), int(fields['native'])
                check((input_n >= last_input and native_n >= last_native) if filename.endswith('-final.state')
                      else (input_n > last_input and native_n > last_native),
                      f'{tier}/{rate} non-monotonic {filename}')
                last_input,last_native=input_n,native_n
            check(last_native == 3600 * rate, f'{tier}/{rate} final frames')
            check(last_input == 3600 * p['configuration']['source_hz'],
                  f'{tier}/{rate} final input frames')
        check(rates == {2822400,5644800,11289600}, f'{tier} three rates')
    check(num_states == 549 and indexed == state_files, 'soak 549 and no missing/extra states')
    return {'schema':'P11/replay-independent-adjudication/1',
            'status': 'PASS' if not errors else 'FAIL',
            'independent_qemu_rerun': False,
            'qemu_execution_source': 'operator-recorded, unchanged prior-adjudication qualifier',
            'qualifier_sha256': actual_qualifier,
            'recorded_qemu_checks': len(rows),
            'qemu_native_hash_pairs_matching':matches,
            'soak_snapshots_sha256_verified':num_states,
            'soak_groups':9,
            'checks': {'21_replay_rows':len(rows)==21,
                       'all_snapshots_indexed':num_states==549 and indexed==state_files},
            'errors':errors}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=audit()
    encoded=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        tmp=args.output.with_suffix('.tmp')
        tmp.write_text(encoded)
        tmp.replace(args.output)
    print(encoded,end='')
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':sys.exit(main())

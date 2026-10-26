#!/usr/bin/env python3
"""Private licensed-media P17 DSF whole-track functional evidence collector.

Does not include files, source names or PCM in public receipts. Never converts
an internal packed/expanded identity test into independent audio qualification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time
import math

ROOT=Path(__file__).resolve().parents[2]
CASE_SCHEMA='P17/commercial-full-file-case/1'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(8<<20),b''):h.update(chunk)
    return h.hexdigest()

def load(path):
    return json.loads(path.read_text(),parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))

def sanitized(stderr, source):
    for value in sorted({str(source), str(source.resolve()), source.name},
                        key=len, reverse=True):
        if value:
            stderr = stderr.replace(value, '<licensed-file>')
    return stderr[-2000:]


def atomic(path,row):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(row,sort_keys=True,indent=2,allow_nan=False)+'\n')
    os.replace(temp,path)


def functional_decode_pass(result, rc, profile, out, tier):
    """Apply the same P17 decoder acceptance conditions to new and reused evidence."""
    if rc != 0 or not isinstance(result, dict):
        return False
    rate = result.get('rate_hz')
    frames = result.get('native_frames')
    if (type(rate) is not int or rate not in (22579200, 45158400) or
        type(frames) is not int or frames <= 0 or
        type(result.get('pcm_frames')) is not int):
        return False
    return (result.get('status') == 'PASS_FUNCTIONAL_ONLY' and
            result.get('packed_expanded_equal') is True and
            result.get('channels') == 2 and
            result.get('profile') == profile and
            result.get('destination_hz') == out and
            result.get('kernel') == tier and
            result['pcm_frames'] == (frames * out + rate // 2) // rate)


ROW_FOR_NATIVE = {22579200: 'dsf-read-22579200', 45158400: 'dsf-read-45158400'}
NATIVE_FOR_LABEL = {512: 22579200, 1024: 45158400}


def decoder_profile_verdicts(profile_bases, rate_complete, reader_gate,
                             commercial_rows, row_profiles):
    """Bind each clock's decode profiles to that clock's own capability row.

    The previous form was a cartesian product over {mastering, wideband} x
    {v1, v2} x {512, 1024} whose verdict read `rate == 512 and ...`. That had
    two consequences worth naming. The four DSD1024 entries were false by
    literal, so they would have stayed false even if independent DSD1024 media
    had been supplied; the adjacent `missing_media` string read like a measured
    conclusion but merely restated the hardcode. And the product invented
    decode.wideband.v2.dsd512 and .dsd1024, which exist at no rate: src/dsd.c
    defines mastering v1, mastering v2 and wideband v1 only.

    Enumerating the reader gate's own PROFILE_IDS against the rates yields
    exactly the six decode ids that exist. Each verdict now requires that
    clock's functional completeness, a passing reader gate, commercial
    provenance on that clock's row, and that row qualifying the profile. A
    clock with no evidence reports false because its evidence is absent, and
    qualifies without a code change once that evidence exists.
    """
    verdicts = {}
    for label, native in sorted(NATIVE_FOR_LABEL.items()):
        row = ROW_FOR_NATIVE[native]
        for base in sorted(profile_bases):
            verdicts[f'{base}.dsd{label}'] = bool(
                rate_complete.get(native) and reader_gate == 'PASS' and
                commercial_rows.get(row) is True and
                row_profiles.get(row, {}).get(base) is True)
    return verdicts


def validate_reader_evidence(report_path, commercial_hashes, sox_path, reference_path):
    """Recompute P21 qualification from bound case receipts, never summary flags."""
    from p21_independent_reader import (CASE_SCHEMA, REPORT_SCHEMA, EXPECTED_ROWS,
        PROFILE_IDS, PROFILES, SELF_RATES, SELF_CONTAINERS, judge, summarize_cases,
        thresholds)

    report_path = report_path.resolve()
    report = load(report_path)
    if report.get('schema') != REPORT_SCHEMA:
        raise ValueError('unsupported reader evidence schema; rerun the gate')
    runner_path = Path(__file__).with_name('p21_independent_reader.py')
    if not runner_path.is_file() or report.get('runner_sha256') != sha(runner_path):
        raise ValueError('independent reader code changed since evidence was collected')
    if not sox_path.is_file() or report.get('sox_sha256') != sha(sox_path):
        raise ValueError('SoX binary changed since independent reader run')
    if not reference_path.is_file() or report.get('reference_sha256') != sha(reference_path):
        raise ValueError('reference binary changed since independent reader run')
    if report.get('commercial_media_sha256') != sorted(commercial_hashes):
        raise ValueError('commercial source hashes differ from P17 full-file receipts')
    case_index = report.get('case_receipts')
    if not isinstance(case_index, dict) or not case_index:
        raise ValueError('missing reader case index')
    if report.get('case_count') != len(case_index):
        raise ValueError('reader case count does not match index')
    if report.get('thresholds') != thresholds():
        raise ValueError('reader thresholds differ from current implementation')
    cases = []
    for rel, status in case_index.items():
        # Only exact P21 receipt basenames are permitted, not arbitrary paths.
        if not isinstance(rel, str) or not rel.startswith('cases/') or '/' in rel[6:]:
            raise ValueError('invalid receipt path')
        receipt = report_path.parent / rel
        if not receipt.is_file():
            raise ValueError(f'missing reader receipt: {rel}')
        c = load(receipt)
        if c.get('schema') != CASE_SCHEMA:
            raise ValueError(f'wrong reader case schema: {rel}')
        if c.get('status') != status or status != 'PASS' or c.get('failure_reasons') != []:
            raise ValueError(f'reader case is not PASS: {rel}')
        if (c.get('runner_sha256') != report['runner_sha256'] or
            c.get('sox_sha256') != report['sox_sha256'] or
            c.get('reference_sha256') != report.get('reference_sha256') or
            c.get('thresholds') != thresholds() or
            c.get('sox_exit') != 0 or c.get('reference_exit') != 0 or
            c.get('control_exit') != 0):
            raise ValueError(f'reader case executable or threshold mismatch: {rel}')
        source = c.get('source_sha256')
        control = c.get('control_sha256')
        if (not isinstance(source, str) or len(source) != 64 or
            not all(ch in '0123456789abcdef' for ch in source) or
            not isinstance(control, str) or len(control) != 64 or
            control == source):
            raise ValueError(f'invalid source/control identities: {rel}')
        if c.get('source_id') != source[:20]:
            raise ValueError(f'source ID mismatch: {rel}')
        if (c.get('container') not in SELF_CONTAINERS or
            c.get('native_hz') not in SELF_RATES or
            c.get('media_provenance') not in ('commercial', 'self-encoded') or
            c.get('capability_row') !=
                f'{c["container"]}-read-{c["native_hz"]}'):
            raise ValueError(f'invalid source row: {rel}')
        if (c['media_provenance'] == 'commercial' and
            (source not in commercial_hashes or c['container'] != 'dsf' or
             c['native_hz'] != 22579200 or c.get('stimulus_origin') != 'licensed-original')):
            raise ValueError(f'commercial provenance mismatched: {rel}')
        if c['media_provenance'] == 'self-encoded' and (
            source in commercial_hashes or
            c.get('stimulus_origin') != 'derived-from-licensed-pcm'):
            raise ValueError(f'self-encoded source provenance not qualified: {rel}')
        definitions = {pid: (flag, outputs[c['native_hz']])
                       for flag, pid, outputs in PROFILES}
        pid = c.get('profile_id')
        if pid not in PROFILE_IDS:
            raise ValueError(f'unknown profile: {rel}')
        flag, rate = definitions[pid]
        if (c.get('output_hz') != rate or
            c.get('cli_decode_flag') != (flag or '(default)') or
            not isinstance(c.get('seconds'), (int, float)) or
            not math.isfinite(c['seconds']) or c['seconds'] < 0.5):
            raise ValueError(f'invalid output profile or interval: {rel}')
        metrics = c.get('metrics')
        passed, problems = judge(metrics)
        if not passed:
            raise ValueError(f'invalid stored reader metrics in {rel}: {problems}')
        expected_frames = int(round(c['seconds'] * rate))
        if (not isinstance(metrics.get('frames_compared'), int) or
            not isinstance(metrics.get('expected_frames'), int) or
            metrics['expected_frames'] != expected_frames or
            abs(metrics['frames_compared'] - expected_frames) > 2):
            raise ValueError(f'incomplete reader interval: {rel}')
        expected_rel = f'cases/{source[:20]}-{c["container"]}-{pid}.json'
        if rel != expected_rel:
            raise ValueError(f'reader case path mismatch: {rel}')
        cases.append(c)
    if len(cases) != len({(c['source_sha256'], c['container'], c['profile_id']) for c in cases}):
        raise ValueError('duplicate reader source/profile case')
    # Every negative control must name another tested source in the same row.
    by_source = {(c['media_provenance'], c['capability_row'], c['source_sha256'])
                 for c in cases}
    for c in cases:
        if ((c['media_provenance'], c['capability_row'], c['control_sha256'])
                not in by_source):
            raise ValueError('negative control is not another tested source in the row')
    commercial = sorted({c['source_sha256'] for c in cases
                         if c['media_provenance'] == 'commercial'})
    self_encoded = sorted({c['source_sha256'] for c in cases
                           if c['media_provenance'] == 'self-encoded'})
    if (report.get('commercial_media_sha256') != commercial or
        report.get('self_encoded_media_sha256') != self_encoded or
        report.get('media_sha256') != sorted(commercial + self_encoded) or
        report.get('tracks') != len(commercial + self_encoded)):
        raise ValueError('media inventory does not match case receipts')
    rows, commercial_rows, profiles, provenance = summarize_cases(cases)
    if (report.get('rows_qualified') != rows or
        report.get('rows_qualified_commercial') != commercial_rows or
        report.get('row_profiles_qualified') != profiles or
        report.get('rows_by_provenance') != provenance):
        raise ValueError('row qualification/provenance does not match cases')
    complete = (EXPECTED_ROWS <= rows.keys() and
                all(rows[r] for r in EXPECTED_ROWS) and
                commercial_rows.get('dsf-read-22579200') is True)
    declared_profiles = {pid: bool(complete) and all(
        profiles[row].get(pid) is True for row in EXPECTED_ROWS)
        for pid in PROFILE_IDS}
    if report.get('profiles_qualified') != declared_profiles:
        raise ValueError('profile summary does not match case coverage')
    if report.get('independent_reader_and_audio_reference_gate') != ('PASS' if complete else 'INCOMPLETE'):
        raise ValueError('global reader verdict does not match case coverage')
    return report, rows, commercial_rows, profiles


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--media-root',type=Path,default=None,
        help='private licensed DSF directory; never copied to evidence')
    a.add_argument('--probe',type=Path,default=ROOT/'test/dsd_test_p17_dsf')
    a.add_argument('--results',type=Path,default=ROOT/'tests/dsd/results/P17_qualification_2026-10-21/media')
    a.add_argument('--expected-dsd512-tracks',type=int,default=12)
    a.add_argument('--expected-dsd1024-tracks',type=int,default=0,
        help='independent DSD1024 tracks required to bind that clock; 0 leaves it unevaluated')
    a.add_argument('--tiers',default='scalar')
    a.add_argument('--timeout-per-track',type=int,default=14400)
    a.add_argument('--require-media',action='store_true')
    a.add_argument('--reader-sox', type=Path, default=ROOT/'src/sox',
        help='SoX executable used by the independent reader')
    a.add_argument('--reader-reference', type=Path, default=Path('/usr/bin/ffmpeg'),
        help='reference executable used by the independent reader')
    a.add_argument('--independent-reader-evidence',type=Path,
        default=ROOT/'tests/dsd/results/P21_INDEPENDENT_READER_2026-10-24/independent-reader-evidence.json',
        help='verdict from tests/dsd/p21_independent_reader.py; absent means UNRUN')
    args=a.parse_args();args.probe=args.probe.resolve();args.results=args.results.resolve()
    if args.expected_dsd512_tracks<1 or args.expected_dsd1024_tracks<0 or args.timeout_per_track<1:
        a.error('track count and timeout must be positive')
    if not args.probe.is_file():a.error('DSF probe not built')
    tiers=args.tiers.split(',')
    if ('scalar' not in tiers or len(set(tiers))!=len(tiers) or any(x not in
        ('scalar','sse2','avx1','avx2','avx512') for x in tiers)):
        a.error('explicit unique supported tiers including scalar required')
    paths=[]
    if args.media_root is not None:
        root=args.media_root.resolve()
        if not root.is_dir():a.error('media directory missing')
        paths=sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower()=='.dsf')
    binary_sha=sha(args.probe);runner_sha=sha(Path(__file__))
    cases=[]
    for path in paths:
        full_sha=sha(path);token=full_sha[:20];source_bytes=path.stat().st_size
        for profile,out in (('mastering',176400),('wideband',705600)):
            for tier in tiers:
                dest=args.results/'full_file'/f'{token}-{profile}-{tier}.json'
                previous=load(dest) if dest.is_file() else None
                reuse=(previous is not None and
                    previous.get('schema')==CASE_SCHEMA and
                    previous.get('source_sha256')==full_sha and
                    previous.get('source_id')==token and
                    type(previous.get('source_bytes')) is int and
                    previous['source_bytes']==source_bytes and
                    previous.get('probe_sha256')==binary_sha and
                    previous.get('runner_sha256')==runner_sha and
                    previous.get('profile')==profile and previous.get('tier')==tier and
                    previous.get('status')=='PASS_FUNCTIONAL_ONLY' and
                    functional_decode_pass(previous.get('decoder'), previous.get('exit_code'),
                        profile, out, tier))
                if reuse:
                    cases.append(previous);print('REUSE',token,profile,tier,flush=True)
                    continue
                if previous is not None:
                    raise RuntimeError('refusing stale/mismatched media receipt overwrite '+str(dest))
                started=time.monotonic();cmd=[str(args.probe),str(path),profile,str(out),tier,'full']
                try:
                    proc=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,
                        text=True,timeout=args.timeout_per_track)
                    rc=proc.returncode;stderr=proc.stderr[-2000:]
                    result=json.loads(proc.stdout,parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x))) if rc==0 else None
                except (subprocess.TimeoutExpired,ValueError,json.JSONDecodeError) as ex:
                    result=None;rc=124;stderr=str(ex)
                passed=functional_decode_pass(result, rc, profile, out, tier)
                decode_wall=result.get('decode_wall_seconds') if result else None
                speed=(result['native_frames']/decode_wall
                    if decode_wall and decode_wall>0 else None)
                realtime=(speed/result['rate_hz'] if speed else None)
                stderr=sanitized(stderr,path)
                row=dict(schema=CASE_SCHEMA,
                    status='PASS_FUNCTIONAL_ONLY' if passed else 'FAIL',
                    source_sha256=full_sha,source_id=token,source_bytes=source_bytes,
                    profile=profile,tier=tier,probe_sha256=binary_sha,runner_sha256=runner_sha,
                    command=['test/dsd_test_p17_dsf','<licensed-file>',profile,str(out),tier,'full'],
                    exit_code=rc,elapsed_seconds=time.monotonic()-started,
                    stderr_tail=stderr,decoder=result,
                    instrumented_native_frames_per_second=speed,
                    instrumented_real_time_factor=realtime,
                    timing_scope='two independent decode contexts (packed+expanded); NOT shipping single-path throughput',
                    independent_reference_qualification='UNRUN_NOT_COLLECTED',
                    device_interoperability='NOT_CLAIMED')
                atomic(dest,row);cases.append(row)
                print(row['status'],token,profile,tier,flush=True)
    by_rate={rate:{x['source_sha256'] for x in cases if
        x['decoder'] is not None and x['decoder']['rate_hz']==rate}
        for rate in (22579200,45158400)}
    dsd512=by_rate[22579200];dsd1024=by_rate[45158400]
    r512=[x for x in cases if x['source_sha256'] in dsd512]
    failed=any(x['status']=='FAIL' for x in cases)
    complete=(not failed and len(dsd512)>=args.expected_dsd512_tracks and
        len(r512)==len(dsd512)*len(tiers)*2 and
        all(x['status']=='PASS_FUNCTIONAL_ONLY' for x in r512) and
        all(x['source_sha256'] in dsd512|dsd1024 for x in cases))
    reader_gate, reader_ref, row_profiles, commercial_rows = 'UNRUN', None, {}, {}
    if (args.independent_reader_evidence is not None and
            args.independent_reader_evidence.is_file()):
        try:
            reader, rows, commercial_rows, row_profiles = validate_reader_evidence(
                args.independent_reader_evidence, dsd512, args.reader_sox, args.reader_reference)
            reader_gate = reader['independent_reader_and_audio_reference_gate']
            reader_ref = dict(
                path=os.path.relpath(args.independent_reader_evidence.resolve(), ROOT),
                runner_sha256=reader['runner_sha256'],
                sox_sha256=reader['sox_sha256'],
                tracks=reader['tracks'], case_count=reader['case_count'],
                media_sha256_match=True)
        except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as ex:
            reader_gate = 'INVALID'
            reader_ref = dict(path=os.path.relpath(
                args.independent_reader_evidence.resolve(), ROOT),
                media_sha256_match=False, validation_error=str(ex))
    # Per-clock functional completeness, so each rate answers for itself
    # instead of inheriting DSD512's verdict.
    expected={22579200:args.expected_dsd512_tracks,45158400:args.expected_dsd1024_tracks}
    rate_complete={}
    for rate,sources in by_rate.items():
        entries=[x for x in cases if x['source_sha256'] in sources]
        want=expected[rate]
        rate_complete[rate]=bool(not failed and want>0 and len(sources)>=want and
            len(entries)==len(sources)*len(tiers)*2 and
            all(x['status']=='PASS_FUNCTIONAL_ONLY' for x in entries))
    from p21_independent_reader import PROFILE_IDS as READER_PROFILE_IDS
    profile_qualification=decoder_profile_verdicts(READER_PROFILE_IDS,rate_complete,
        reader_gate,commercial_rows,row_profiles)
    report=dict(schema='P17/commercial-decoder-evidence/1',
        probe_sha256=binary_sha,runner_sha256=runner_sha,
        host=dict(node=platform.node(),os=platform.platform(),machine=platform.machine()),
        expected_dsd512_tracks=args.expected_dsd512_tracks,
        expected_dsd1024_tracks=args.expected_dsd1024_tracks,
        rate_functional_complete={str(k):v for k,v in sorted(rate_complete.items())},
        distinct_dsd512_tracks=len(dsd512),distinct_dsd1024_tracks=len(dsd1024),
        case_count=len(cases),
        full_file_functional_gate='PASS' if complete else ('FAIL' if failed else 'UNRUN_OR_INCOMPLETE'),
        media_sha256=sorted(dsd512|dsd1024),
        case_receipts={f'full_file/{x["source_id"]}-{x["profile"]}-{x["tier"]}.json':x['status'] for x in cases},
        decoder_profile_qualified=profile_qualification,
        independent_reader_and_audio_reference_gate=reader_gate,
        independent_reader_evidence=reader_ref,
        missing_media=(None if rate_complete.get(45158400) else
            ('No independent DSD1024 licensed media provided'
             if args.expected_dsd1024_tracks<1 else
             f'DSD1024 evidence incomplete: {len(dsd1024)} of '
             f'{args.expected_dsd1024_tracks} expected tracks')),
        device_claims=[],public_capabilities_enabled=False,qualification='UNQUALIFIED',
        note='P17 full-file functional checks do not establish an independent audio oracle. P21 compares audio-band output from independently written readers on the recorded intervals; it does not exhaustively certify parsing behavior, filter equivalence or device interoperability.')
    atomic(args.results/'commercial-decode-evidence.json',report)
    print('MEDIA',report['full_file_functional_gate'],len(dsd512),'DSD512 tracks')
    return 0 if (complete or not args.require_media) and not failed else 1
if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
"""Executable one-encoder contract at all five native DSD bit clocks.

Synthetic audio only. Assert both the chosen route and the actual output:
exact/native pins, planner/runtime gain parity, override semantics, retired
selector refusal, low-level legacy isolation, and repeatable native bits.
This is a bounded regression gate, not a replacement for music-library soaks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import wave

NATIVE = (2822400, 5644800, 11289600, 22579200, 45158400)
EXPECTED_DB = -20 * math.log10(.9)


def require(test, reason, run=None):
    if not test:
        raise AssertionError(reason + (f'\n{run.stderr[-1400:]}' if run else ''))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audio(path):
    hz, n = 176400, round(.028 * 176400)
    samples = bytearray()
    for i in range(n):
        window = min(1., i/(hz*.003), (n-1-i)/(hz*.003))
        x = .23 * window * (math.sin(2*math.pi*997*i/hz) +
                            .29*math.cos(2*math.pi*2347*i/hz))
        samples.extend(struct.pack('<i', round(x * (2**31-1))))
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(4)
        out.setframerate(hz)
        out.writeframes(samples)


def run(sox, *args):
    return subprocess.run([str(sox), *map(str, args)], capture_output=True,
        text=True, stdin=subprocess.DEVNULL, timeout=150,
        env={**os.environ, 'SOX_OPTS': '', 'OMP_NUM_THREADS': '1'})


def plan(sox, *args):
    result = run(sox, '--plan', *args)
    require(result.returncode == 0, 'planner failed', result)
    return json.loads(result.stdout)


def test(sox, root):
    wav = root/'input.wav'
    audio(wav)
    input_hash = sha(wav)
    rows = []
    for hz in NATIVE:
        suffix = hz//44100
        ident = f'encode.mastering.dsd{suffix}'
        output = root/'out.dsf'
        receipt = root/'receipt.json'
        prior = None
        for clip in ('warn', 'error'):
            selected = plan(sox, '--dsd-clip', clip, wav, '-r', hz, output)
            require(selected['encoder']['id'] == ident and selected['executable'],
                    f'DSD{suffix}: nonmastering/unsupported planned encoder')
            require(selected['policy']['encode'] == 'mastering',
                    f'DSD{suffix}: wrong user-facing encoder choice')
            certificate=selected['encoder']['certificate_sha256']
            require((certificate is None) if hz>=22579200 else
                    (isinstance(certificate,str) and len(certificate)==64),
                    f'DSD{suffix}: unsupported or missing coefficient certificate')
            require(abs(selected['encoder']['planned_linear_gain']-.9) < 1e-14,
                    f'DSD{suffix}/{clip}: missing default 0.9 gain in plan')
            require(selected['encoder']['warning_clip_ceiling'] ==
                    (.45 if clip=='warn' else None),
                    f'DSD{suffix}/{clip}: incorrect clip policy')
            for kind, flags in (('default',()),
                                ('name',('--encode','mastering')),
                                ('pin',('--encode',ident))):
                cmd = run(sox, *flags, '--dsd-clip', clip, '--report', receipt,
                          wav, '-r', hz, output)
                require(cmd.returncode==0 and output.is_file() and receipt.is_file(),
                        f'DSD{suffix}/{clip}/{kind}: encode failed', cmd)
                encoder = json.loads(receipt.read_text())['processing']['encoder']
                require(len(encoder)==1 and encoder[0]['profile_id']==ident,
                        f'DSD{suffix}/{clip}/{kind}: wrong runtime profile')
                certificate=encoder[0]['coefficient_certificate_sha256']
                require((certificate is None) if hz>=22579200 else
                        (isinstance(certificate,str) and len(certificate)==64),
                        f'DSD{suffix}/{clip}/{kind}: incorrect reported certificate')
                require(abs(encoder[0]['headroom_applied_db']-EXPECTED_DB)<1e-10,
                        f'DSD{suffix}/{clip}/{kind}: runtime gain changed')
                require(int(encoder[0]['clipped_interpolated_samples'])==0,
                        f'DSD{suffix}/{clip}/{kind}: quiet fixture clipped')
                digest = sha(output)
                if prior is None: prior = digest
                require(digest==prior,
                        f'DSD{suffix}/{clip}/{kind}: selected mastering bits differ')
                rows.append({'rate':hz,'clip':clip,'selection':kind,
                             'profile_id':ident,'sha256':digest})
        # Local effect selection agrees with the implicit mastering stage.
        local = run(sox, '--dsd-clip','error',wav,'-r',hz,output,
                    'pcmdsd','-p',ident,str(hz))
        require(local.returncode==0 and sha(output)==prior,
                f'DSD{suffix}: local pcmdsd selection differs', local)
        fixed = plan(sox, '--dsd-clip','error','--headroom','0',
                     wav,'-r',hz,output)
        require(fixed['encoder']['planned_linear_gain']==1,
                f'DSD{suffix}: explicit unity did not replace default gain')
        changed = run(sox,'--dsd-clip','error','--headroom','0',
                      wav,'-r',hz,output)
        require(changed.returncode==0 and sha(output)!=prior,
                f'DSD{suffix}: fixed override produced unchanged bits',changed)
        unity_digest = sha(output)
        measured = plan(sox, '--auto-headroom', wav,'-r',hz,output)
        require(measured['encoder']['planned_linear_gain'] is None,
                f'DSD{suffix}: auto headroom unexpectedly uses default gain')
        auto = run(sox,'--auto-headroom','--dsd-clip','error','--report',receipt,
                   wav,'-r',hz,output)
        require(auto.returncode==0 and sha(output)==unity_digest,
                f'DSD{suffix}: quiet auto-headroom differs from explicit unity',auto)
        auto_report = json.loads(receipt.read_text())['processing']['encoder']
        require(len(auto_report)==1 and abs(auto_report[0]['headroom_applied_db'])<1e-10,
                f'DSD{suffix}: quiet auto-headroom must be unity')
        rows.append({'rate':hz,'selection':'headroom override',
                     'fixed_gain':fixed['encoder']['planned_linear_gain'],
                     'auto_gain_db':auto_report[0]['headroom_applied_db']})

        for invalid in (f'encode.mastering.v1.dsd{suffix}',
                        f'encode.mastering.v2.dsd{suffix}',
                        'experimental'):
            output.unlink(missing_ok=True)
            denied = run(sox,'--encode',invalid,wav,'-r',hz,output)
            require(denied.returncode!=0 and not output.exists(),
                    f'DSD{suffix}: retired encoder was accepted: {invalid}',denied)
        other = NATIVE[0] if hz!=NATIVE[0] else NATIVE[1]
        output.unlink(missing_ok=True)
        denied = run(sox,'--encode',f'encode.mastering.dsd{other//44100}',
                     wav,'-r',hz,output)
        require(denied.returncode!=0 and not output.exists(),
                f'DSD{suffix}: wrong-clock pin accepted',denied)
        output.unlink(missing_ok=True)
        denied = run(sox,wav,'-r',hz,output,'pcmdsd','-p','legacy',str(hz))
        require(denied.returncode!=0 and not output.exists(),
                f'DSD{suffix}: pcmdsd -p legacy is not mastering',denied)

    # Legacy is a low-level effect route. The composite planner must not
    # claim that naming it without explicit effects can produce native DSD.
    output = root/'legacy.dsf'
    implicit = plan(sox,'--encode','legacy',wav,'-r','dsd64',output)
    require(not implicit['executable'], 'implicit legacy route incorrectly executable')
    require(implicit['encoder']['planned_linear_gain'] is None,
            'implicit legacy incorrectly receives mastering gain')
    refuse = run(sox,'--encode','legacy',wav,'-r','dsd64',output)
    require(refuse.returncode!=0 and not output.exists(),
            'implicit legacy illegally emitted output',refuse)
    # Explicit legacy route, with and without --encode legacy, must be
    # independent of mastering clip policy and default attenuation.
    hashes=[]
    for named in (False,True):
        for policy in ('warn','error'):
            options=['--encode','legacy'] if named else []
            graph=plan(sox,*options,'--dsd-clip',policy,wav,'-r',
                      'dsd64',output,'rate','-v','2822400','sdm','-f','sdm-8')
            require(graph['executable'] and graph['encoder']['planned_linear_gain'] is None,
                    'legacy effect received mastering gain or became unavailable')
            proc=run(sox,*options,'--dsd-clip',policy,wav,'-r','dsd64',output,
                     'rate','-v','2822400','sdm','-f','sdm-8')
            require(proc.returncode==0 and output.is_file(),
                    'explicit legacy conversion failed',proc)
            hashes.append(sha(output))
    require(len(set(hashes))==1,
            'legacy bits changed with --encode or mastering clip policy')
    output.unlink(missing_ok=True)
    forbidden = run(sox,'--headroom','1',wav,'-r','dsd64',output,
                    'rate','-v','2822400','sdm','-f','sdm-8')
    require(forbidden.returncode!=0 and not output.exists(),
            'legacy accepted mastering-only headroom',forbidden)
    require(sha(wav)==input_hash, 'encoder modified source PCM')
    rows.append({'route':'legacy', 'sha256':hashes[0],
                 'headroom':'not applied','policy':'ignored for low-level sdm'})
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sox',required=True,type=Path)
    parser.add_argument('--results',type=Path)
    args=parser.parse_args()
    sox=args.sox.resolve()
    require(sox.is_file(), 'SoX executable absent')
    with tempfile.TemporaryDirectory(prefix='sox-one-encoder-') as temp:
        rows=test(sox,Path(temp))
    if args.results:
        args.results.parent.mkdir(parents=True,exist_ok=True)
        args.results.write_text(json.dumps({'schema':'sox.dsd.one_encoder.111/1',
            'binary_sha256':sha(sox),'cases':rows,'passed':len(rows)},indent=2)+'\n')
    print(json.dumps({'status':'PASS','checked':len(rows),'rates':list(NATIVE)}))


if __name__=='__main__':
    main()

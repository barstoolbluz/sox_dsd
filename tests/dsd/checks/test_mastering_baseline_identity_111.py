#!/usr/bin/env python3
"""Compare default warn-mode DSF bits with the shipped source snapshot.

Generates one deterministic stereo PCM vector, encodes with each separately
built binary, and compares complete DSF byte hashes. Pure-Python, no external
music or optional dependencies. DSD64/128/256 must match byte-for-byte;
DSD512/1024 intentionally use different high-rate SDM-8 zeros.
"""
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

RATES=(2822400, 5644800, 11289600, 22579200, 45158400)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def sample_file(path):
    rate, n = 96000, 24000
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(2)
        out.setsampwidth(4)
        out.setframerate(rate)
        frames=bytearray()
        for index in range(n):
            t=index/rate
            fade=min(1., index/2500., (n-index-1)/2500.)
            for channel in (0,1):
                v=fade*(.28*math.sin(2*math.pi*997*t+channel*.27)+
                        .21*math.cos(2*math.pi*13111*t-channel*.12)+
                        .06*math.sin(2*math.pi*(130*t+350*t*t)))
                frames.extend(struct.pack('<i', round((2**31-1)*v)))
        out.writeframes(frames)
    return sha(path.read_bytes())


def encode(binary, source, rate, output):
    process=subprocess.run([str(binary), '--dsd-clip','warn',str(source),
        '-r',str(rate),'-t','dsf',str(output)],capture_output=True,
        env={**os.environ,'SOX_OPTS':'','OMP_NUM_THREADS':'1'},
        stdin=subprocess.DEVNULL,timeout=120)
    if process.returncode:
        raise RuntimeError(f'{binary}: DSD{rate//44100} status {process.returncode}: '
            +process.stderr.decode(errors='replace')[-700:])
    raw=output.read_bytes()
    return sha(raw),len(raw)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',required=True,type=Path)
    ap.add_argument('--current',required=True,type=Path)
    ap.add_argument('--results',type=Path)
    args=ap.parse_args()
    for binary in (args.baseline,args.current):
        if not binary.is_file():ap.error(f'missing executable: {binary}')
    with tempfile.TemporaryDirectory(prefix='sox-encoder-identity-') as temp:
        input_path=Path(temp)/'source.wav'
        input_sha=sample_file(input_path)
        result=[]
        for native in RATES:
            old,old_size=encode(args.baseline,input_path,native,
                Path(temp)/f'baseline-{native}.dsf')
            new,new_size=encode(args.current,input_path,native,
                Path(temp)/f'current-{native}.dsf')
            same=old==new and old_size==new_size
            expected=native<=11289600
            if same!=expected:
                raise AssertionError(f'DSD{native//44100}: '
                    f'bitstream identity={same}, expected={expected}')
            result.append({'rate':native,'baseline_sha256':old,
                'current_sha256':new,'baseline_bytes':old_size,
                'current_bytes':new_size,'identical':same})
    receipt={'schema':'sox.dsd.baseline-identity/1',
        'input_sha256':input_sha,'baseline_exe_sha256':sha(args.baseline.read_bytes()),
        'current_exe_sha256':sha(args.current.read_bytes()),'results':result}
    if args.results:
        args.results.parent.mkdir(parents=True,exist_ok=True)
        args.results.write_text(json.dumps(receipt,indent=2)+'\n')
    for item in result:
        print('DSD{} {} {}'.format(item['rate']//44100,
            'IDENTICAL' if item['identical'] else 'DIFFERENT',item['current_sha256']))
    print('Baseline identity PASS')


if __name__=='__main__':
    main()

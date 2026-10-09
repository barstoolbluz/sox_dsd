#!/usr/bin/env python3
"""Isolated six-channel small-buffer DFF repack A/B, never a P05 gate by default.

Each arm uses identical bytes, flags, compiler settings and buffered writes.
JSON intentionally omits host-specific absolute paths and stderr paths.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
import tempfile
from bench_read_p02 import dff_bytes, run, summarize


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--control', type=Path, required=True)
    ap.add_argument('--candidate', type=Path, required=True)
    ap.add_argument('--control-identity', default='P06-before-hotfix')
    ap.add_argument('--pairs', type=int, default=40)
    ap.add_argument('--warmups', type=int, default=3)
    ap.add_argument('--frames', type=int, default=1048576)
    ap.add_argument('--cpu', type=int)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if args.pairs < 15 or args.warmups < 1 or args.frames % 32768:
        ap.error('minimum 15 pairs, 1 warmup; frames multiple of 32768')
    if not args.control.is_file() or not args.candidate.is_file():
        ap.error('both built binaries required')
    measurements = {'control': [], 'candidate': []}
    outputs = {'control': set(), 'candidate': set()}
    failures = []
    order = random.Random(0xA716)
    with tempfile.TemporaryDirectory(dir='/dev/shm' if Path('/dev/shm').is_dir() else None) as tmp:
        tmp = Path(tmp)
        source = tmp/'input.dff'
        source.write_bytes(dff_bytes(6, args.frames))
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        for idx in range(args.warmups+args.pairs):
            variants = ('control','candidate') if order.randrange(2) else ('candidate','control')
            for variant in variants:
                path = tmp / (variant+'.dff')
                if path.exists(): path.unlink()
                result = run(args.control if variant=='control' else args.candidate,
                             source, path, 32, 'repack', args.cpu)
                if result['exit']:
                    failures.append({'variant':variant,'repetition':idx,'exit':result['exit']})
                else:
                    outputs[variant].add(result['output_sha256'])
                    if idx >= args.warmups:
                        measurements[variant].append(result['cpu_seconds'])
    verdict = summarize(measurements['control'], measurements['candidate'], 0xA716) if not failures else None
    output = {'comparison':'P06 original versus isolated P06 small-buffer DFF reader correction',
              'control_identity': args.control_identity,
              'is_p05_certification': args.control_identity == '149ea582',
              'source_sha256': source_hash,
              'control_binary_sha256': hashlib.sha256(args.control.read_bytes()).hexdigest(),
              'candidate_binary_sha256': hashlib.sha256(args.candidate.read_bytes()).hexdigest(),
              'workload':'dff-6ch-repack-small', 'buffersize_samples':32,
              'frames_per_channel':args.frames, 'pairs':args.pairs,
              'warmups':args.warmups, 'cpu':args.cpu,
              'control_cpu_seconds': measurements['control'],
              'candidate_cpu_seconds':measurements['candidate'],
              'output_sha256_by_arm':{key:sorted(value) for key,value in outputs.items()},
              'output_equivalent':len(outputs['control'])==1 and outputs['control']==outputs['candidate'],
              'summary':verdict, 'failures':failures}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'summary':verdict,'output_equivalent':output['output_equivalent'],
                      'failures':failures},indent=2))
    return 1 if failures or not output['output_equivalent'] else 0

if __name__=='__main__':
    raise SystemExit(main())

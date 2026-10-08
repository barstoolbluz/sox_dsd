#!/usr/bin/env python3
"""Record actual commands, raw output and exits; never infer completion."""
import argparse, datetime, json, os, pathlib, shlex, subprocess, sys, time
p=argparse.ArgumentParser()
p.add_argument('--cwd',type=pathlib.Path,required=True)
p.add_argument('--results',type=pathlib.Path,required=True)
p.add_argument('name'); p.add_argument('command',nargs=argparse.REMAINDER)
a=p.parse_args(); a.results.mkdir(parents=True,exist_ok=True)
command=a.command[1:] if a.command[:1]==['--'] else a.command
base=a.results/a.name
record=dict(command=command,cwd=str(a.cwd.resolve()),start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),exit=None,env={k:os.environ[k] for k in ('CFLAGS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','LC_ALL') if k in os.environ})
base.with_suffix('.command.txt').write_text(shlex.join(command)+'\n')
base.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n')
start=time.perf_counter()
with base.with_suffix('.log').open('wb') as log:
    child=subprocess.Popen(command,cwd=a.cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    while chunk := child.stdout.read(65536):
        log.write(chunk); log.flush()
    child.wait()
record.update(exit=child.returncode,wall_seconds=time.perf_counter()-start,end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
base.with_suffix('.exit').write_text(str(child.returncode)+'\n')
base.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
if child.returncode:
    print(base.with_suffix('.log').read_text(errors='replace')[-5000:],flush=True)
sys.exit(child.returncode)

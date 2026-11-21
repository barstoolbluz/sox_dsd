"""Identity, durable publication and constrained file-system helpers."""
from __future__ import annotations
import contextlib,fcntl,hashlib,json,os,platform,shutil,stat,subprocess,tempfile,time
from pathlib import Path

CHUNK=1<<20

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(CHUNK),b''): h.update(b)
    return h.hexdigest()

def digest_json(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def code_fingerprint(root):
    root=Path(root)
    return {p.relative_to(root).as_posix():digest(p) for p in sorted(root.rglob('*.py')) if p.is_file()}

def syncdir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def atomic_json(path,obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.new',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(obj,f,indent=2,sort_keys=True,allow_nan=False)
            f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(name,path);syncdir(path.parent)
    finally:
        if os.path.exists(name):os.unlink(name)

def read_json(path):
    with open(path,encoding='utf-8') as f:return json.load(f)

@contextlib.contextmanager
def lock(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with open(path,'ab') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        yield

def run_logged(cmd,log,env=None,timeout=3600):
    log=Path(log)
    began=time.monotonic()
    with open(log,'wb') as dest:
        try:
            cp=subprocess.run([str(v) for v in cmd],stdout=dest,stderr=subprocess.STDOUT,env=env,timeout=timeout,check=False)
        except subprocess.TimeoutExpired:
            dest.write(b'\nHARNESS TIMEOUT\n');dest.flush();os.fsync(dest.fileno())
            raise RuntimeError('SoX command timed out; see '+str(log))
        dest.flush();os.fsync(dest.fileno())
    if cp.returncode:raise RuntimeError('SoX command failed ('+str(cp.returncode)+'); see '+str(log))
    return time.monotonic()-began

def version_info():
    import numpy
    import scipy
    return {'python':platform.python_version(),'platform':platform.platform(),'numpy':numpy.__version__,'scipy':scipy.__version__}

def safe_child_directory(path,base):
    p=Path(path).resolve();b=Path(base).resolve()
    if p==b or b not in p.parents:raise ValueError('output directory must be strictly inside requested results root')
    return p

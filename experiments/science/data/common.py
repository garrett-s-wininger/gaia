"""Pinned real package data and bounded evidence helpers for science prototypes."""
import contextlib,fcntl,hashlib,json,os,platform,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'experiments/artifacts/followthrough'))
from run_catalogue import source_rows

def digest(body):return hashlib.sha256(body).hexdigest()
def read_corpus(index,payload):
    raw=payload.read_bytes();rows=source_rows(index);objects={}
    for row in rows:
        body=raw[row['offset']:row['offset']+row['size']]
        if digest(body)!=row['sha256']:raise ValueError('producer content mismatch')
        objects.setdefault(row['sha256'],body)
    return rows,raw,objects

@contextlib.contextmanager
def measured(lock):
    if lock is None:yield;return
    lock.parent.mkdir(parents=True,exist_ok=True)
    with lock.open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX);yield

def pins(paths):return {p.name:digest(p.read_bytes()) for p in paths}
def save(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')
def publish(output,data,summary,validation,sources):
    save(output/'results.json',data)
    raw=(output/'results.json').resolve();identity={'path':raw.relative_to(ROOT).as_posix() if raw.is_relative_to(ROOT) else raw.name,'bytes':raw.stat().st_size,'sha256':digest(raw.read_bytes())}
    save(output/'summary.json',summary);save(output/'validation.json',validation);save(output/'raw-identity.json',identity)
    save(output/'provenance.json',{'python':sys.version,'platform':platform.platform(),'implementation_sha256':pins(sources),'raw_identity':identity,'measurement':'Short per-case shared advisory lock; warm host pages; unrelated preparation/host work may overlap. Algorithms in Python unless declared otherwise.'})
    return identity

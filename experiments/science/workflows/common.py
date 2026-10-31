"""Shared measurement helpers; lock only one measured operation at a time."""
import contextlib,fcntl,hashlib,json,platform,subprocess,sys,time
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def digest(body):return hashlib.sha256(body).hexdigest()
def filepin(path):return digest(Path(path).read_bytes())
def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2)+'\n')
def sources():return {p.name:filepin(p) for p in sorted(HERE.iterdir()) if p.suffix in ('.py','.odin')}
@contextlib.contextmanager
def lock(path):
    with Path(path).open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX);yield
def timed(function):
    begin=time.perf_counter_ns();cpu=time.process_time_ns();value=function()
    return dict(wall_ns=time.perf_counter_ns()-begin,parent_cpu_ns=time.process_time_ns()-cpu,value=value)
def checked(command,**kw):
    return subprocess.run(list(map(str,command)),capture_output=True,check=True,**kw)
def provenance():return dict(python=sys.version,platform=platform.platform(),sources=sources())
def publish(output,data):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);save(output/'results.json',data)
    raw=output/'results.json'
    location=raw.relative_to(ROOT).as_posix() if raw.is_relative_to(ROOT) else raw.as_posix()
    entry=dict(path=location,bytes=raw.stat().st_size,sha256=filepin(raw))
    save(output/'raw-identity.json',entry);return entry

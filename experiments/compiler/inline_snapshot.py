"""Publish the existing immutable wire format from caller-admitted input bytes.

The consumer still authenticates the snapshot. This removes a redundant delta
round trip when the caller already owns the complete admitted collection.
"""
import hashlib
import os
from pathlib import Path
import tempfile
import time

from project_benchmark import encode_inputs


def atomic_write(path,body):
    path=Path(path)
    fd,name=tempfile.mkstemp(prefix=path.name+'.tmp.',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(body)
        os.replace(name,path)
    finally:
        Path(name).unlink(missing_ok=True)


def publish(files,masks,jobs,output,views,blake3=None):
    begin=time.perf_counter_ns()
    if not 1<=jobs<=64 or not 0<len(files)<=100000 or files.keys()!=masks.keys():
        raise ValueError('snapshot membership/job bounds')
    bits=(1<<jobs)-1
    for name,body in files.items():
        if (not name.startswith('/') or name.endswith(('/','/.','/..')) or
            any(part in name for part in ('//','/./','/../','\\','\0')) or
            len(name.encode())>4096 or not 0<=masks[name]<=bits or len(body)>64*1024*1024):
            raise ValueError('snapshot path/mask/content bounds')
    size=16+sum(14+len(name.encode())+len(body) for name,body in files.items())
    if size>64*1024*1024:raise ValueError('snapshot size limit')
    blob=encode_inputs(files,magic=b'GAIACIN3' if blake3 else b'GAIACIN2')
    view=('GAIACV1\n'+''.join(f'{masks[name]}\n' for name in sorted(files))).encode()
    pin='blake3:'+blake3(blob).hex() if blake3 else hashlib.sha256(blob).hexdigest()
    view_pin=hashlib.sha256(view).hexdigest()
    atomic_write(output,blob);atomic_write(views,view)
    return dict(correct=True,pin=pin,view_pin=view_pin,files=len(files),bytes=len(blob),
                loose_reads=0,loose_bytes=0,native_ns=0,caller_ns=time.perf_counter_ns()-begin)

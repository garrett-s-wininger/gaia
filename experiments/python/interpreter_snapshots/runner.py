#!/usr/bin/env python3
"""Single-threaded Linux fork-template research runner; not a disk snapshot."""
import importlib
import json
import os
from pathlib import Path
import random
import resource
import sys
import threading
import time

MAX_REQUEST=65536
MAX_REPLY=1048576

def memory():
    wanted={'Rss','Pss','Private_Dirty','Private_Clean','Shared_Clean','Shared_Dirty'}
    return {key:int(value.split()[0])*1024 for key,value in
            (line.split(':',1) for line in Path('/proc/self/smaps_rollup').read_text().splitlines() if ':' in line)
            if key in wanted}

def admit_template():
    if threading.active_count()!=1 or len(list(Path('/proc/self/task').iterdir()))!=1:
        raise RuntimeError('template must have exactly one OS thread')
    # A live socket/database/file must have an explicit rebuild hook; this
    # prototype accepts none. /proc enumeration's temporary fd is already closed.
    opened=[]
    for path in Path('/proc/self/fd').iterdir():
        if int(path.name)>2:
            try:opened.append((path.name,os.readlink(path)))
            except FileNotFoundError:pass
    if opened:raise RuntimeError('template has unapproved open resources: '+str(opened))

def bind(request):
    if set(request)-{'cwd','argv','environment','token','marker','fail'}:
        raise ValueError('unknown request field')
    os.chdir(request['cwd']);sys.argv=list(request['argv'])
    os.environ.clear();os.environ.update(request['environment'])
    # Only the module-global generator is reset here. User Random instances,
    # native RNGs and arbitrary library resources need consumer-specific hooks.
    random.seed()

def execute(module,request):
    bind(request)
    if request.get('marker'):
        import atexit
        atexit.register(Path(request['marker']).write_text,'normal-finalization')
    if request.get('fail'):raise RuntimeError('injected request failure')
    result=module.run(request)
    return dict(ok=True,result=result,nonce=random.getrandbits(128),pid=os.getpid(),memory=memory())

def emit(value):
    raw=json.dumps(value,separators=(',',':'))
    if len(raw)>MAX_REPLY:raise ValueError('reply too large')
    print(raw,flush=True)

def main():
    mode,stage,module_name,config_path=sys.argv[1:]
    config=json.loads(Path(config_path).read_text())
    sys.path.insert(0,str(Path(config['fixture_parent']).resolve()))
    sys.path.insert(0,config['adapter_root'])
    module=importlib.import_module(module_name)
    def no_network(event,args):
        if event in ('socket.connect','socket.bind','socket.getaddrinfo'):
            raise RuntimeError('network is outside this snapshot fixture')
    sys.addaudithook(no_network)
    if config.get('template_cwd'):os.chdir(config['template_cwd'])
    start=time.perf_counter();module.prepare(stage,config)
    def check_identity(request):
        if config.get('template_cwd') and request['cwd']!=config['template_cwd']:
            raise ValueError('request cwd differs from admitted template')
        for key,value in config.get('protected_environment',{}).items():
            if request['environment'].get(key)!=value:
                raise ValueError('request environment differs from admitted template: '+key)
    if mode=='once':
        raw=sys.stdin.buffer.readline(MAX_REQUEST+1)
        if len(raw)>MAX_REQUEST:raise ValueError('request too large')
        request=json.loads(raw);check_identity(request)
        emit(execute(module,request))
        return 0
    if mode!='server':raise ValueError('unknown runner mode')
    admit_template()
    emit(dict(ready=True,prepare_seconds=time.perf_counter()-start,memory=memory(),pid=os.getpid(),threads=1))
    while True:
        raw=sys.stdin.buffer.readline(MAX_REQUEST+1)
        if not raw:return 0
        if len(raw)>MAX_REQUEST:raise ValueError('request too large')
        request=json.loads(raw)
        if request=={'stop':True}:return 0
        admit_template()
        readfd,writefd=os.pipe();before=resource.getrusage(resource.RUSAGE_CHILDREN)
        pid=os.fork()
        if pid==0:
            os.close(readfd);os.close(0)
            try:
                check_identity(request);reply=execute(module,request);code=0
            except Exception as error:reply=dict(ok=False,error=type(error).__name__+': '+str(error));code=1
            with os.fdopen(writefd,'w') as stream:
                payload=json.dumps(reply,separators=(',',':'))
                if len(payload)>MAX_REPLY:raise ValueError('reply too large')
                stream.write(payload)
            # Return through main and sys.exit, allowing CPython finalizers and
            # atexit handlers. Do not substitute multiprocessing's os._exit.
            return code
        os.close(writefd)
        with os.fdopen(readfd,'rb') as stream:payload=stream.read(MAX_REPLY+1)
        _,status,usage=os.wait4(pid,0)
        if len(payload)>MAX_REPLY:raise ValueError('reply too large')
        try:reply=json.loads(payload)
        except Exception:reply=dict(ok=False,error='child produced no valid reply')
        reply.update(wait_status=os.waitstatus_to_exitcode(status),child_cpu_seconds=usage.ru_utime+usage.ru_stime,
                     child_maxrss_bytes=usage.ru_maxrss*1024)
        emit(reply)

if __name__=='__main__':
    raise SystemExit(main())

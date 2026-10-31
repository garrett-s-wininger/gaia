"""Linux sealed source generations shared by real Python compiler workers.

The broker's byte bound covers unique retained input objects, not total RSS or
producer/consumer transient allocations. Child workers retain private runtime
and compiler state. No arbitrary process snapshot is involved.
"""
from dataclasses import dataclass
import argparse
import fcntl
import hashlib
import json
import marshal
import mmap
import os
from pathlib import Path
import random
import struct
import subprocess
import sys
import sysconfig
import time


def sha(data):return hashlib.sha256(data).hexdigest()


@dataclass
class Entry:
    fd: int
    size: int
    leases: int=0


class Broker:
    def __init__(self,budget):self.budget=budget;self.entries={};self.bytes=0;self.leases={}
    def admit(self,body):
        pin=sha(body)
        if pin in self.entries:return pin
        if self.bytes+len(body)>self.budget:raise MemoryError('retained-input admission budget')
        fd=os.memfd_create('gaia-source-generation',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
        try:
            offset=0
            while offset<len(body):
                written=os.write(fd,memoryview(body)[offset:])
                if written<=0:raise OSError('input write failed')
                offset+=written
            fcntl.fcntl(fd,fcntl.F_ADD_SEALS,fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL)
        except BaseException:os.close(fd);raise
        self.entries[pin]=Entry(fd,len(body));self.bytes+=len(body);return pin
    def lease(self,pin):
        entry=self.entries[pin];fd=os.dup(entry.fd);entry.leases+=1;self.leases[fd]=pin;return fd
    def release(self,pin,fd):
        if self.leases.get(fd)!=pin:raise ValueError('lease ownership mismatch')
        entry=self.entries[pin]
        if entry.leases<1:raise ValueError('lease underflow')
        os.close(fd);entry.leases-=1;del self.leases[fd]
    def evict(self,pin):
        entry=self.entries[pin]
        if entry.leases:raise BlockingIOError('generation has active readers')
        os.close(entry.fd);self.bytes-=entry.size;del self.entries[pin]
    def close(self):
        if any(e.leases for e in self.entries.values()):raise BlockingIOError('active input leases')
        for entry in self.entries.values():os.close(entry.fd)
        self.entries.clear();self.bytes=0


def encode(rows):
    metadata=[];data=bytearray()
    for name,body in sorted(rows.items()):
        metadata.append([name,len(data),len(body)]);data.extend(body)
    header=json.dumps(metadata,separators=(',',':')).encode()
    return b'GASRC001'+struct.pack('<Q',len(header))+header+data


def decode(body):
    if len(body)<16 or bytes(body[:8])!=b'GASRC001':raise ValueError('source format')
    size=struct.unpack_from('<Q',body,8)[0]
    if size>1024*1024 or size>len(body)-16:raise ValueError('source header bounds')
    rows=json.loads(body[16:16+size]);base=16+size;seen=set()
    if len(rows)>10000:raise ValueError('source row count')
    for name,offset,length in rows:
        if not isinstance(name,str) or name in seen or not isinstance(offset,int) or not isinstance(length,int) or offset<0 or length<0 or offset+length>len(body)-base:raise ValueError('source row')
        seen.add(name)
    return rows,base


def compile_rows(body,rows,base,indices):
    digest=hashlib.sha256()
    for index in indices:
        if not isinstance(index,int) or not 0<=index<len(rows):raise ValueError('source selection')
        name,offset,length=rows[index]
        code=compile(memoryview(body)[base+offset:base+offset+length],name,'exec',dont_inherit=True,optimize=0)
        encoded=marshal.dumps(code);digest.update(struct.pack('<Q',len(encoded)));digest.update(encoded)
    return digest.hexdigest()


def worker(a):
    seals=fcntl.fcntl(a.fd,fcntl.F_GET_SEALS)
    required=fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK
    if seals&required!=required:raise ValueError('input is mutable')
    length=os.fstat(a.fd).st_size;body=None
    try:
        body=mmap.mmap(a.fd,length,access=mmap.ACCESS_READ) if a.mode=='shared' else os.pread(a.fd,length,0)
        if sha(body)!=a.pin:raise ValueError('input identity')
        rows,base=decode(body);print(json.dumps({'event':'READY','sources':len(rows),'bytes':len(body),'pid':os.getpid(),'cpu_ns':time.process_time_ns()}),flush=True)
        for line in sys.stdin:
            request=json.loads(line)
            if request.get('quit'):break
            if request.get('generation')!=a.pin:
                print(json.dumps({'ok':False,'error':'stale generation'}),flush=True);continue
            start=time.perf_counter_ns();cpu_start=time.process_time_ns()
            try:response={'ok':True,'sha256':compile_rows(body,rows,base,request['indices'])}
            except (SyntaxError,ValueError,TypeError) as error:response={'ok':False,'error_type':type(error).__name__}
            response['worker_ns']=time.perf_counter_ns()-start;response['cpu_ns']=time.process_time_ns()-cpu_start;print(json.dumps(response),flush=True)
        print(json.dumps({'event':'STOPPED','cpu_ns':time.process_time_ns()}),flush=True)
    finally:
        if isinstance(body,mmap.mmap):body.close()


def memory(pids):
    result={'rss_bytes':0,'pss_bytes':0,'scope':'Sequential current worker samples, not an atomic peak; producer and transient allocations excluded.'}
    for pid in pids:
        values={}
        for line in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines():
            fields=line.split()
            if fields and fields[0] in ('Rss:','Pss:'):values[fields[0]]=int(fields[1])*1024
        result['rss_bytes']+=values['Rss:'];result['pss_bytes']+=values['Pss:']
    return result


def dataset(source,limit):
    rows={};size=0
    for path in sorted(source.rglob('*.py')):
        relative=path.relative_to(source)
        if path.is_symlink() or any(p in {'test','tests','site-packages','dist-packages','__pycache__'} for p in relative.parts):continue
        body=path.read_bytes()
        if size+len(body)>limit:continue
        compile(body,relative.as_posix(),'exec',dont_inherit=True,optimize=0)
        rows[relative.as_posix()]=body;size+=len(body)
    if len(rows)<20:raise ValueError('source corpus too small')
    return rows


def run(a):
    a.work.mkdir(parents=True,exist_ok=False);prep_start=time.perf_counter_ns();data=dataset(a.source,a.limit);payload=encode(data);rows,base=decode(payload);preparation_ns=time.perf_counter_ns()-prep_start
    indices=[n for n,row in enumerate(rows) if row[2]>=1024][:a.units]
    expected=compile_rows(payload,rows,base,indices);pins={p.name:sha(p.read_bytes()) for p in [Path(__file__)]};observations=[]
    result={'schema_version':1,'status':'running','scope':'Real Python stdlib source, compile-only private workers. Shared sealed mappings vs private copies, both verify full pin. Common producer body is outside worker PSS snapshots. Logical retained-input budget is not total-memory quota. Cooperative leases are released after child exit; arbitrary untracked descriptor duplication is outside the broker contract.','python':sys.version,'sources':{k:sha(v) for k,v in data.items()},'implementation':pins,'producer_preparation_ns':preparation_ns,'observations':observations}
    a.output.mkdir(parents=True,exist_ok=True)
    def save():(a.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    save()
    for block in range(a.trials):
        modes=['private','shared'];random.Random(block).shuffle(modes)
        for mode in modes:
            with a.lock.open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                broker=Broker(len(payload)*2);processes=[];leases=[];ready=[];start=time.perf_counter_ns()
                try:
                    admitted=broker.admit(payload);admission_ns=time.perf_counter_ns()-start
                    for i in range(a.workers):
                        lease=broker.lease(admitted);leases.append(lease)
                        child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'worker','--fd',str(lease),'--pin',admitted,'--mode',mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(a.work/f'{mode}-{block}-{i}.stderr').open('w'),text=True,pass_fds=(lease,));processes.append(child)
                    for child in processes:
                        value=json.loads(child.stdout.readline());assert value['event']=='READY';ready.append(value)
                    ready_ns=time.perf_counter_ns()-start;snapshot=memory([p.pid for p in processes]);requests=[]
                    for request in range(a.requests):
                        begin=time.perf_counter_ns()
                        for child in processes:child.stdin.write(json.dumps({'generation':admitted,'indices':indices})+'\n');child.stdin.flush()
                        answers=[json.loads(child.stdout.readline()) for child in processes]
                        assert all(x.get('ok') and x['sha256']==expected for x in answers)
                        requests.append({'wall_ns':time.perf_counter_ns()-begin,'answers':answers})
                    # A live lease must prevent reclaim, and mismatched generations
                    # must not turn an old worker result into a current result.
                    try:broker.evict(admitted)
                    except BlockingIOError:pass
                    else:raise AssertionError('leased input reclaimed')
                    processes[0].stdin.write(json.dumps({'generation':'wrong','indices':indices})+'\n');processes[0].stdin.flush();assert not json.loads(processes[0].stdout.readline())['ok']
                    for child in processes:child.stdin.write('{"quit":true}\n');child.stdin.flush()
                    stopped=[]
                    for child in processes:
                        tail,_=child.communicate(timeout=30);assert child.returncode==0;stopped.append(json.loads(tail))
                    for lease in leases:broker.release(admitted,lease)
                    leases.clear();broker.evict(admitted);broker.close();elapsed=time.perf_counter_ns()-start
                    observations.append({'block':block,'mode':mode,'admission_ns':admission_ns,'ready_ns':ready_ns,'session_ns':elapsed,'memory_ready':snapshot,'requests':requests,'input_bytes':len(payload),'worker_count':a.workers,'source_count':len(rows),'compiled_units_per_request':len(indices),'expected_output':expected,'ready':ready,'stopped':stopped})
                    save()
                finally:
                    for child in processes:
                        if child.poll() is None:child.terminate();child.communicate(timeout=10)
                    for lease in leases:broker.release(admitted,lease)
                    broker.close()
    assert pins=={Path(__file__).name:sha(Path(__file__).read_bytes())}
    result['status']='complete';result['source_pins_verified_after']=True;save();print('Shared-input compiler worker cases:',len(observations),'sources:',len(rows),'bytes:',len(payload))


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    w=sub.add_parser('worker');w.add_argument('--fd',type=int,required=True);w.add_argument('--pin',required=True);w.add_argument('--mode',choices=['private','shared'],required=True)
    b=sub.add_parser('benchmark');b.add_argument('--source',type=Path,default=Path(sysconfig.get_path('stdlib')));b.add_argument('--limit',type=int,default=16*1024*1024);b.add_argument('--workers',type=int,default=4);b.add_argument('--requests',type=int,default=3);b.add_argument('--units',type=int,default=20);b.add_argument('--trials',type=int,default=3);b.add_argument('--work',type=Path,required=True);b.add_argument('--output',type=Path,required=True);b.add_argument('--lock',type=Path,required=True)
    a=p.parse_args();worker(a) if a.command=='worker' else run(a)


if __name__=='__main__':main()

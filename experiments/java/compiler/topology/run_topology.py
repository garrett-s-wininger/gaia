"""Compare private compiler threads in one JVM with the same slots in many JVMs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import random
import select
import shutil
import subprocess
import sys
import threading
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import benchmark as base


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def environment():
    paths=('/proc/pressure/cpu','/proc/pressure/memory','/proc/loadavg','/proc/self/cgroup','/sys/fs/cgroup/cpuset.cpus.effective','/sys/fs/cgroup/init.scope/cpu.max')
    return dict(uname=list(os.uname()),visible_cpus=os.cpu_count(),observations={name:Path(name).read_text() for name in paths if Path(name).is_file()})


def parse_smaps(text):
    fields={}
    for line in text.splitlines():
        parts=line.split()
        if len(parts)==3 and parts[0].endswith(':') and parts[2]=='kB':fields[parts[0][:-1]]=int(parts[1])*1024
    for key in ('Rss','Pss','Private_Clean','Private_Dirty'):
        if key not in fields:raise ValueError('missing memory field '+key)
    return dict(rss_bytes=fields['Rss'],pss_bytes=fields['Pss'],private_bytes=fields['Private_Clean']+fields['Private_Dirty'],pss_anon_bytes=fields.get('Pss_Anon'),pss_file_bytes=fields.get('Pss_File'))


def memory(pids):
    begin=time.perf_counter_ns();rows=[]
    for pid in pids:
        entry=parse_smaps(Path(f'/proc/{pid}/smaps_rollup').read_text());entry['pid']=pid;rows.append(entry)
    totals={key:sum(row[key] for row in rows) for key in ('rss_bytes','pss_bytes','private_bytes')}
    return dict(**totals,processes=rows,read_ns=time.perf_counter_ns()-begin)


class Sampler:
    def __init__(self,pids,interval):
        self.pids=pids;self.interval=interval;self.stop=threading.Event();self.rows=[];self.error=None;self.thread=threading.Thread(target=self.loop,daemon=True)
    def loop(self):
        begin=time.perf_counter_ns()
        try:
            while not self.stop.is_set():
                if len(self.rows)>=16384:raise ValueError('sample bound')
                self.rows.append(dict(elapsed_ns=time.perf_counter_ns()-begin,**memory(self.pids)))
                self.stop.wait(self.interval)
        except Exception as error:self.error=str(error)
    def __enter__(self):self.thread.start();return self
    def __exit__(self,*args):
        self.stop.set();self.thread.join()
        if self.error:raise RuntimeError(self.error)


class Session:
    def __init__(self,data,work,number,workers,jvms,cpu_count,total_heap):
        heap=total_heap//jvms;initial=max(8,64//jvms)
        self.flags=[f'-Xms{initial}m',f'-Xmx{heap}m','-XX:+UseG1GC',f'-XX:ActiveProcessorCount={max(1,cpu_count//jvms)}','-Xshare:on','-XX:-UsePerfData']
        self.command=[str(Path(data['image'])/'bin/java'),*self.flags,'-cp',data['app'],'TopologyHarness',str(workers),data['source'],data['second_source'],data['jdk'],data['compilation_classpath'],str(Path(data['work'])/'broken/Broken.java')]
        self.log=work/f'jvm{number}.stderr';self.stderr=self.log.open('w')
        env=dict(os.environ)
        for name in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS','CLASSPATH'):env.pop(name,None)
        self.process=subprocess.Popen(self.command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,text=True,env=env)
    def line(self):
        if not select.select([self.process.stdout],[],[],120)[0]:raise TimeoutError('JVM response')
        line=self.process.stdout.readline()
        if not line:raise RuntimeError('JVM terminated; see '+str(self.log))
        return line
    def ready(self):
        line=self.line()
        if not line.startswith('READY '):raise ValueError('ready framing '+line)
        return json.loads(line[6:])
    def call(self,command):
        self.process.stdin.write(command+'\n');self.process.stdin.flush();return json.loads(self.line())
    def stop(self):
        self.process.stdin.write('stop\n');self.process.stdin.flush();out,_=self.process.communicate(timeout=120);self.stderr.close()
        if self.process.returncode or out:raise ValueError('normal JVM shutdown failed')
    def abort(self):
        if self.process.poll() is None:self.process.kill()
        self.process.communicate(timeout=30);self.stderr.close()


class Group:
    def __init__(self,data,work,slots,jvms,cpus,heap,tasks):
        self.data=data;self.tasks=tasks;self.sessions=[]
        if slots%jvms or tasks%jvms or not 1<=slots<=8 or not 1<=jvms<=slots:raise ValueError('topology bounds')
        begin=time.perf_counter()
        try:
            for i in range(jvms):self.sessions.append(Session(data,work,i,slots//jvms,jvms,cpus,heap))
            self.ready=[session.ready() for session in self.sessions]
            if sum(row['heap_max'] for row in self.ready)!=heap*1048576:raise ValueError('effective aggregate heap cap differs')
        except Exception:
            for session in self.sessions:session.abort()
            raise
        self.start_seconds=time.perf_counter()-begin;self.pids=[s.process.pid for s in self.sessions]
    def batch(self,token):
        count=self.tasks//len(self.sessions);cpu=time.process_time();begin=time.perf_counter()
        with ThreadPoolExecutor(max_workers=len(self.sessions)) as executor:
            futures=[executor.submit(s.call,f'run {token} {i*count} {count}') for i,s in enumerate(self.sessions)]
            replies=[future.result() for future in futures]
        result=dict(seconds=time.perf_counter()-begin,controller_cpu_seconds=time.process_time()-cpu,jvm_cpu_seconds=sum(r.get('cpu_ns',0) for r in replies)/1e9,replies=replies)
        validate(result,self.data['expected'],self.tasks)
        return result
    def consume(self):
        with ThreadPoolExecutor(max_workers=len(self.sessions)) as executor:replies=list(executor.map(lambda s:s.call('check'),self.sessions))
        observed={int(k):v for r in replies for k,v in r.get('versions',{}).items()}
        expected={i:self.data['target_versions'][i%2] for i in range(self.tasks)}
        if observed!=expected or not all(r.get('ok') for r in replies):raise ValueError('actual bytecode consumer mismatch')
        return dict(targets=len(observed),versions=observed)
    def gc_diagnostic(self):
        with ThreadPoolExecutor(max_workers=len(self.sessions)) as executor:replies=list(executor.map(lambda s:s.call('gc'),self.sessions))
        if not all(r.get('ok') and r.get('requested_gc') for r in replies):raise ValueError('GC diagnostic failed')
        return dict(replies=replies,memory=memory(self.pids))
    def stop(self):
        begin=time.perf_counter()
        with ThreadPoolExecutor(max_workers=len(self.sessions)) as executor:list(executor.map(lambda s:s.stop(),self.sessions))
        return time.perf_counter()-begin
    def abort(self):
        for session in self.sessions:session.abort()


def validate(result,expected,tasks):
    seen={}
    for reply in result['replies']:
        if not reply.get('ok'):raise ValueError('compiler failure '+str(reply))
        for row in reply['outputs']:
            i=row['target']
            if i in seen or not 0<=i<tasks:raise ValueError('duplicate/invalid target')
            seen[i]=row
            if {k:row[k] for k in ('classes','bytes','sha256')}!=expected[i%2]:raise ValueError('independent CLI output mismatch')
    if set(seen)!=set(range(tasks)):raise ValueError('missing targets')


def prepare(source,work):
    data=json.loads(source.read_text());data['origin_prepared_sha256']=base.sha(source)
    if base.sha(HERE.parent/'CompilerHarness.java')!=data['harness_source_sha256']:raise ValueError('base harness source changed')
    for key,pins in (('source','source_sha256'),('second_source','second_source_sha256')):
        for name,pin in data[pins].items():
            if base.sha(Path(data[key])/name)!=pin:raise ValueError('source input changed')
        target=work/key;shutil.copytree(data[key],target);data[key]=str(target)
    data['work']=str(work);data['outputs']=str(work/'reference-outputs');empty=work/'empty-classpath';empty.mkdir();data['compilation_classpath']=str(empty)
    (work/'broken').mkdir();(work/'broken/Broken.java').write_text('class Broken { void invalid( }\n')
    classes=work/'classes';classes.mkdir();_,seconds=base.checked([Path(data['jdk'])/'bin/javac','-proc:none','-d',classes,HERE.parent/'CompilerHarness.java',HERE/'TopologyHarness.java'])
    app=work/'topology.jar';base.checked([Path(data['jdk'])/'bin/jar','--create','--file',app,'-C',classes,'.']);data['app']=str(app)
    data.pop('aot_cache',None)
    data['input_pins']['harness_jar_sha256']=base.sha(app)
    data['setup']=dict(harness_compile_seconds=seconds,app_sha256=base.sha(app),jdk_java_sha256=base.sha(Path(data['jdk'])/'bin/java'),jdk_modules_sha256=base.sha(Path(data['jdk'])/'lib/modules'),image_java_sha256=base.sha(Path(data['image'])/'bin/java'),image_modules_sha256=base.sha(Path(data['image'])/'lib/modules'))
    runtime_files=[app,Path(data['jdk'])/'bin/javac',Path(data['jdk'])/'lib/modules',Path(data['image'])/'bin/java',Path(data['image'])/'lib/modules',Path(data['image'])/'lib/server/libjvm.so',Path(data['image'])/'lib/server/classes.jsa']
    for key,pins in (('source','source_sha256'),('second_source','second_source_sha256')):runtime_files.extend(Path(data[key])/name for name in data[pins])
    data['admitted_files']={str(path):base.sha(path) for path in runtime_files}
    data['expected']=[{k:r[k] for k in ('classes','bytes','sha256')} for r in (base.cli(data,'reference-a',True,0),base.cli(data,'reference-b',True,1))]
    save(work/'prepared.json',data);return data


def run(args):
    cpus=sorted(os.sched_getaffinity(0))[:args.cpus]
    if len(cpus)!=args.cpus:raise ValueError('insufficient allowed CPU affinity')
    os.sched_setaffinity(0,cpus)
    runid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/runid;work.mkdir(parents=True)
    data=prepare(args.prepared.resolve(),work)
    configurations=[(k,j) for k in args.workers for j in ([1] if k==1 else [1,k])]
    result=dict(run_id=runid,status='running',trials=args.trials,tasks_per_batch=args.tasks,steady_batches=args.steady_batches,aggregate_heap_cap_mib=args.heap_mib,shared_cpu_affinity=cpus,sampler_interval_seconds=args.sample_interval,gc_diagnostic=args.gc_after,preparation=data,source_sha256={n:base.sha(p) for n,p in [('TopologyHarness.java',HERE/'TopologyHarness.java'),('run_topology.py',HERE/'run_topology.py'),('CompilerHarness.java',HERE.parent/'CompilerHarness.java'),('benchmark.py',HERE.parent/'benchmark.py')]},cases=[])
    frozen=work/'sources';frozen.mkdir()
    for name in result['source_sha256']:shutil.copyfile(HERE/name if (HERE/name).is_file() else HERE.parent/name,frozen/name)
    result['source_snapshots']=str(frozen);result['environment_before']=environment();rng=random.Random(300124)
    args.output.mkdir(parents=True,exist_ok=False)
    for block in range(args.trials):
        order=configurations.copy();rng.shuffle(order)
        for slots,jvms in order:
            folder=work/f'b{block}-slots{slots}-jvms{jvms}';folder.mkdir();whole=time.perf_counter();group=Group(data,folder,slots,jvms,args.cpus,args.heap_mib,args.tasks)
            try:
                row=dict(block=block,slots=slots,jvms=jvms,workers_per_jvm=slots//jvms,start_seconds=group.start_seconds,ready=group.ready,vm_flags=[s.flags for s in group.sessions],memory_ready=memory(group.pids))
                row['first']=group.batch('first');row['memory_after_first']=memory(group.pids)
                row['warmup']=group.batch('warmup');row['memory_after_warmup']=memory(group.pids)
                if args.sample_interval:
                    with Sampler(group.pids,args.sample_interval) as sampler:row['steady']=[group.batch(f'steady-{i}') for i in range(args.steady_batches)]
                    row['samples']=sampler.rows;row['sampled_peak']={key:max(r[key] for r in sampler.rows) for key in ('rss_bytes','pss_bytes','private_bytes')}
                else:row['steady']=[group.batch(f'steady-{i}') for i in range(args.steady_batches)]
                row['memory_after_steady']=memory(group.pids)
                if args.gc_after:row['gc_diagnostic']=group.gc_diagnostic()
                row['consumer']=group.consume();row['memory_after_consumer']=memory(group.pids);row['shutdown_seconds']=group.stop();row['whole_session_seconds']=time.perf_counter()-whole
                result['cases'].append(row);save(args.output/'results.json',result)
                print(block,slots,jvms,'first',round(row['first']['seconds']*1000,1),'steady',[round(r['seconds']*1000,1) for r in row['steady']],'PSS MiB',round(row['memory_after_steady']['pss_bytes']/1048576,1),flush=True)
            except Exception:group.abort();raise
    for name,pin in data['admitted_files'].items():
        if base.sha(Path(name))!=pin:raise ValueError('admitted input changed during run: '+name)
    result['admitted_input_postcheck']=True;result['environment_after']=environment();result['status']='complete';save(args.output/'results.json',result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--workers',nargs='+',type=int,default=[1,2,4,8])
    parser.add_argument('--tasks',type=int,default=8)
    parser.add_argument('--cpus',type=int,default=8)
    parser.add_argument('--heap-mib',type=int,default=3072)
    parser.add_argument('--trials',type=int,default=3)
    parser.add_argument('--steady-batches',type=int,default=2)
    parser.add_argument('--sample-interval',type=float,default=0)
    parser.add_argument('--gc-after',action='store_true',help='Separate diagnostic: request GC after timed batches; never a latency optimization')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not 1<=args.tasks<=8 or any(k not in (1,2,4,8) or args.tasks%k for k in args.workers) or len(set(args.workers))!=len(args.workers):parser.error('distinct worker counts1/2/4/8 must divide task count')
    if args.trials<1 or args.steady_batches<1 or not 1<=args.cpus<=16 or args.heap_mib<384*max(args.workers) or args.sample_interval<0:parser.error('invalid resource/trial limits')
    run(args)

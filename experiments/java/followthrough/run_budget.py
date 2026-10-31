"""Longer mixed javac queues; soft sampled PSS admission budget, not a quota."""
import argparse, contextlib, fcntl, hashlib, json, os, pathlib, random, re, select, statistics, subprocess, sys, time
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'compiler/topology'))
import run_topology as topology
OriginalSession=topology.Session
class Session(OriginalSession):
    collector='parallel';diagnostic=False
    def __init__(self,data,work,number,workers,jvms,cpu_count,total_heap):
        heap=total_heap//jvms;initial=max(8,64//jvms)
        self.flags=[f'-Xms{initial}m',f'-Xmx{heap}m','-XX:+UseParallelGC' if self.collector=='parallel' else '-XX:+UseG1GC',f'-XX:ActiveProcessorCount={max(1,cpu_count//jvms)}','-Xshare:on','-XX:-UsePerfData']
        if self.diagnostic:self.flags+=['-XX:NativeMemoryTracking=summary','-XX:+UnlockDiagnosticVMOptions','-XX:+PrintNMTStatistics']
        self.command=[str(pathlib.Path(data['image'])/'bin/java'),*self.flags,'-cp',data['app'],'TopologyHarness',str(workers),data['source'],data['second_source'],data['jdk'],data['compilation_classpath'],str(pathlib.Path(data['work'])/'broken/Broken.java')]
        self.log=work/f'jvm{number}.stderr';self.stderr=self.log.open('w');env=dict(os.environ)
        for n in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS','CLASSPATH'):env.pop(n,None)
        self.process=subprocess.Popen(self.command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,text=True,env=env)
    def stop(self):
        self.process.stdin.write('stop\n');self.process.stdin.flush();out,_=self.process.communicate(timeout=120);self.stderr.close();self.exit_stdout=out
        if self.process.returncode or (out and not self.diagnostic):raise ValueError('normal JVM shutdown failed')
        if self.diagnostic and 'Native Memory Tracking:' not in out:raise ValueError('NMT exit report absent')
topology.Session=Session
class Group(topology.Group):
    def __init__(self,data,work,slots,jvms,cpus,heap,tasks):
        self.data=data;self.tasks=tasks;self.sessions=[]
        if slots%jvms or tasks%jvms or not 1<=slots<=8 or not 1<=jvms<=slots:raise ValueError('topology bounds')
        begin=time.perf_counter()
        try:
            for i in range(jvms):self.sessions.append(Session(data,work,i,slots//jvms,jvms,cpus,heap))
            self.ready=[session.ready() for session in self.sessions]
            # Parallel maxMemory excludes a survivor space: preserve effective report,
            # do not assert equality to -Xmx as the older G1-only harness did.
            if sum(row['heap_max'] for row in self.ready)>heap*1048576:raise ValueError('effective heap exceeds requested cap')
        except Exception:
            for session in self.sessions:session.abort()
            raise
        self.start_seconds=time.perf_counter()-begin;self.pids=[s.process.pid for s in self.sessions]

def smaps(pid):
    text=pathlib.Path(f'/proc/{pid}/smaps').read_text();summary={}
    category='unknown'
    for line in text.splitlines():
        if re.match(r'^[0-9a-f]+-[0-9a-f]+ ',line):
            fields=line.split(maxsplit=5);name=fields[5] if len(fields)>5 else '[anonymous]'
            category='anonymous' if name.startswith('[') else 'file'
        else:
            fields=line.split()
            if len(fields)==3 and fields[0].rstrip(':') in ('Rss','Pss','Anonymous','LazyFree','Private_Dirty'):
                key=category+'_'+fields[0].rstrip(':')+'_bytes';summary[key]=summary.get(key,0)+int(fields[1])*1024
    return summary

def save(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2)+'\n')
def run(a):
    a.output.mkdir(parents=True,exist_ok=True);a.work.mkdir(parents=True,exist_ok=True)
    os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:a.cpus])
    prep=a.work/'prepared';prep.mkdir(exist_ok=False);data=topology.prepare(a.prepared,prep)
    result=dict(companion_command=json.loads(a.companion_command) if a.companion_command else None,schema='GAIA-JVM-RESIDENT-BUDGET-1',scope='Same eight alternating whole picocli targets; sampled soft aggregate PSS gate checked between batches, not hard RSS enforcement. Sequential smaps samples are not atomic peaks. NMT is diagnostic only.',budget_bytes=a.budget_mib*1048576,batches=a.batches,tasks=8,heap_mib=a.heap_mib,cpu_affinity=sorted(os.sched_getaffinity(0)),preparation=data,cases=[],environment=topology.environment())
    cases=[(spec.split(':')[0],int(spec.split(':')[1])) for spec in a.cases]
    if any(c not in ('g1','parallel') or n not in (1,4) for c,n in cases):raise ValueError('supported cases g1/parallel:1/4')
    random.Random(234).shuffle(cases)
    for diagnostic in ([True] if a.diagnostic_only else ([False] if a.skip_diagnostic else [False,True])):
      for collector,jvms in (cases if not diagnostic else [('parallel',1)]):
        Session.collector=collector;Session.diagnostic=diagnostic
        folder=a.work/f'{collector}-{jvms}-{diagnostic}';folder.mkdir();companion=None;group=None;whole=time.perf_counter()
        try:
            if a.companion_command:
                companion=subprocess.Popen(json.loads(a.companion_command),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(folder/'companion.stderr').open('w'),text=True)
                if not select.select([companion.stdout],[],[],60)[0]:raise TimeoutError('companion readiness')
                ready=companion.stdout.readline()
                if json.loads(ready).get('event')!='READY':raise ValueError(ready)
            group=Group(data,folder,4,jvms,a.cpus,a.heap_mib,8)
            pids=group.pids+([companion.pid] if companion else [])
            row=dict(companion_ready=json.loads(ready) if companion else None,collector=collector,jvms=jvms,diagnostic=diagnostic,start_seconds=group.start_seconds,effective_ready=group.ready,commands=[s.command for s in group.sessions],memory_ready=topology.memory(pids),batches=[])
            with topology.Sampler(pids,.05) as sampler:
                for batch in range(2 if diagnostic else a.batches):
                    current=topology.memory(pids)
                    if current['pss_bytes']>a.budget_mib*1048576:
                        row['admission_stopped_at_batch']=batch;break
                    value=group.batch(f'q{batch}');value['memory_after']=topology.memory(pids);row['batches'].append(value)
            row['sampled_max_pss_bytes']=max(s['pss_bytes'] for s in sampler.rows);row['samples']=sampler.rows
            row['pre_gc_smaps']=[dict(pid=p,fields=smaps(p)) for p in pids];row['gc']=group.gc_diagnostic();row['post_gc_smaps']=[dict(pid=p,fields=smaps(p)) for p in pids]
            if row['batches']:row['consumer']=group.consume()
            group.stop();row['exit_stdout']=[getattr(session,'exit_stdout','') for session in group.sessions];group=None
            if companion:
                companion.terminate();stdout,_=companion.communicate(timeout=30);row['companion_final']=stdout;row['companion_exit']=companion.returncode;companion=None
            row['whole_seconds']=time.perf_counter()-whole
            row['stderr']=[p.read_text() for p in sorted(folder.glob('jvm*.stderr'))]
            if row['batches']:
                late=row['batches'][-8:];row['late_median_batch_ms']=statistics.median(r['seconds']*1000 for r in late);row['completed_targets']=8*len(row['batches'])
            result['cases'].append(row);save(a.output/'results.json',result)
            print(collector,jvms,diagnostic,len(row['batches']),row.get('late_median_batch_ms'),round(row['sampled_max_pss_bytes']/1048576),flush=True)
        finally:
            if group:group.abort()
            if companion:companion.terminate();companion.communicate(timeout=10)
    result['status']='complete';save(a.output/'results.json',result)
    raw=a.output/'results.json';save(a.output/'summary.json',dict(raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),raw_bytes=raw.stat().st_size,cases=[{k:v for k,v in c.items() if k in ('collector','jvms','diagnostic','late_median_batch_ms','completed_targets','sampled_max_pss_bytes','admission_stopped_at_batch','whole_seconds')} for c in result['cases']]))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepared',type=pathlib.Path,required=True);p.add_argument('--work',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--batches',type=int,default=24);p.add_argument('--budget-mib',type=int,default=2048);p.add_argument('--heap-mib',type=int,default=1536);p.add_argument('--cpus',type=int,default=8);p.add_argument('--companion-command');p.add_argument('--cases',nargs='+',default=['g1:1','parallel:1','parallel:4']);p.add_argument('--skip-diagnostic',action='store_true');p.add_argument('--diagnostic-only',action='store_true');a=p.parse_args()
    if min(a.batches,a.budget_mib,a.heap_mib,a.cpus)<1:p.error('positive limits')
    run(a)

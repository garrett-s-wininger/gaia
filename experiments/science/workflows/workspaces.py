"""Actual source analysis in private namespaces and shared immutable generations."""
import ast,hashlib,json,os,random,shutil,threading,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from common import filepin,lock,timed

FILES=('ast.py','tokenize.py','difflib.py','statistics.py','fractions.py','doctest.py','pprint.py','inspect.py','dataclasses.py','typing.py','argparse.py','pathlib/__init__.py','json/decoder.py','json/encoder.py','collections/__init__.py','unittest/case.py')

def facts(body,name):
    try:
        tree=ast.parse(body,filename=name)
        # Detached immutable names/locations, not a shared mutable Python AST.
        names=tuple(sorted((type(n).__name__,n.name,n.lineno) for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))))
        compile(body,name,'exec')
        return names,None
    except SyntaxError as exc:return (),dict(line=exc.lineno,offset=exc.offset,message=exc.msg)

def query(items):
    result=[];errors=[]
    for name,(body,observation) in sorted(items.items()):
        names,error=observation
        if error:errors.append((name,error['line'],error['message']))
        result.extend((name,kind,value,line) for kind,value,line in names if value.startswith(('parse','gaia_')))
    return dict(names=result,errors=errors)

def signature(items):
    h=hashlib.sha256()
    for name,(body,_) in sorted(items.items()):h.update(name.encode()+b'\0'+hashlib.sha256(body).digest())
    return h.hexdigest()

class Workspace:
    def __init__(self,base,cache,folder=None,hardlinks=None):
        self.generation=0;self.cache=cache;self.folder=folder;self._lock=threading.Lock();self.last_publication=None
        self.items={}
        if folder:folder.mkdir(parents=True)
        for name,body in base.items():
            if folder:
                target=folder/name;target.parent.mkdir(parents=True,exist_ok=True)
                if hardlinks:os.link(hardlinks/name,target)
                else:target.write_bytes(body)
            key=hashlib.sha256(body).hexdigest()
            if key not in cache:cache[key]=(body,facts(body,name))
            self.items[name]=cache[key]
    def edit(self,name,body,expected,observe=True):
        with self._lock:
            if expected!=self.generation:return False
            if self.folder:
                target=self.folder/name;temp=target.with_name(target.name+'.new');temp.write_bytes(body);os.replace(temp,target)
            key=hashlib.sha256(body).hexdigest()
            if key not in self.cache:self.cache[key]=(body,facts(body,name) if observe else None)
            self.items=dict(self.items);self.items[name]=self.cache[key];self.generation+=1;self.last_publication=None;return True
    def capture(self):
        with self._lock:return self.generation,dict(self.items)
    def publish(self,generation,result):
        with self._lock:
            if generation!=self.generation:return False
            self.last_publication=(generation,result);return True

def corpus():
    root=Path('/usr/lib/python3.14')
    return {name:(root/name).read_bytes() for name in FILES}

def session(mode,base,folder,rounds=4):
    folder.mkdir();begin=time.perf_counter_ns();cache={};workers=[];physical=None
    if mode!='private-materialized':
        for name,body in base.items():cache[hashlib.sha256(body).hexdigest()]=(body,facts(body,name))
    if mode=='materialized-shared-cache':
        physical=folder/'base';physical.mkdir()
        for name,body in base.items():p=physical/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body)
    for actor in range(4):
        shared=cache if mode!='private-materialized' else {}
        workers.append(Workspace(base,shared,None if mode=='logical-shared' else folder/f'actor{actor}',physical))
    initial_ns=time.perf_counter_ns()-begin;operations=[]
    for epoch in range(rounds):
        for actor,workspace in enumerate(workers):
            body=base['difflib.py']+f'\ndef gaia_actor_{actor}_{epoch}():\n    return {actor+epoch}\n'.encode()
            start=time.perf_counter_ns();assert workspace.edit('difflib.py',body,workspace.generation)
            generation,items=workspace.capture();result=query(items);accepted=workspace.publish(generation,result)
            operations.append(dict(actor=actor,epoch=epoch,wall_ns=time.perf_counter_ns()-start,generation=generation,accepted=accepted,signature=signature(items),names=[x for x in result['names'] if x[2].startswith('gaia_')]))
            assert accepted and operations[-1]['names']==[('difflib.py','FunctionDef',f'gaia_actor_{actor}_{epoch}',len(base['difflib.py'].splitlines())+2)]
    # Account retained logical cache payload, not heap/RSS. Private caches truly
    # own independently parsed byte objects in a physical implementation; this
    # harness's admitted base bytes may share Python identity across namespaces.
    unique_caches={id(w.cache):w.cache for w in workers}
    retained=sum(len(body) for cache in unique_caches.values() for body,_ in cache.values())
    return dict(initial_ns=initial_ns,operations=operations,logical_cached_payload_bytes=retained,
                session_ns=time.perf_counter_ns()-begin)

def run(args):
    base=corpus();pins={name:hashlib.sha256(body).hexdigest() for name,body in base.items()};rows=[];reference=None
    for block in range(args.trials):
        modes=['private-materialized','materialized-shared-cache','logical-shared'];random.Random(44+block).shuffle(modes)
        for mode in modes:
            folder=args.work/f'workspace-{block}-{mode}'
            with lock(args.lock):sample=timed(lambda:session(mode,base,folder))
            result=sample['value'];identities=[(r['actor'],r['epoch'],r['signature'],r['names']) for r in result['operations']]
            if reference is None:reference=identities
            assert identities==reference
            footprint=sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())
            cleanup=time.perf_counter_ns();shutil.rmtree(folder);cleanup=time.perf_counter_ns()-cleanup
            rows.append(dict(block=block,mode=mode,wall_ns=sample['wall_ns'],materialized_bytes=footprint,cleanup_ns=cleanup,complete_cycle_ns=sample['wall_ns']+cleanup,**result))
    assert pins=={name:filepin(Path('/usr/lib/python3.14')/name) for name in base}
    return dict(rows=rows,source_pins=pins,source_bytes=sum(map(len,base.values())),files=len(base),
        scope='Four scripted actors,16actual CPython source modules,detached AST-name facts plus real Python compile validation. Four declared updates peractor,private views/current generations. Strong materialized shared-content/fact cache control uses immutable hardlinks plus atomic replacement. Logical provider omits full ordinary-file namespaces, a different compatibility contract. Logical cached byte counts are not actual unique heap/RSS; historical changed-result cache entries retained only for bounded trace, not memory guarantee. All modes accept reported edits only, no unreported filesystem-change discovery.')

def editor(args):
    base=corpus();results=[]
    for block in range(args.trials):
        modes=['fifo','cancel-obsolete'];random.Random(701+block).shuffle(modes)
        for mode in modes:
            preparation=time.perf_counter_ns();workspace=Workspace(base,{});preparation=time.perf_counter_ns()-preparation
            gate=threading.Event();ready=threading.Event();executed=[];futures=[]
            def analyze(generation,items):
                executed.append(generation)
                current=dict(items);body=current['difflib.py'][0];current['difflib.py']=(body,facts(body,'difflib.py'))
                return generation,query(current)
            def blocker():ready.set();gate.wait(timeout=30)
            with lock(args.lock):
                begin=time.perf_counter_ns()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    blocked=pool.submit(blocker);assert ready.wait(5)
                    for epoch in range(12):
                        body=base['difflib.py']+f'\ndef gaia_edit_{epoch}():\n    return {epoch}\n'.encode()
                        assert workspace.edit('difflib.py',body,workspace.generation,observe=False)
                        if mode=='cancel-obsolete':
                            for future in futures:future.cancel()
                        futures.append(pool.submit(analyze,*workspace.capture()))
                    gate.set();blocked.result();accepted=[];stale=0;cancelled=0
                    for future in futures:
                        if future.cancelled():cancelled+=1;continue
                        generation,result=future.result()
                        if workspace.publish(generation,result):accepted.append(generation)
                        else:stale+=1
                elapsed=time.perf_counter_ns()-begin
            assert accepted==[12]
            timed_executed=len(executed)
            # A captured running result must still be rejected after a newer edit.
            generation,items=workspace.capture();assert workspace.edit('difflib.py',base['difflib.py']+b'\ndef broken(:\n',12,observe=False)
            assert not workspace.publish(generation,analyze(generation,items)[1]);_,current=analyze(*workspace.capture());assert current['errors']
            assert not workspace.edit('difflib.py',base['difflib.py'],12)
            results.append(dict(block=block,mode=mode,wall_ns=elapsed,preparation_ns=preparation,executed=timed_executed,post_clock_guard_queries=len(executed)-timed_executed,cancelled=cancelled,stale=stale,accepted=accepted,current_syntax_errors=current['errors']))
    return dict(rows=results,source_pins={name:hashlib.sha256(body).hexdigest() for name,body in base.items()},scope='Actual ThreadPoolExecutor parse/compile/query over admitted real-source bytes, controlled12edit queued burst. One worker held at explicit barrier to make queued cancellation deterministic; not a natural typing trace or latency percentile. Byte admission and worker current-overlay analysis/query charged; initial base fact preparation reported separately. Queuedobsolete futures maycancel, running/captured generations require publicationguard. No GUI/LSPimplementation or arbitrary-effect cancellation.')

if __name__=='__main__':
    import argparse,resource,tracemalloc
    parser=argparse.ArgumentParser();parser.add_argument('--memory-mode',choices=['private-materialized','materialized-shared-cache','logical-shared'],required=True);parser.add_argument('--work',type=Path,required=True);a=parser.parse_args()
    base=corpus();tracemalloc.start();result=session(a.memory_mode,base,a.work);_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    print(json.dumps(dict(mode=a.memory_mode,python_traced_peak_bytes=peak,process_highwater_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,logical_cached_payload_bytes=result['logical_cached_payload_bytes'],scope='Separate fresh-process diagnostic. RSS includes interpreter/source admission/parser/transient work; Python trace starts after base bytes admitted. Instrumented run excluded from latency comparisons.')))

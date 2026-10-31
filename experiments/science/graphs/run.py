"""Frozen bounded studies for patch laws, observations, scheduling and retention."""
import argparse
from collections import defaultdict
import ctypes
from dataclasses import asdict
import fcntl
import hashlib
import itertools
import json
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time
import tracemalloc

import patches
import facts
import retention
import scheduling

HERE=Path(__file__).resolve().parent


def digest(body):return hashlib.sha256(body).hexdigest()


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2)+'\n')


def timed(function):
    begin=time.perf_counter_ns();cpu=time.process_time_ns();value=function()
    return dict(wall_ns=time.perf_counter_ns()-begin,cpu_ns=time.process_time_ns()-cpu,value=value)


def lock_run(lock,function):
    with lock.open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        return timed(function)


def patch_study(args):
    entries=(None,patches.Entry('file',b'a'),patches.Entry('file',b'b'),patches.Entry('file',b'a',True),patches.Entry('link',b'target'))
    def exhaustive():
        counts=defaultdict(int)
        for a,b in itertools.product(entries,repeat=2):
            state={k:v for k,v in [('a',a),('b',b)] if v is not None}
            for av,bv in itertools.product(entries,repeat=2):
                p=(patches.Edit('a',a,av),);q=(patches.Edit('b',b,bv),)
                expected={k:v for k,v in [('a',av),('b',bv)] if v is not None}
                result=patches.apply(state,patches.compose(p,q));assert result==expected;counts['composition']+=1
                assert patches.apply(patches.apply(state,p),patches.inverse(p))==state;counts['inverse']+=1
                swap=patches.commute(p,q);assert patches.apply(state,patches.compose(*swap))==expected;counts['commutation']+=1
        for a,b,c in itertools.product([frozenset(),frozenset({(1,'answer','left')}),frozenset({(1,'answer','right')})],repeat=3):
            assert patches.join_facts(a,b)==patches.join_facts(b,a)
            assert patches.join_facts(a,a)==a
            assert patches.join_facts(patches.join_facts(a,b),c)==patches.join_facts(a,patches.join_facts(b,c));counts['join_triples']+=1
        target=patches.Target();assert target.publish(0,'a');assert not target.publish(0,'b');counts['stale_publish_rejected']=1
        return dict(counts)
    checks=lock_run(args.lock,exhaustive)
    state={f'file/{i:05}':patches.Entry('file',b'initial') for i in range(500)}
    rng=random.Random(312);pairs=[]
    for _ in range(1000):
        a,b=rng.sample(list(state),2);pairs.append(((patches.Edit(a,state[a],patches.Entry('file',b'a')),),(patches.Edit(b,state[b],patches.Entry('file',b'b')),)))
    rows=[]
    for block in range(args.trials):
        for mode in random.Random(block).sample(['law-check','snapshot-oracle'],2):
            def work():
                accepted=0
                for p,q in pairs:
                    swap=patches.commute(p,q)
                    if mode=='snapshot-oracle':assert patches.apply(state,patches.compose(p,q))==patches.apply(state,patches.compose(*swap))
                    accepted+=swap is not None
                return accepted
            row=lock_run(args.lock,work);assert row.pop('value')==1000;rows.append(dict(block=block,mode=mode,**row))
    return dict(exhaustive=checks,rows=rows,scope='Law-check is a precondition decision, not complete snapshot integration or proof of program independence; snapshot oracle reconstructs complete states. No patch-replay storage selected.')


def synthetic_fixture(components=20,width=8):
    specs={};files={};env={'SELECT':'first','FLAGS':'base'}
    for component in range(components):
        for index in range(width):
            name=f'c{component}/n{index}';files[f'c{component}/late/{index}.h']=f'content-{component}-{index}'.encode()
            deps=(f'c{component}/n{(index+1)%width}',) if index<3 else ((f'c{component}/n{index-1}',) if index else ())
            specs[name]=facts.Spec(((f'c{component}/early/{index}.h',f'c{component}/late/{index}.h'),),('FLAGS',),deps=deps)
        specs[f'test:{component}']=facts.Spec(deps=(f'c{component}/n{width-1}',))
        specs[f'editor:{component}']=facts.Spec(directories=(f'c{component}/early',),deps=(f'c{component}/n0',),env_lookup='SELECT')
    files['first/selected.h']=b'first';files['second/selected.h']=b'second'
    changes=[]
    for step in range(24):
        c=step%components;i=step%width
        kind=step%6
        if kind==0:changes.append(dict(files={f'c{c}/early/{i}.h':f'shadow-{step}'.encode()}))
        elif kind==1:changes.append(dict(files={f'c{c}/late/{i}.h':f'edit-{step}'.encode()}))
        elif kind==2:changes.append(dict(files={f'c{c}/early/{i}.h':None}))
        elif kind==3:changes.append(dict(env={'SELECT':'second' if step%2 else 'first'}))
        elif kind==4:changes.append(dict(specs={f'c{c}/n0':facts.Spec(((f'c{c}/early/0.h',f'c{c}/late/0.h'),),('FLAGS',),deps=(f'c{(c+1)%components}/n1',))}))
        else:changes.append(dict(files={f'c{c}/early/added.h':f'member-{step}'.encode()}))
    return specs,files,env,changes


def graph_study(args):
    specs,files,env,changes=synthetic_fixture()
    expected=[];oracle=facts.Engine(specs,files,env)
    for change in changes:
        row=oracle.update(**change);expected.append((dict(oracle.outputs),row['changed_outputs']))
    rows=[];construction=[]
    for block in range(args.trials):
        modes=random.Random(17+block).sample([facts.Engine,facts.Frontier,facts.Relational],3)
        for cls in modes:
            built=lock_run(args.lock,lambda:cls(specs,files,env));engine=built.pop('value');construction.append(dict(block=block,mode=cls.mode,**built))
            for step,change in enumerate(changes):
                row=lock_run(args.lock,lambda:engine.update(**change));metrics=row.pop('value')
                assert engine.outputs==expected[step][0] and metrics['changed_outputs']==expected[step][1]
                rows.append(dict(block=block,mode=cls.mode,step=step,**row,**metrics))
    allocations={}
    for cls in (facts.Engine,facts.Frontier,facts.Relational):
        tracemalloc.start();engine=cls(specs,files,env)
        for change in changes:engine.update(**change)
        current,peak=tracemalloc.get_traced_memory();tracemalloc.stop();allocations[cls.mode]=dict(retained=current,peak=peak)
    return dict(nodes=len(specs),files=len(files),updates=len(changes),construction=construction,rows=rows,python_allocations=allocations,
        scope='Explicit lookup/directory/environment observation language; relation mode materializes reachability and rebuilds it on topology changes. Cyclic outputs are union fixed points, not compiler AST/IR. Whole outputs and test/editor changed sets match full recomputation after every update.')


def captured_ninja(args):
    if not args.ninja_project:return dict(status='not-run',reason='provide --ninja-project for captured relation; synthetic dynamic study remains independent')
    project=args.ninja_project.resolve();ninja=project/'ninja';before=digest(ninja.read_bytes())
    text=subprocess.check_output([str(ninja),'-t','deps'],cwd=project,text=True);mapping={};current=None;states={}
    for line in text.splitlines():
        if line and not line.startswith(' '):
            current=line.split(':',1)[0];mapping[current]=[];states[current]='STALE' if '(STALE)' in line else 'VALID'
        elif line.startswith('    ') and current:mapping[current].append(line.strip())
    files={path:(project/path).read_bytes() for values in mapping.values() for path in values}
    specs={f'test:{target}':facts.Spec(tuple((p,) for p in deps)) for target,deps in mapping.items()}
    engine=facts.Frontier(specs,files,{})
    probes=[]
    for path in ['src/version.h','src/util.h','build/browse_py.h']:
        if path not in files:continue
        change={path:files[path]+b'\n/* hypothetical admitted byte change */\n'}
        expected={root for root,spec in specs.items() if (path,) in spec.lookups}
        row=lock_run(args.lock,lambda:engine.update(files=change));metrics=row.pop('value');assert set(metrics['selected_tests'])==expected
        probes.append(dict(path=path,selected=metrics['selected_tests'],**row))
        engine.update(files={path:files[path]})
    assert digest(ninja.read_bytes())==before
    return dict(status='complete',compile_targets=len(mapping),dependency_edges=sum(map(len,mapping.values())),captured_status_counts={s:list(states.values()).count(s) for s in set(states.values())},
        ninja_sha256=before,dependency_relation_sha256=digest(text.encode()),file_pins={p:digest(b) for p,b in files.items()},probes=probes,
        scope='Captured prior Ninja positive-dependency relation, including its reported stale entry. Target IDs reuse test prefix for selection machinery; they are compile targets, not tests. No new Clang integration or soundness proof for arbitrary future includes.')


def compiler_probe(args):
    if not args.clang:return dict(status='not-run',reason='provide --clang for independent C lookup-control')
    root=args.work/'compiler-probe';root.mkdir();(root/'early').mkdir();(root/'late').mkdir()
    files={'late/selected.h':b'#define VALUE 1\n'};specs={}
    for index in range(3):
        path=f'unit{index}.c';body=(f'#include <selected.h>\n#if __has_include(<optional.h>)\n#include <optional.h>\n#else\n#define EXTRA 0\n#endif\nint f{index}(void){{return VALUE+EXTRA+FLAG;}}\n').encode();files[path]=body
        specs[f'test:{index}']=facts.Spec(((path,),('early/selected.h','late/selected.h'),('early/optional.h','late/optional.h')),('FLAG',))
    env={'FLAG':'0'};engine=facts.Frontier(specs,files,env)
    def materialize(changes):
        for path,body in changes.items():
            target=root/path
            if body is None:target.unlink(missing_ok=True)
            else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
    materialize(files)
    def compile_one(index,suffix):
        output=root/f'unit{index}-{suffix}.o'
        command=[str(args.clang),'-O2','-I',str(root/'early'),'-I',str(root/'late'),'-DFLAG='+env['FLAG'],'-c',str(root/f'unit{index}.c'),'-o',str(output)]
        subprocess.run(command,capture_output=True,check=True);return output.read_bytes()
    objects={i:compile_one(i,'retained') for i in range(3)}
    scenarios=[('shadow-appearance',{'early/selected.h':b'#define VALUE 2\n'},{}),
               ('unobserved-later-change',{'late/selected.h':b'#define VALUE 4\n'},{}),
               ('environment',{}, {'FLAG':'7'}),('shadow-removal',{'early/selected.h':None},{}),
               ('optional-appearance',{'early/optional.h':b'#define EXTRA 9\n'},{}),
               ('one-source',{'unit2.c':files['unit2.c'].replace(b'VALUE+EXTRA+FLAG',b'VALUE+EXTRA+FLAG+1')},{}),
               ('optional-removal',{'early/optional.h':None},{}),('unobserved-membership',{'early/unused.h':b'ignored\n'}, {})]
    rows=[]
    for name,changed,env_changed in scenarios:
        materialize(changed);env.update(env_changed);selected=engine.update(files=changed,env=env_changed)['selected_tests']
        for target in selected:
            index=int(target.split(':')[1]);objects[index]=compile_one(index,'retained')
        references={i:compile_one(i,'oracle') for i in range(3)};assert objects==references
        rows.append(dict(scenario=name,recompiled=len(selected),selected=selected,oracle_objects=3,object_sha256={str(i):digest(b) for i,b in objects.items()}))
    return dict(status='complete',rows=rows,initial_compilations=3,oracle_compilations=3*len(rows),selected_recompilations=sum(r['recompiled'] for r in rows),clang_sha256=digest(args.clang.read_bytes()),scope='Three declared C include fixtures and explicitFLAG argument; objectbytes matched after each change. Resolver language is explicit, not automatic Clang observation extraction or a sound production scheduler; physical SDK held by environment, not atomically admitted.')


def native_probe(args):
    if not args.library:return dict(status='not-run',reason='provide --library for Odin frontier check')
    library=ctypes.CDLL(str(args.library.resolve()));call=library.gaia_affected;call.argtypes=[ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p];call.restype=ctypes.c_int32
    rng=random.Random(515);rows=[]
    for n in (1,8,32,128):
        for iteration in range(10):
            specs={f'n{i}':facts.Spec(deps=tuple(f'n{j}' for j in range(n) if rng.random()<2/n)) for i in range(n)}
            dirty={i for i in range(n) if rng.random()<.08} or {0};matrix=bytes(int(f'n{j}' in specs[f'n{i}'].deps) for i in range(n) for j in range(n));mask=bytes(int(i in dirty) for i in range(n));out=(ctypes.c_uint8*n)()
            row=lock_run(args.lock,lambda:call(n,ctypes.c_char_p(matrix),ctypes.c_char_p(mask),out));assert row.pop('value')==0
            expected={i for i in range(n) if {f'n{j}' for j in dirty}&facts.closure_nodes(specs,f'n{i}')};assert {i for i,x in enumerate(out) if x}==expected
            rows.append(dict(nodes=n,iteration=iteration,**row))
    bad=(ctypes.c_uint8*1)();assert call(0,None,None,bad)==1;assert call(1,ctypes.c_char_p(b'\x02'),ctypes.c_char_p(b'\x00'),bad)==2
    return dict(status='complete',rows=rows,library_sha256=digest(args.library.read_bytes()),scope='Bounded dense borrowed-buffer reverse-reachability kernel only; caller supplies separate valid buffers; no file/env/observation semantics or complete-engine speed comparison.')


def modularity():
    specs={};roots=[]
    for component in range(20):
        for level in range(8):specs[f'c{component}/n{level}']=facts.Spec(deps=(f'c{component}/n{level-1}',) if level else ())
        roots.append(f'c{component}/n7')
    dirty={'c0/n0'};exact={r for r in roots if dirty&facts.closure_nodes(specs,r)};rows=[]
    for policy in ('exact','aligned','scrambled','global'):
        if policy=='exact':selected=exact
        else:
            partition={n:(n.split('/')[0] if policy=='aligned' else n.split('/')[1] if policy=='scrambled' else 'all') for n in specs}
            reverse=defaultdict(set)
            for name,spec in specs.items():
                for dep in spec.deps:
                    if partition[name]!=partition[dep]:reverse[partition[dep]].add(partition[name])
            affected={partition[n] for n in dirty};pending=list(affected)
            while pending:
                n=pending.pop()
                for parent in reverse[n]-affected:affected.add(parent);pending.append(parent)
            selected={r for r in roots if partition[r] in affected}
        assert exact<=selected;rows.append(dict(partition=policy,selected_roots=len(selected),unnecessary_roots=len(selected-exact)))
    return dict(fine_nodes=len(specs),roots=len(roots),rows=rows,scope='Same fine graph and roots, different conservative coarsening; tests boundary-induced over-invalidation, not changing programarchitecture or biologicalmodularity performance.')


def scheduler_study(args):
    rows=[]
    for period in (15,40,100):
        for error in (False,True):
            tasks=scheduling.fixture(period=period)
            for policy in ('fifo','critical','fair','work-stealing','foraging'):
                row=lock_run(args.lock,lambda:scheduling.simulate(tasks,policy,estimate_error=error));result=row.pop('value');rows.append(dict(period=period,estimate_error=error,harness=row,result=result))
        row=lock_run(args.lock,lambda:scheduling.simulate(scheduling.fixture(period=period),'fifo',cancellation=False));result=row.pop('value');rows.append(dict(period=period,estimate_error=False,harness=row,result=result))
    return dict(rows=rows,scope='Synthetic discreteevent tasks withdeclaredcompute/coldsetup modelunits; cancellation onlyatsafequantum boundaries; durablebulkworkneverdiscarded andstalecompletionnotpublished. Modelunitsare notmeasuredcompiler walltime; decisionharnesscost ismeasured separately. No actualservice integration.')


def retention_study(args):
    nodes=retention.fixture();traces={'alternating':['lint','binary']*4,'hot-lint':['lint']*6+['binary']*2,'reverse-hot':['binary']*6+['lint']*2};rows=[]
    for budget in (7,9,12,20):
        for name,requests in traces.items():
            oracle=lock_run(args.lock,lambda:retention.optimal(nodes,requests,budget));optimal=oracle.pop('value')
            for policy in ('retain-all','lru','cost-size'):
                sample=lock_run(args.lock,lambda:retention.simulate(nodes,requests,budget,policy));result=sample.pop('value')
                assert result['peak_bytes']<=budget
                if result['status']=='complete':assert optimal['status']=='complete' and result['cost']>=optimal['cost']
                rows.append(dict(budget=budget,trace=name,policy=policy,result=result,offline_oracle=optimal,oracle_harness=oracle,harness=sample))
    return dict(nodes={n:asdict(v) for n,v in nodes.items()},rows=rows,scope='Sequential sixnode DAGmodel, explicit dependency leases and simultaneous producer scratch counted. Bytes/work are modelunits, not processRSS or measuredcompiler cost. Oracle hasfutureknowledge and is boundedto12nodes; heuristics mayreportinfeasible ratherthanexceedbudget.')


def main():
    parser=argparse.ArgumentParser()
    for name in ('work','output','lock'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--ninja-project',type=Path);parser.add_argument('--clang',type=Path);parser.add_argument('--library',type=Path);parser.add_argument('--trials',type=int,default=3)
    args=parser.parse_args();args.work.mkdir(parents=True,exist_ok=False);args.output.mkdir(parents=True,exist_ok=True);args.lock.parent.mkdir(parents=True,exist_ok=True)
    sources=[p for p in HERE.iterdir() if p.suffix in ('.py','.odin')];pins={p.name:digest(p.read_bytes()) for p in sources}
    data=dict(schema='GAIA-SCIENCE-GRAPHS-1',status='running',python=sys.version,platform=platform.platform(),source_sha256=pins,studies={})
    try:
        for name,run in [('patches',patch_study),('dynamic-facts',graph_study),('captured-ninja',captured_ninja),('compiler-probe',compiler_probe),('native-frontier',native_probe),('scheduling',scheduler_study),('retention',retention_study)]:
            print('START',name,flush=True);data['studies'][name]=run(args);save(args.output/'results.json',data);print('DONE',name,flush=True)
        data['studies']['modularity']=modularity()
        assert pins=={p.name:digest(p.read_bytes()) for p in sources};data['source_pins_verified_after']=True;data['status']='complete'
    except Exception as error:
        data['status']='failed';data['error']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(args.output/'results.json',data)


if __name__=='__main__':main()

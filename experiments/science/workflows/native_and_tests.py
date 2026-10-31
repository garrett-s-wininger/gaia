import importlib,json,random,subprocess,sys,time
from pathlib import Path
from common import HERE,checked,filepin,lock,timed

def native(args):
    host=args.native/'module-host';libraries={name:args.native/f'{name}.so' for name in ('v1','v2','bad')};rows=[]
    before={p.name:filepin(p) for p in [host,*libraries.values()]}
    # Identical serial declared-state workload for every arrangement.
    trace=[1]*16+[2]*16+[1]*16;expected=[];state=0
    for version in trace:state+=version;expected.append(dict(version=version,state=state,result=10*(version+1)+state))
    def run(mode):
        state=0;observations=[]
        if mode=='fresh-per-request':
            for version in trace:
                result=checked([host,libraries[f'v{version}'],version,state],input=b'run 10\nstop\n');response=json.loads(result.stdout);state=response['state'];observations.append(response)
        else:
            process=subprocess.Popen([str(host),str(libraries['v1']),'1','0'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            commands=[];current=1
            for version in trace:
                if version!=current:commands.append(f'load {libraries[f"v{version}"]} {version}');current=version
                commands.append('run 10')
            commands.append('stop')
            if mode=='batch-existing-host':
                output,errors=process.communicate('\n'.join(commands)+'\n',timeout=30);assert process.returncode==0,errors
                responses=list(map(json.loads,output.splitlines()));observations=[r for cmd,r in zip(commands,responses) if cmd.startswith('run ')]
            else:
                for command in commands:
                    process.stdin.write(command+'\n');process.stdin.flush()
                    if command=='stop':break
                    response=json.loads(process.stdout.readline())
                    if command.startswith('run '):observations.append(response)
                process.stdin.close();assert process.wait(timeout=30)==0,process.stderr.read()
        assert all(r['ok'] for r in observations)
        assert [{k:r[k] for k in ('version','state','result')} for r in observations]==expected
        return len(observations)
    for block in range(args.trials):
        modes=['fresh-per-request','batch-existing-host','resident-online'];random.Random(block).shuffle(modes)
        for mode in modes:
            with lock(args.lock):sample=timed(lambda:run(mode))
            rows.append(dict(block=block,mode=mode,wall_ns=sample['wall_ns'],requests=sample['value']))
    command=f'run 10\nload {libraries["bad"]} 3\nrun 10\nload {libraries["v2"]} 99\nrun 10\nload {args.native/"missing.so"} 1\nrun 10\nstop\n'
    result=checked([host,libraries['v1'],1,0],input=command.encode());validation=list(map(json.loads,result.stdout.splitlines()))
    assert [r['ok'] for r in validation]==[True,False,True,False,True,False,True]
    assert [r['result'] for r in validation if r['ok']]==[21,22,23,24]
    assert before=={p.name:filepin(p) for p in [host,*libraries.values()]}
    return dict(rows=rows,validation=validation,tools=before,
                scope='48 declared scalar requests and two compatible module replacements. Host-owned integer state survives only at serial quiescent points. Candidate ABI/version/missing image rejected before publication; pure trusted modules only, no arbitrary constructor rollback, state migration, pointer/callback/thread live-patching or ORC claim. Compile/link preparation excluded and separately recorded.')

def doctests(args):
    from doctest_worker import MODULES,pin
    pins={name:pin(importlib.import_module(name)) for name in MODULES};requests=[dict(module=name,source_sha256=pins[name],token=f'e{epoch}-{name}') for epoch in range(3) for name in MODULES];rows=[]
    argv=[sys.executable,'-B',str(HERE/'doctest_worker.py')]
    expected=None
    def run(mode):
        results=[]
        if mode=='fresh-per-request':
            for request in requests:results.append(json.loads(checked(argv,input=(json.dumps(request)+'\n').encode()).stdout))
        elif mode=='batch-existing-api':
            results=list(map(json.loads,checked(argv,input=('\n'.join(map(json.dumps,requests))+'\n').encode()).stdout.splitlines()))
        else:
            process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            for request in requests:
                process.stdin.write(json.dumps(request)+'\n');process.stdin.flush();results.append(json.loads(process.stdout.readline()))
            process.stdin.close();assert process.wait(timeout=30)==0,process.stderr.read()
        assert len(results)==len(requests) and all(r['ok'] and r['failed']==0 for r in results)
        return [(r['token'],r['attempted']) for r in results]
    for block in range(args.trials):
        modes=['fresh-per-request','batch-existing-api','resident-online'];random.Random(77+block).shuffle(modes)
        for mode in modes:
            with lock(args.lock):sample=timed(lambda:run(mode))
            if expected is None:expected=sample['value']
            assert sample['value']==expected
            rows.append(dict(block=block,mode=mode,wall_ns=sample['wall_ns'],test_attempts=sum(x[1] for x in sample['value']),requests=len(requests)))
    guards=[dict(module='difflib',source_sha256='0'*64,token='stale'),dict(module='invalid',token='invalid'),requests[0]]
    responses=list(map(json.loads,checked(argv,input=('\n'.join(map(json.dumps,guards))+'\n').encode()).stdout.splitlines()))
    assert not responses[0]['ok'] and responses[1]['failed']==1 and responses[2]['ok']
    assert pins=={name:pin(importlib.import_module(name)) for name in MODULES}
    return dict(rows=rows,source_pins=pins,guards=responses,
                scope='Actual installed CPython difflib/statistics/fractions documentation-test subset,189examples per full module pass; Decimal context supplied identically. Existing doctest API and batched runner are strong controls. Nine requests per session; source pin rejection and expected failing example then recovery tested. No full CPython/production application suite, process snapshot, external-resource reset or general fixture isolation claim.')

#!/usr/bin/env python3
"""Isolate existing Python/Odin reader paths on exact observed Django requests.

No implementation changes: both named APIs return owned bytes and verify CRC.
An Odin ordinal diagnostic separately bypasses the Python name/wrapper layer.
It changes the request API, so it is not a fair named-provider speedup claim.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
import benchmark
from native_loader import NativeBundleReader
from precomputed_index import IndexedBundleReader


def worker(args):
    request=json.loads(args.request.read_text())
    rng=random.Random(request['seed'])
    factories={
        'python':lambda:IndexedBundleReader(request['archive'],request['index'],index_sha256=request['pin'],verify='local'),
        'odin':lambda:NativeBundleReader(request['archive'],request['index'],index_sha256=request['pin'],verify='local',library=request['library']),
    }
    readers={};opening={};open_cpu={}
    order=list(factories);rng.shuffle(order)
    for name in order:
        begin=time.perf_counter();cpu=time.process_time()
        readers[name]=factories[name]()
        open_cpu[name]=time.process_time()-cpu;opening[name]=time.perf_counter()-begin
    native=readers['odin']
    names=request['names'];rows=[native.entries[n].index for n in names]
    expected=[readers['python'].read(n) for n in names]
    for name,value in zip(names,expected):
        if native.read(name)!=value:raise RuntimeError('reader bytes differ')
    payload_bytes=sum(map(len,expected))
    functions={'python-named':readers['python'].read,'odin-named':native.read,
               'odin-ordinal':lambda row:native._ffi.read(native._handle,row)}
    samples={name:[] for name in functions};cpu_samples={name:[] for name in functions}
    token=sum(len(v)+(v[0]+v[-1] if v else 0) for v in expected)
    def scan(name):
        read=functions[name];requests=rows if name=='odin-ordinal' else names
        checksum=0
        for _ in range(args.repeat):
            for key in requests:
                value=read(key)
                checksum+=len(value)+(value[0]+value[-1] if value else 0)
        return checksum
    for name in functions:
        if scan(name)!=token*args.repeat:raise RuntimeError('warmup result differs')
    for _ in range(args.blocks):
        order=list(functions);rng.shuffle(order)
        for name in order:
            begin=time.perf_counter();cpu=time.process_time()
            checksum=scan(name)
            cpu_samples[name].append((time.process_time()-cpu)/args.repeat)
            samples[name].append((time.perf_counter()-begin)/args.repeat)
            if checksum!=token*args.repeat:raise RuntimeError('timed result differs')
    # Attribute constructor CPU separately; never substitute profiles for timings.
    profiles={}
    if args.profile:
        import cProfile,pstats
        for name in factories:
            profile=cProfile.Profile();profile.enable();reader=factories[name]();profile.disable()
            stats=pstats.Stats(profile);reader.close()
            profiles[name]=dict(total_self_seconds=stats.total_tt,functions=[
                dict(file=f,line=l,function=n,calls=calls,self_seconds=own,inclusive_seconds=total)
                for (f,l,n),(_,calls,own,total,_) in sorted(stats.stats.items(),key=lambda x:x[1][2],reverse=True)])
    for reader in readers.values():reader.close()
    print(json.dumps(dict(correct=True,requests=len(names),payload_bytes=payload_bytes,
                          payload_sha256=hashlib.sha256(b''.join(expected)).hexdigest(),
                          opening_seconds=opening,opening_cpu_seconds=open_cpu,
                          native_timings=native.native_timings,scans_seconds=samples,
                          scans_cpu_seconds=cpu_samples,constructor_profiles=profiles)))


def render(data,path):
    lines=['# CPython/Odin bridge diagnosis','',f"Run: `{data['run_id']}`.",'',
           'Existing reader/library implementations, exact Django REST dependency-code request traces. '
           'Both named APIs return owned Python bytes with payload CRC verification. No module execution, '
           'compilation or Django initialization is timed. No native kernel or bridge optimization is '
           'introduced. The Python reader delegates mapping, CRC and copying to native runtime libraries.', '',
           f"{data['trials']} fresh processes per corpus, warm filesystem cache. Both readers open once "
           'in randomized order within each process. Read variants are interleaved in randomized blocks '
           'after warmup. Each block repeats the entire trace; reported scans are normalized by repeat '
           'count, then median within each process and across fresh processes. Setup is reported separately. '
           'CPU observations and all raw blocks are retained. The separate Odin ordinal variant '
           'bypasses the Python name/wrapper API and is a diagnostic, not a named-provider comparison.', '',
           '| Input | Requests | Payload MiB | Python open ms | Odin open ms | Python named scan ms | Odin named scan ms | Odin ordinal scan ms |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for case in data['cases']:
        samples=case['samples'];med=lambda f:statistics.median(f(s) for s in samples)
        values=[med(lambda s:s['opening_seconds'][k])*1000 for k in ('python','odin')]
        values += [med(lambda s:statistics.median(s['scans_seconds'][k]))*1000 for k in ('python-named','odin-named','odin-ordinal')]
        lines.append(f"| {case['mode']} | {samples[0]['requests']} | {samples[0]['payload_bytes']/2**20:.3f} | "+' | '.join(f'{v:.3f}' for v in values)+' |')
    lines += ['', 'The common Python request loop/checksum is included in every scan. Constructor profiles '
              'are separate instrumented observations and must not be used as subdivisions of unprofiled '
              'timings. This test measures bridge-inclusive reads, not a pure ABI-only call cost. It cannot '
              'by itself prove that startup differences are ABI overhead or inefficient Odin codegen. '
              'Read loops follow validation/warmup, so they exclude first-touch payload page faults '
              'and are not a partition of application startup. '
              'Natural full-application timings remain in the parent Django report.', '']
    path.write_text('\n'.join(lines))


def run(args):
    source=json.loads(args.inputs.read_text())
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work=benchmark.HERE/'_work'/('bridge-'+run_id);work.mkdir(parents=True)
    args.output.mkdir(parents=True,exist_ok=True)
    data=dict(run_id=run_id,parent_run_id=source['run_id'],trials=args.trials,repeat=args.repeat,blocks=args.blocks,
              environment=benchmark.environment(work),native=source['native'],cases=[])
    for mode in ('source','bytecode'):
        original=next(c for c in source['cases'] if c['scenario']=='rest' and c['mode']==mode and c['reader']=='odin')
        input=next(i for i in source['scenarios']['rest']['inputs'] if i['mode']==mode)
        names=[]
        for name,count in original['samples'][0]['executed_files'].items():
            if mode=='bytecode':name=name+'c' if name.endswith('.py') else name
            names.extend([name]*count)
        case=dict(mode=mode,samples=[],commands=[]);data['cases'].append(case)
        for trial in range(args.trials):
            request=dict(archive=input['archive'],index=input['index'],pin=input['index_sha256'],
                         library=source['native']['path'],names=names,seed=20261029+trial)
            path=work/f'{mode}-{trial}.json';benchmark.write_json(path,request)
            command=[sys.executable,'-I','-S','-B',str(Path(__file__).resolve()),'--worker','--request',str(path),
                     '--repeat',str(args.repeat),'--blocks',str(args.blocks)]
            # Instrument only one additional observation, after the timed set.
            case['commands'].append(command)
            case['samples'].append(benchmark.consume(command))
        command=case['commands'][0]+['--profile']
        case['profile_observation']=benchmark.consume(command)
        print('verified bridge trace',mode,case['samples'][0]['requests'],flush=True)
    benchmark.write_json(args.output/'results.json',data);render(data,args.output/'REPORT.md')
    print(args.output/'REPORT.md')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--request',type=Path)
    parser.add_argument('--profile',action='store_true')
    parser.add_argument('--inputs',type=Path,default=benchmark.HERE/'_work/runs/django/results.json')
    parser.add_argument('--output',type=Path,default=benchmark.HERE/'_work/runs/bridge')
    parser.add_argument('--trials',type=int,default=15)
    parser.add_argument('--repeat',type=int,default=16);parser.add_argument('--blocks',type=int,default=11)
    args=parser.parse_args()
    if min(args.trials,args.repeat,args.blocks)<1:parser.error('positive trials/repeats/blocks required')
    if args.worker:worker(args)
    else:run(args)

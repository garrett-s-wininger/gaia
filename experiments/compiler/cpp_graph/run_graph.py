"""Four-target real C++ integration graph, Ninja+ccache versus programmatic host."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import time

import graph
from capture import arguments as capture_arguments

HERE=Path(__file__).resolve().parent


def arguments():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=HERE/'_work/downloads/fmt-12.2.0.tar.gz')
    parser.add_argument('--llvm',type=Path,required=True);parser.add_argument('--host',type=Path,required=True);parser.add_argument('--blake3-helper',type=Path,required=True)
    parser.add_argument('--blake3-library',type=Path,default=Path('/usr/lib/libblake3.so'));parser.add_argument('--ninja',type=Path,required=True);parser.add_argument('--ccache',type=Path,required=True);parser.add_argument('--tool-library-path',type=Path)
    parser.add_argument('--cache-policy',choices=('baseline-seeded','repeated-trace'),default='baseline-seeded');parser.add_argument('--trials',type=int,default=3);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    if args.trials<1:parser.error('positive trials required')
    return args


def main(args):
    args.output.mkdir(parents=True,exist_ok=True)
    if (args.output/'results.json').exists():raise ValueError('fresh output required')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/('graph-'+run_id);work.mkdir();info=graph.prepare(args,work)
    data=dict(run_id=run_id,status='prepared',trials=args.trials,cache_policy=args.cache_policy,source_url=graph.SOURCE_URL,source_sha256=graph.SOURCE_SHA,graph=[{k:v for k,v in t.items() if k not in ('original_link','captured_link')} for t in info['targets']],sdk_search=info['roots'],admitted_files=len(info['files']),admitted_bytes=sum(map(len,info['files'].values())),crt_aliases=info['aliases'],work=str(work),cases=[],boundaries=[],implementation_sha256={str(p.relative_to(HERE)):graph.sha(p.read_bytes()) for p in [*HERE.glob('*.py'),*HERE.joinpath('fixture').glob('*')] if p.is_file()})
    def save():
        (args.output/'results.json').write_bytes(graph.canonical(data))
    if args.prepare_only:save();return
    baseline={str(p):p.read_bytes() for p in info['fixture'].glob('*') if p.is_file()};report=info['fixture']/'report.cpp';header=info['fixture']/'graph.h'
    def state(name):
        desired=dict(baseline)
        if name=='source':desired[str(report)]=desired[str(report)].replace(b'value + graph_bias + 0',b'value + graph_bias + 1')
        if name=='header':desired[str(header)]=desired[str(header)].replace(b'graph_bias = 0',b'graph_bias = 1')
        for path,body in desired.items():
            if Path(path).read_bytes()!=body:Path(path).write_bytes(body)
    references={};objects={};reference_dir=work/'references';reference_dir.mkdir()
    for scenario in ('unchanged','source','header'):
        state(scenario);output=reference_dir/scenario;references[scenario]=graph.cli_build(info,output,trace=scenario=='unchanged');objects[scenario]={t['name']:{n:graph.sha((output/n).read_bytes()) for n in t['objects']} for t in info['targets']};graph.verify_runtime(output,scenario,info['env'])
        if scenario=='unchanged':data['crt_alias_proof']=graph.alias_proof(info,output)
        print('CLI reference',scenario,'verified',flush=True)
    references['revert']=references['unchanged'];objects['revert']=objects['unchanged'];state('unchanged')
    # Resolve runtime/tool dependency files as well as recursive LLD trace inputs.
    for tool in [*info['tools'],reference_dir/'unchanged/report-cli',reference_dir/'unchanged/graph-test']:
        p=graph.run(['ldd',tool],env=info['env'])
        for line in p.stdout.splitlines():
            for token in line.split():
                path=Path(token)
                if token.startswith('/') and path.is_file() and not str(path.resolve()).startswith(str(reference_dir.resolve())+'/'):info['sdk_inputs'].add(str(path))
    data['external_input_sha256']={p:graph.sha(Path(p).read_bytes()) for p in sorted(info['sdk_inputs'])};data['references']=references;data['reference_objects']=objects
    data['versions']={name:graph.run([tool,'--version'],env=info['env']).stdout.splitlines()[0] for name,tool in (('clang',info['cpp']),('ninja',args.ninja),('ccache',args.ccache))}
    data['common_sources_sha256']={p.name:graph.sha(p.read_bytes()) for p in [graph.HERE.parent/name for name in ('benchmark.py','object_cache_benchmark.py','project_benchmark.py','shared_inputs.py','resident_host.py','blake3_digest.py')]}
    frozen=work/'sources';frozen.mkdir()
    for relative in data['implementation_sha256']:
        target=frozen/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(HERE/relative,target)
    for name in data['common_sources_sha256']:shutil.copy2(HERE.parent/name,frozen/name)
    data['source_snapshots']=str(frozen);engines={}
    def verify(engine,sample,scenario):
        if sample['artifacts']!=references[scenario]:raise ValueError('whole-graph CLI artifact identity differs: '+engine.name+' '+scenario)
        graph.verify_runtime(engine.output,scenario,info['env'])
        for native in sample['targets']:
            if not native['skip']:
                target=next(t for t in info['targets'] if t['name']==native['target']);expected=[objects[scenario][target['name']][n] for n in target['objects']]
                if native['object_sha256']!=expected:raise ValueError('native intermediate object differs from independent CLI')
    try:
        for name in ('ninja-ccache','programmatic'):
            state('unchanged');begin=time.perf_counter();engines[name]=graph.Engine(name,info,args,work);startup=time.perf_counter()-begin;sample=engines[name].build();verify(engines[name],sample,'unchanged');data['boundaries'].append(dict(engine=name,engine_setup_seconds=startup,clean=sample));print('clean boundary',name,'verified',flush=True)
        seeds=work/'baseline-object-seeds';seeds.mkdir()
        if args.cache_policy=='baseline-seeded':
            shutil.copytree(work/'ccache',seeds/'ccache')
            for target in info['targets']:shutil.copytree(engines['programmatic'].output/target['name']/'store',seeds/target['name'])
        data['cache_lifetimes']=dict(object_cache='restored baseline-only before each block' if args.cache_policy=='baseline-seeded' else 'retained across the whole repeated trace',input_session='resident sealed segments and authenticated input digests retained across blocks',linked_history='disabled; only current target receipt retained',seed_restore_timing='outside operation timing')
        data['status']='running';save();rng=random.Random(716)
        for block in range(args.trials):
            if args.cache_policy=='baseline-seeded':
                state('unchanged')
                shutil.rmtree(work/'ccache');shutil.copytree(seeds/'ccache',work/'ccache')
                for target in info['targets']:
                    destination=engines['programmatic'].output/target['name']/'store';shutil.rmtree(destination);shutil.copytree(seeds/target['name'],destination)
            for scenario in ('unchanged','source','header','revert'):
                state(scenario);order=list(engines);rng.shuffle(order)
                for name in order:
                    sample=engines[name].build();verify(engines[name],sample,scenario)
                    if name=='programmatic':
                        links=sum(n['link_calls'] for n in sample['targets']);executions=sum(n['compiler_executions'] for n in sample['targets'])
                        if links!=(0 if scenario=='unchanged' else 3):raise ValueError('whole-graph relink contract')
                        expected_executions={'unchanged':0,'source':1,'header':4,'revert':0}[scenario]
                        if args.cache_policy=='baseline-seeded' and executions!=expected_executions:raise ValueError('fresh-edit compilation count mismatch')
                        if args.cache_policy=='repeated-trace' and executions>expected_executions:raise ValueError('unexpected recompilation or lost history')
                        if not sample['targets'][0]['skip']:raise ValueError('unrelated fmt target rebuilt')
                    elif scenario=='unchanged' and 'no work to do' not in sample['messages']:raise ValueError('Ninja no-op baseline performed work')
                    data['cases'].append(dict(engine=name,scenario=scenario,block=block,**sample));print(block,scenario,name,round(sample['seconds']*1000,3),'ms',flush=True)
            save()
        data['status']='complete';save()
    finally:
        for engine in engines.values():engine.close()
    summary=[];paired=[]
    for scenario in ('unchanged','source','header','revert'):
        for name in engines:
            ss=[s for s in data['cases'] if s['engine']==name and s['scenario']==scenario]
            summary.append(dict(engine=name,scenario=scenario,median_ms=statistics.median(s['seconds']*1000 for s in ss),min_ms=min(s['seconds']*1000 for s in ss),max_ms=max(s['seconds']*1000 for s in ss),native_compiler_executions=[sum(n['compiler_executions'] for n in s['targets']) for s in ss],native_link_calls=[sum(n['link_calls'] for n in s['targets']) for s in ss]))
        differences=[]
        for block in range(args.trials):
            a=next(s for s in data['cases'] if s['engine']=='programmatic' and s['scenario']==scenario and s['block']==block);b=next(s for s in data['cases'] if s['engine']=='ninja-ccache' and s['scenario']==scenario and s['block']==block);differences.append((a['seconds']-b['seconds'])*1000)
        paired.append(dict(scenario=scenario,deltas_ms=differences,programmatic_wins=sum(x<0 for x in differences)))
    (args.output/'summary.json').write_text(json.dumps(dict(run_id=run_id,cache_policy=args.cache_policy,cache_lifetimes=data['cache_lifetimes'],rows=summary,paired=paired,boundaries=data['boundaries'],graph=data['graph'],admitted_files=data['admitted_files'],admitted_bytes=data['admitted_bytes']),indent=2)+'\n')
    (args.output/'validation.json').write_text(json.dumps(dict(passed=True,timed_operations=len(data['cases']),clean_boundaries=2,independent_cli_artifacts_and_runtime_match=True,all_native_object_sha256_match=True,crt_original_alias_links_byte_identical=True,prepost_source_sdk_link_pins_checked=True,whole_link_history_disabled_both=True,raw_sha256=graph.sha((args.output/'results.json').read_bytes())),indent=2)+'\n')

if __name__=='__main__':main(arguments())

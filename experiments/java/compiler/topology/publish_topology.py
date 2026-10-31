import json, hashlib, shutil, statistics
from pathlib import Path
import argparse
_parser=argparse.ArgumentParser(description='Validate complete topology runs and retain portable compact summaries.')
_parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[4])
ROOT=_parser.parse_args().root.resolve()
BASE=ROOT/'experiments/java/compiler/topology'
MIB=1048576

def dump(p,x):
    p.write_text(json.dumps(x,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def med(x):return statistics.median(x)
def mem(x):return {k:x[k] for k in ('rss_bytes','pss_bytes','private_bytes','read_ns')}
def heap(batch):return {k:sum(r[k] for r in batch['replies']) for k in ('heap_used','heap_committed')}
def validate(d,configs):
    assert d['status']=='complete' and d['admitted_input_postcheck'] is True
    assert d['aggregate_heap_cap_mib']==3072 and len(d['shared_cpu_affinity'])==8 and d['tasks_per_batch']==8
    assert {(c['block'],c['slots'],c['jvms']) for c in d['cases']}=={(b,*c) for b in range(d['trials']) for c in configs}
    assert len(d['cases'])==len(configs)*d['trials']
    expected=d['preparation']['expected']; batches=targets=0
    for c in d['cases']:
        j=c['jvms']; assert c['workers_per_jvm']*j==c['slots'] and len(c['ready'])==j
        assert sum(r['heap_max'] for r in c['ready'])==3072*MIB
        for f in c['vm_flags']:
            assert f==[f'-Xms{max(8,64//j)}m',f'-Xmx{3072//j}m','-XX:+UseG1GC',f'-XX:ActiveProcessorCount={8//j}','-Xshare:on','-XX:-UsePerfData']
        assert len(c['vm_flags'])==j and len(c['steady'])==d['steady_batches']
        for b in [c['first'],c['warmup'],*c['steady']]:
            got={}; assert len(b['replies'])==j and b['seconds']>0
            for r in b['replies']:
                assert r['ok'] and r['workers']==c['workers_per_jvm']
                for o in r['outputs']:
                    n=o['target'];assert n not in got;got[n]=o
                    assert {k:o[k] for k in ('classes','bytes','sha256')}==expected[n%2]
            assert set(got)==set(range(8));batches+=1;targets+=8
        assert c['consumer']['targets']==8 and c['consumer']['versions']=={str(i):d['preparation']['target_versions'][i%2] for i in range(8)}
        assert c['shutdown_seconds']>=0 and c['whole_session_seconds']>0
        if d['gc_diagnostic']:
            assert len(c['gc_diagnostic']['replies'])==j and all(r['ok'] and r['requested_gc'] for r in c['gc_diagnostic']['replies'])
        for key in ['memory_ready','memory_after_first','memory_after_warmup','memory_after_steady','memory_after_consumer']:
            m=c[key];assert len(m['processes'])==j
            for metric in ('rss_bytes','pss_bytes','private_bytes'):assert m[metric]==sum(x[metric] for x in m['processes'])
    snapshots=Path(d['source_snapshots']); source_current={
        'run_topology.py':BASE/'run_topology.py','TopologyHarness.java':BASE/'TopologyHarness.java',
        'CompilerHarness.java':BASE.parent/'CompilerHarness.java','benchmark.py':BASE.parent/'benchmark.py'}
    # Current source can acquire a documented non-timing regression test later, but measured sources must match snapshots.
    for name,pin in d['source_sha256'].items():
        assert sha(snapshots/name)==pin
        assert sha(source_current[name])==pin,(name,'current differs')
    return {'complete':True,'cases':len(d['cases']),'validated_batches_including_warmup':batches,'validated_target_compilations':targets,'validated_class_outputs':targets*227,'consumer_target_checks':len(d['cases'])*8,'all_normal_shutdowns':True,'aggregate_heap_and_flags_checked':True,'final_admitted_input_postcheck':True,'frozen_sources_match_current':True}

def publish(kind,src,configs):
    d=json.loads(src.read_text()); validation=validate(d,configs)
    out=BASE/'results'/kind;out.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(src,out/'results.json')
    compact=[]
    for c in d['cases']:
        item={k:c[k] for k in ['block','slots','jvms','workers_per_jvm','start_seconds','shutdown_seconds','whole_session_seconds']}
        item['batch_seconds']={'first':c['first']['seconds'],'warmup_excluded':c['warmup']['seconds'],'late':[x['seconds'] for x in c['steady']]}
        item['late_case_median_seconds']=med(item['batch_seconds']['late'])
        item['jvm_cpu_seconds']={'first':c['first']['jvm_cpu_seconds'],'late':[x['jvm_cpu_seconds'] for x in c['steady']]}
        item['memory']={k:mem(c[k]) for k in ['memory_ready','memory_after_first','memory_after_warmup','memory_after_steady','memory_after_consumer']}
        item['heap_after_late']=heap(c['steady'][-1])
        if 'samples' in c:
            item['sample_count']=len(c['samples']);item['sampled_sequential_aggregate_max']=c['sampled_peak']
            item['samples']=[{k:s[k] for k in ['elapsed_ns','rss_bytes','pss_bytes','private_bytes','read_ns']} for s in c['samples']]
            item['requested_gc']={'memory':mem(c['gc_diagnostic']['memory']),'heap':heap(c['gc_diagnostic'])}
        compact.append(item)
    grouped=[]
    for slots,j in configs:
        cs=[c for c in compact if (c['slots'],c['jvms'])==(slots,j)]
        grouped.append({'slots':slots,'jvms':j,'blocks':len(cs),'startup_seconds':med([c['start_seconds'] for c in cs]),'first_batch_seconds':med([c['batch_seconds']['first'] for c in cs]),'late_case_median_seconds':med([c['late_case_median_seconds'] for c in cs]),'after_late_pss_bytes':med([c['memory']['memory_after_steady']['pss_bytes'] for c in cs]),'after_late_private_bytes':med([c['memory']['memory_after_steady']['private_bytes'] for c in cs]),'after_late_rss_bytes':med([c['memory']['memory_after_steady']['rss_bytes'] for c in cs]),'after_late_heap_used_bytes':med([c['heap_after_late']['heap_used'] for c in cs]),'after_late_heap_committed_bytes':med([c['heap_after_late']['heap_committed'] for c in cs])})
    pairs=[]
    for slots in sorted({s for s,j in configs if s>1}):
        blocks=[]
        for b in range(d['trials']):
            one=next(c for c in compact if (c['block'],c['slots'],c['jvms'])==(b,slots,1))
            many=next(c for c in compact if (c['block'],c['slots'],c['jvms'])==(b,slots,slots))
            blocks.append({'block':b,'one_first_seconds':one['batch_seconds']['first'],'many_first_seconds':many['batch_seconds']['first'],'one_late_seconds':one['late_case_median_seconds'],'many_late_seconds':many['late_case_median_seconds'],'one_pss_bytes':one['memory']['memory_after_steady']['pss_bytes'],'many_pss_bytes':many['memory']['memory_after_steady']['pss_bytes']})
        pairs.append({'slots':slots,'blocks':blocks,'one_first_wins':sum(b['one_first_seconds']<b['many_first_seconds'] for b in blocks),'one_late_wins':sum(b['one_late_seconds']<b['many_late_seconds'] for b in blocks),'one_after_late_pss_wins':sum(b['one_pss_bytes']<b['many_pss_bytes'] for b in blocks)})
    summary={'schema_version':1,'run_id':d['run_id'],'scope':'Whole-target Picocli compiler pool topology; late window is not a convergence claim','aggregate_heap_cap_mib':3072,'common_cpu_count':8,'tasks_per_batch':8,'late_batches_per_case':d['steady_batches'],'trials':d['trials'],'sample_interval_seconds':d['sampler_interval_seconds'],'gc_diagnostic':d['gc_diagnostic'],'groups':grouped,'pairs':pairs,'cases':compact}
    dump(out/'summary.json',summary);dump(out/'validation.json',validation)
    prep=d['preparation']
    provenance={'run_id':d['run_id'],'raw':{'path':str((out/'results.json').relative_to(ROOT)),'bytes':src.stat().st_size,'sha256':sha(src)},'source_sha256':d['source_sha256'],'source_snapshot_policy':'Four measured driver/harness sources frozen in ignored raw work directory and checked against current sources at publication','jdk':prep['java'],'setup':prep['setup'],'source_a_sha256':prep['source_sha256'],'source_b_sha256':prep['second_source_sha256'],'expected_outputs':prep['expected'],'target_versions':prep['target_versions'],'origin_prepared_sha256':prep['origin_prepared_sha256'],'admitted_file_count':len(prep['admitted_files']),'admitted_sha256_by_role':{('application/harness.jar' if k==prep['app'] else 'target-sdk/'+str(Path(k).relative_to(prep['jdk'])) if Path(k).is_relative_to(prep['jdk']) else 'runtime-image/'+str(Path(k).relative_to(prep['image'])) if Path(k).is_relative_to(prep['image']) else 'source-a/'+str(Path(k).relative_to(prep['source'])) if Path(k).is_relative_to(prep['source']) else 'source-b/'+str(Path(k).relative_to(prep['second_source']))):v for k,v in prep['admitted_files'].items()},'admitted_input_policy':'Listed application jar, target javac/modules, selected image java/modules/libjvm/CDS and both listed source trees pinned before execution and rehashed after all cases; not a full OS or runtime closure','collection':'Sequential Linux smaps_rollup reads; per-case probes outside batch clocks; optional sampler can perturb diagnostic latency'}
    provenance['publication_sources_sha256']={n:sha(BASE/n) for n in ['publish_topology.py','test_topology.py','test_lifecycle.py']}
    dump(out/'provenance.json',provenance)
    print(kind,json.dumps({'run':d['run_id'],'validation':validation,'raw':provenance['raw']},indent=2))
    return d,summary,out

if __name__=='__main__':
    publish('primary',BASE/'_work/main-perfdata-off/results.json',[(1,1),(2,1),(2,2),(4,1),(4,4),(8,1),(8,8)])
    publish('long-memory',BASE/'_work/long-memory/results.json',[(4,1),(4,4),(8,1),(8,8)])

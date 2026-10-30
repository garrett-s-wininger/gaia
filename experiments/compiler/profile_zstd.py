"""Separate instrumented phase attribution over completed Zstd controls."""
import json
from pathlib import Path
import shutil
import benchmark as base
import project_benchmark as project

HERE=base.HERE

def run():
    out=HERE/'_work/runs/zstd-handoff';d=json.loads((out/'results.json').read_text())
    if d['status']!='complete':raise ValueError('timing must finish before profiling')
    host=HERE/'_work/followup-hosts/profile/build/host';rows=[]
    for config in ('release','debug'):
        case=next(c for c in d['cases'] if c['name']==config+'-direct')
        output=Path(d['work'])/(config+'-profile');output.mkdir()
        cmd=case['command'].copy();cmd[0]=str(host);cmd[6]=str(output)
        p=project.run_checked(cmd,cwd=output);sample=json.loads(p.stdout)
        expected=case['warmup']['artifacts_sha256']
        if not sample['correct'] or sample['buffer_hits']!=d['jobs'] or sample['buffer_misses']:raise ValueError('profile build incomplete')
        artifacts=dict(zip(d['objects'],sample['object_sha256']));artifacts['libzstd.so']=base.sha(output/'libzstd.so')
        if artifacts!=expected:raise ValueError('profile changed artifacts')
        trace=json.loads((output/'compiler-trace.json').read_text());events=trace['traceEvents'];totals={}
        for e in events:
            if e.get('ph')=='X' and not e.get('name','').startswith('Total '):totals[e['name']]=totals.get(e['name'],0)+e.get('dur',0)
        jobs=[]
        for e in events:
            if e.get('name')!='GaiaJob' or e.get('ph')!='X':continue
            index=int(e['args']['detail']);args=case['commands'][index];source=next(x for x in args if x.endswith('.c'))
            jobs.append(dict(index=index,source=source,start_us=e['ts'],duration_us=e['dur']))
        if len(jobs)!=d['jobs']:raise ValueError('trace omitted jobs')
        target=out/f'compiler-{config}-trace.json';shutil.copy2(output/'compiler-trace.json',target)
        rows.append(dict(config=config,command=cmd,result=sample,artifacts_sha256=artifacts,event_totals_us=totals,jobs=jobs,trace=str(target)))
        print('profiled',config,flush=True)
    base.save(out/'phase-profiles.json',dict(run_id=d['run_id'],timed=False,host_sha256=base.sha(host),rows=rows,
        build_provenance=json.loads((HERE/'_work/followup-hosts/profile/build.json').read_text()),analyzer_sha256=base.sha(Path(__file__))))
    lines=['# Zstandard compiler phases','', 'Separate instrumented runs; artifact identities match the completed timed controls. Durations '
      'are summed job/event wall spans across eight workers, including descheduling. These are not '
      'CPU samples or independent additive stages: backend contains optimizer/code-generation subphases.','',
      '| Configuration | Sum job spans ms | Frontend ms | Backend ms | Optimizer ms | CodeGenPasses ms |',
      '| --- | ---: | ---: | ---: | ---: | ---: |']
    for row in rows:
        t=row['event_totals_us'];lines.append('| '+row['config']+' | '+' | '.join(f"{t.get(k,0)/1000:.2f}" for k in ('GaiaJob','Frontend','Backend','Optimizer','CodeGenPasses'))+' |')
    lines+=['','The raw traces include every job and finer nested phases. Profiling overhead is excluded '
        'from all latency tables. The library configuration, optimization/debug flags and compiler '
        'lifecycle are unchanged. No compilation result is reused.','']
    (out/'PHASES.md').write_text('\n'.join(lines))

if __name__=='__main__':run()

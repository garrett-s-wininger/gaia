#!/usr/bin/env python3
"""One instrumented whole-target endpoint across JVM and Native Image runtimes."""
import argparse
import json
import random
import statistics
from pathlib import Path
from run_native import run
from run_variants import write


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--references',type=Path,required=True)
    parser.add_argument('--modules',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--trials',type=int,default=3)
    parser.add_argument('--warm-count',type=int,default=12)
    parser.add_argument('--short',action='store_true')
    args=parser.parse_args()
    if not 1<=args.warm_count<=32 or args.trials<1:parser.error('bounded positive counts required')
    p=json.loads(args.prepared.read_text());config=json.loads(args.config.read_text());refs=json.loads(args.references.read_text())
    w=args.output;w.mkdir(parents=True,exist_ok=True)
    data=dict(schema_version=2,status='running',prepared=p,runtimes=config,references=refs,warm_count=args.warm_count,short=args.short,cases=[])
    rng=random.Random(5807)
    for block in range(args.trials):
        order=list(config);rng.shuffle(order)
        for name in order:
            spec=config[name];output=w/(name+str(block));(output/'broken').mkdir(parents=True,exist_ok=True)
            (output/'broken/Broken.java').write_text('class Broken { this is invalid; }\n')
            command=[*spec['prefix'],p['source'],p['second_source'],p.get('target_sdk',p['jdk']),str(output)]
            if spec.get('modules',True):command.append(str(args.modules))
            fresh=run(command,['first'])
            requests=['first',*['warm']*args.warm_count]
            if not args.short:requests+=['edit','fail','warm']
            resident=run(command,requests)
            expected=refs[spec['reference']]
            for row in fresh['requests']+resident['requests']:
                if row['request']=='fail':
                    if row.get('ok') is not False:raise ValueError('accepted invalid source')
                else:
                    reference=expected['1' if row['request']=='edit' else '0']
                    if any(row.get(k)!=reference[k] for k in ('classes','bytes','sha256')):raise ValueError((name,row,reference))
                    if row['compile_ns']<=0:raise ValueError('missing compile phase')
            data['cases'].append(dict(block=block,engine=name,fresh=fresh,resident=resident))
            write(w/'results.json',data)
    summary={}
    for name in config:
        rows=[r for r in data['cases'] if r['engine']==name]
        late=[r['resident']['requests'][i] for r in rows for i in range(max(1,args.warm_count-2),args.warm_count+1)]
        summary[name]=dict(fresh_ms=statistics.median(r['fresh']['elapsed_seconds']*1000 for r in rows),
            first_compile_ms=statistics.median(r['resident']['requests'][0]['compile_ns']/1e6 for r in rows),
            late_compile_ms=statistics.median(r['compile_ns']/1e6 for r in late),
            late_thread_cpu_ms=statistics.median(r['compile_thread_cpu_ns']/1e6 for r in late if r['compile_thread_cpu_ns']>=0) if any(r['compile_thread_cpu_ns']>=0 for r in late) else None,
            late_process_cpu_ms=statistics.median(r['process_cpu_seconds']*1000 for r in late),
            late_request_ms=statistics.median(r['wall_seconds']*1000 for r in late),
            rss_bytes=statistics.median(r['resident']['requests'][args.warm_count]['rss_bytes'] for r in rows),
            lifecycle_cpu_seconds=statistics.median(r['resident']['cpu_seconds'] for r in rows))
    data.update(status='complete',summary=summary);write(w/'results.json',data);print(json.dumps(summary,indent=2))


if __name__=='__main__':main()

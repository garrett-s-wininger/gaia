"""Exercise upstream Zstd examples against every final cache-control library."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import benchmark as base
import project_benchmark as project
import object_cache_benchmark as bench

HERE=base.HERE
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=HERE/'_work/runs/object-cache/results.json')
    args=parser.parse_args();out=args.results.parent;d=json.loads(args.results.read_text())
    if d['status']!='complete':raise ValueError('finish timing first')
    parent=json.loads((HERE/'_work/runs/zstd-handoff/results.json').read_text())
    examples=[Path(parent['work'])/n for n in ('simple_compression','simple_decompression','streaming_compression','streaming_decompression')]
    work=Path(d['work'])/'upstream-checks';work.mkdir();rows=[]
    bodies=[b'',b'cache-invalidation-test'*4,bytes(((i*37)^(i//97))&255 for i in range(1048576))]
    targets=[(c['name'],Path(c['output'])) for c in d['cases']]+[(name+'-cli',Path(s['reference'])) for name,s in d['inputs']['scenarios'].items()]
    for name,root in targets:
        soname=root/'libzstd.so.1'
        if not soname.exists():soname.symlink_to('libzstd.so')
        before=base.sha(root/'libzstd.so');env={**bench.cache_env(),'LD_LIBRARY_PATH':str(root)}
        listing=project.run_checked(['ldd',str(examples[0])],env=env).stdout
        if str(soname) not in listing:raise ValueError('loaded a different library')
        logs=[listing]
        for body in bodies:
            inp=work/'input';inp.write_bytes(body);archive=work/'input.zst'
            for compressor in (examples[0],examples[2]):
                p=project.run_checked([str(compressor),str(inp)],env=env);logs.append(p.stdout+p.stderr)
                if compressor==examples[0]:
                    p=project.run_checked([str(examples[1]),str(archive)],env=env);logs.append(p.stdout+p.stderr)
                p=subprocess.run([str(examples[3]),str(archive)],env=env,capture_output=True,timeout=180)
                if p.returncode or p.stdout!=body:raise ValueError('upstream round-trip failed')
                logs.append(f'{compressor.name}: {len(body)} bytes round-trip matched')
        if base.sha(root/'libzstd.so')!=before:raise ValueError('checks changed library')
        log=out/(name+'-examples.txt');log.write_text('\n'.join(logs))
        rows.append(dict(case=name,passed=True,roundtrips=6,library_sha256=before,library_unchanged=True,log=str(log)))
    base.save(out/'upstream-checks.json',dict(run_id=d['run_id'],timed=False,rows=rows,
        example_executable_sha256={str(p):base.sha(p) for p in examples},checker_sha256=base.sha(Path(__file__))))
    print('verified',len(rows)*6,'upstream byte-exact round trips against',len(rows),'libraries')

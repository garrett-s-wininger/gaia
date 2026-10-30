"""Single-job, stable-tie and priority-order checks for the scheduling driver."""
import argparse
import ctypes
import json
from pathlib import Path
import subprocess
import tempfile
import benchmark as base
import project_benchmark as project

HERE=base.HERE

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host',type=Path,required=True)
    base.toolchain_arguments(p,headers=False)
    p.add_argument('--output',type=Path,default=HERE/'_work/runs/cost-scheduling/small-queue-checks.json');a=p.parse_args()
    host=a.host.resolve();clang=a.llvm.resolve()/'bin/clang';lld=a.llvm.resolve()/'bin/ld.lld';rows=[]
    # Retain fixtures under ignored work for independent replay.
    work=Path(tempfile.mkdtemp(prefix='schedule-small-',dir=HERE/'_work'))
    for weights in ([0],[7,7],[9,0,15]):
        n=len(weights);root=work/str(n);root.mkdir();commands=[]
        for i in range(n):
            src=root/f'unit{i}.c';src.write_text(f'unsigned f_{i}(unsigned x) {{ return x+{i}u; }}\n')
            commands.append([str(clang),'--target=x86_64-unknown-linux-gnu','-O2','-fPIC','-c',str(src),'-o',f'unit{i}.o'])
        plan=root/'compile.gcr';plan.write_bytes(project.encode_requests(commands));objects=[f'unit{i}.o' for i in range(n)]
        link=[str(lld),'-shared','--threads=1','--build-id=sha1','-o','libx.so',*objects]
        lp=root/'link.gcr';lp.write_bytes(project.encode_requests([link]));costs=root/'costs.txt';costs.write_text('GAIACOST1\n'+'\n'.join(map(str,weights))+'\n')
        reference=root/'reference';reference.mkdir()
        for cmd in commands:project.run_checked(cmd,cwd=reference)
        project.run_checked(link,cwd=reference);expected={x:base.sha(reference/x) for x in [*objects,'libx.so']}
        for mode in ('file','direct'):
            out=root/mode;out.mkdir();cmd=[str(host),'physical',str(clang),str(root),'-','-',str(out),str(plan),'8','internal',str(lld),str(lp),mode,'cost',str(costs)]
            proc=project.run_checked(cmd,cwd=out);s=json.loads(proc.stdout)
            if proc.stderr or not s['correct'] or s['errors'] or s['warnings'] or s['compiled']!=n or not 1<=s['peak_active']<=n or s['link_calls']!=1:raise ValueError('small queue did not complete')
            if s['schedule']!=sorted(range(n),key=lambda i:-weights[i]):raise ValueError('small queue priority/tie order failed')
            if mode=='direct':
                actual=dict(zip(objects,s['object_sha256']))
                if s['buffer_hits']!=n or s['buffer_misses'] or any((out/x).exists() for x in objects):raise ValueError('small direct handoff failed')
            else:actual={x:base.sha(out/x) for x in objects}
            actual['libx.so']=base.sha(out/'libx.so')
            if actual!=expected:raise ValueError('small queue changed artifacts')
            lib=ctypes.CDLL(str(out/'libx.so'))
            for i in range(n):
                fn=getattr(lib,f'f_{i}');fn.argtypes=[ctypes.c_uint];fn.restype=ctypes.c_uint
                if fn(91)!=91+i:raise ValueError('executed output differs')
            rows.append(dict(jobs=n,mode=mode,weights=weights,cost_bytes=costs.stat().st_size,passed=True,result=s,command=cmd))
    base.save(a.output,dict(host_sha256=base.sha(host),work=str(work),timed=False,rows=rows,checker_sha256=base.sha(Path(__file__))))
    print('verified six small-queue cases, artifact identities and executed functions')

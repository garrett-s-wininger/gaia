#!/usr/bin/env python3
"""Prepare stock Roslyn and joint application-only composite ReadyToRun."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from pe_info import inspect
HERE=Path(__file__).resolve().parent
ASSEMBLIES=('csc.dll','Microsoft.CodeAnalysis.dll','Microsoft.CodeAnalysis.CSharp.dll')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def run(args):
    args.tools=args.tools.resolve();args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=True)
    sdk=args.tools/'sdk';source=sdk/'sdk/10.0.403/Roslyn/bincore';runtime=sdk/'shared/Microsoft.NETCore.App/10.0.14'
    stock=args.output/'stock';shutil.copytree(source,stock);inputs=args.output/'input';inputs.mkdir()
    for name in ASSEMBLIES:shutil.copyfile(source/name,inputs/name)
    composite=args.output/'composite';composite.mkdir()
    for name in ('csc.deps.json','csc.runtimeconfig.json'):shutil.copyfile(source/name,composite/name)
    tool=args.tools/'crossgen2/tools/crossgen2';tool.chmod(0o755)
    cmd=[str(tool),'--composite','-O','--parallelism:2','--targetos:linux','--targetarch:x64',
         '--compositerootpath:'+str(inputs),'-o:'+str(composite/'roslyn.r2r.dll')]
    cmd += ['-r:'+str(p) for p in sorted(runtime.glob('*.dll'))]
    cmd += [str(inputs/name) for name in ASSEMBLIES]
    began=time.perf_counter();p=subprocess.run(cmd,cwd=composite,capture_output=True,text=True);elapsed=time.perf_counter()-began
    (args.output/'crossgen.stdout.txt').write_text(p.stdout);(args.output/'crossgen.stderr.txt').write_text(p.stderr)
    if p.returncode:raise RuntimeError('crossgen2 failed: '+p.stderr[-4000:])
    facts=dict(seconds=elapsed,command=cmd,stock={name:dict(sha256=sha(stock/name),bytes=(stock/name).stat().st_size,pe=inspect(stock/name)) for name in ASSEMBLIES},
       runtime_corelib=dict(sha256=sha(runtime/'System.Private.CoreLib.dll'),pe=inspect(runtime/'System.Private.CoreLib.dll')),
       files={p.relative_to(args.output).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(composite.rglob('*')) if p.is_file()})
    (args.output/'preparation.json').write_text(json.dumps(facts,indent=2)+'\n');print(json.dumps(facts,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tools',type=Path,default=HERE/'_work');p.add_argument('--output',type=Path,default=HERE/'_work/prepared')
    run(p.parse_args())

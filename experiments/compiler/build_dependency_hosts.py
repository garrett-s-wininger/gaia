"""Build the dependency-journal consumer and native snapshot delta producer."""
import argparse
from pathlib import Path
import shutil
import subprocess
import time
import benchmark as base
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    base.toolchain_arguments(p)
    p.add_argument('--blake3-library',type=Path,help='Optional BLAKE3 library for the caller digest helper')
    p.add_argument('--sha256-library',type=Path,help='Optional OpenSSL crypto shared library for the digest comparison')
    p.add_argument('--work',type=Path,default=base.HERE/'_work/dependency-development');a=p.parse_args()
    a.work.mkdir(parents=True,exist_ok=True)
    if (a.work/'build').exists():p.error('select a fresh --work directory to preserve measured binaries')
    crypto=[a.sha256_library.resolve()] if a.sha256_library else []
    host,info=base.build(a,a.work,bridge='accelerated_dependency_bridge.cpp' if crypto else 'dependency_bridge.cpp',odin_source='dependency_host.odin',extra_libraries=[
        a.llvm/'lib/liblldELF.so',a.llvm/'lib/liblldCommon.so','-ldl',*crypto,
        '-Wl,--export-dynamic-symbol=_ZN4llvm12MemoryBuffer7getFileERKNS_5TwineEbbbSt8optionalINS_5AlignEE'])
    base.save(a.work/'build.json',info)
    odin=base.odin_executable()
    for name in ('snapshot','decision'):
        obj=a.work/(name+'.o');producer=a.work/(name+'-host')
        commands=[[odin,'build',str(base.HERE/(name+'_host.odin')),'-file','-o:speed','-build-mode:obj','-out:'+str(obj)],
            [str(a.llvm/'bin/clang'),str(obj),'-pthread','-ldl','-o',str(producer)]]
        begin=time.perf_counter()
        for cmd in commands:
            p=subprocess.run(cmd,capture_output=True,text=True)
            if p.returncode:raise RuntimeError(p.stdout+p.stderr)
        base.save(a.work/(name+'-build.json'),dict(commands=commands,seconds=time.perf_counter()-begin,host_sha256=base.sha(producer)))
        print(producer,flush=True)
    if a.blake3_library:
        helper=a.work/'blake3-helper.so'
        cmd=[str(a.llvm/'bin/clang'),'-O3','-fPIC','-shared',str(base.HERE/'blake3_bridge.c'),str(a.blake3_library.resolve()),'-o',str(helper)]
        result=subprocess.run(cmd,capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        base.save(a.work/'blake3-build.json',dict(command=cmd,helper_sha256=base.sha(helper),library_sha256=base.sha(a.blake3_library.resolve())))
        print(helper,flush=True)
    print(host)

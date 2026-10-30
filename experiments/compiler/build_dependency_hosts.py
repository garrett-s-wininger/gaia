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
    p.add_argument('--work',type=Path,default=base.HERE/'_work/dependency-development');a=p.parse_args()
    a.work.mkdir(parents=True,exist_ok=True)
    if (a.work/'build').exists():p.error('select a fresh --work directory to preserve measured binaries')
    host,info=base.build(a,a.work,bridge='dependency_bridge.cpp',odin_source='dependency_host.odin',extra_libraries=[
        a.llvm/'lib/liblldELF.so',a.llvm/'lib/liblldCommon.so','-ldl',
        '-Wl,--export-dynamic-symbol=_ZN4llvm12MemoryBuffer7getFileERKNS_5TwineEbbbSt8optionalINS_5AlignEE'])
    base.save(a.work/'build.json',info)
    odin=base.odin_executable();obj=a.work/'snapshot.o';producer=a.work/'snapshot-host'
    commands=[[odin,'build',str(base.HERE/'snapshot_host.odin'),'-file','-o:speed','-build-mode:obj','-out:'+str(obj)],
        [str(a.llvm/'bin/clang++'),str(obj),'-pthread','-ldl','-o',str(producer)]]
    begin=time.perf_counter()
    for cmd in commands:subprocess.run(cmd,check=True,capture_output=True,text=True)
    base.save(a.work/'snapshot-build.json',dict(commands=commands,seconds=time.perf_counter()-begin,host_sha256=base.sha(producer)))
    print(host);print(producer)

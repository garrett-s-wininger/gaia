"""Build the Odin scheduling host with the existing Clang/LLD handoff adapter."""
import argparse
from pathlib import Path
import benchmark as base

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    base.toolchain_arguments(p)
    p.add_argument('--work',type=Path,default=base.HERE/'_work/schedule-development')
    a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    if (a.work/'build').exists():p.error('build directory already exists; use --work with a fresh path to preserve recorded host binaries')
    host,info=base.build(a,a.work,bridge='handoff_bridge.cpp',odin_source='schedule_host.odin',extra_libraries=[
        a.llvm/'lib/liblldELF.so',a.llvm/'lib/liblldCommon.so','-ldl',
        '-Wl,--export-dynamic-symbol=_ZN4llvm12MemoryBuffer7getFileERKNS_5TwineEbbbSt8optionalINS_5AlignEE'])
    base.save(a.work/'build.json',info);print(host)

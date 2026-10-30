"""Build the Odin local object-cache experiment."""
import argparse
from pathlib import Path
import benchmark as base
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    base.toolchain_arguments(p)
    p.add_argument('--work',type=Path,default=base.HERE/'_work/cache-development')
    a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    if (a.work/'build').exists():p.error('use --work with a fresh directory to preserve existing measured binaries')
    host,info=base.build(a,a.work,bridge='cache_bridge.cpp',odin_source='cache_host.odin',extra_libraries=[
        a.llvm/'lib/liblldELF.so',a.llvm/'lib/liblldCommon.so','-ldl',
        '-Wl,--export-dynamic-symbol=_ZN4llvm12MemoryBuffer7getFileERKNS_5TwineEbbbSt8optionalINS_5AlignEE'])
    base.save(a.work/'build.json',info);print(host)

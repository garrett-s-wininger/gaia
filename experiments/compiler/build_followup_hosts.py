"""Build the separate lifetime and diagnostic-only compiler-trace hosts."""
from pathlib import Path
import argparse
import benchmark as base

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    base.toolchain_arguments(parser)
    parser.add_argument('--work',type=Path,default=base.HERE/'_work/followup-hosts')
    args=parser.parse_args()
    args.llvm=args.llvm.resolve();args.llvm_headers=args.llvm_headers.resolve()
    args.work.mkdir(parents=True,exist_ok=True)
    for name,bridge,host in [('lifecycle','lifecycle_bridge.cpp','lifecycle_host.odin'),('profile','profile_bridge.cpp','handoff_host.odin')]:
        work=args.work/name;work.mkdir(exist_ok=True)
        if (work/'build').exists():raise SystemExit('build path exists; preserve old binaries or select a fresh work path before rebuilding: '+str(work/'build'))
        binary,info=base.build(args,work,bridge=bridge,odin_source=host,extra_libraries=[
            args.llvm/'lib/liblldELF.so',args.llvm/'lib/liblldCommon.so','-ldl',
            '-Wl,--export-dynamic-symbol=_ZN4llvm12MemoryBuffer7getFileERKNS_5TwineEbbbSt8optionalINS_5AlignEE'])
        base.save(work/'build.json',info);print(name,binary,flush=True)

"""Build the Linux Odin/OpenSSL batched condition verifier in a fresh directory."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import benchmark as base

def build(args):
    work=args.work.resolve();work.mkdir(parents=True,exist_ok=True);library=work/'verify.so'
    if library.exists():raise ValueError('choose a fresh work directory')
    odin=base.odin_executable();source=base.HERE/'condition_verify.odin';obj=work/'verify.o'
    commands=[[odin,'build',str(source),'-file','-o:speed','-build-mode:obj','-reloc-mode:pic','-out:'+str(obj)],
              [str(args.llvm/'bin/clang'),'-shared',str(obj),str(args.crypto.resolve()),'-pthread','-ldl','-o',str(library)]]
    begin=time.perf_counter()
    for command in commands:subprocess.run(command,check=True,capture_output=True,text=True)
    meta=dict(seconds=time.perf_counter()-begin,commands=commands,odin_version=subprocess.check_output([odin,'version'],text=True),
              source_sha256=base.sha(source),library_sha256=base.sha(library),crypto_sha256=base.sha(args.crypto),
              libraries=subprocess.check_output(['ldd',str(library)],text=True))
    (work/'build.json').write_text(json.dumps(meta,indent=2)+'\n');print(library)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--llvm',type=Path,default=Path('/usr/lib/llvm22'))
    p.add_argument('--crypto',type=Path,default=Path('/usr/lib/libcrypto.so.3'));p.add_argument('--work',type=Path,required=True)
    build(p.parse_args())

#!/usr/bin/env python3
"""Declare a bounded non-Cartesian GC/JIT and prepared-code comparison."""
import argparse
import hashlib
import json
from pathlib import Path
from run_variants import VM, write


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--oracle',type=Path,required=True)
    parser.add_argument('--ea',type=Path,required=True)
    parser.add_argument('--data',type=Path,required=True)
    args=parser.parse_args();w=args.data;p=json.loads(args.prepared.read_text());graal=Path(p['jdk']);app=p['app']
    def java(jdk,flags):return [str(jdk/'bin/java'),*VM,*flags,'-cp',app,'NativeCompiler']
    def spec(prefix,reference):return dict(prefix=prefix,reference=reference,modules=True)
    g1=['-XX:+UseG1GC'];c2=['-XX:-UseJVMCICompiler','-XX:-EnableJVMCI']
    flags={
        'g1':spec(java(args.oracle,g1),'oracle25'),
        'serial':spec(java(args.oracle,['-XX:+UseSerialGC']),'oracle25'),
        'parallel':spec(java(args.oracle,['-XX:+UseParallelGC']),'oracle25'),
        'zgc':spec(java(args.oracle,['-XX:+UseZGC']),'oracle25'),
        'c1-level1':spec(java(args.oracle,[*g1,'-XX:TieredStopAtLevel=1']),'oracle25'),
        'c1-level3':spec(java(args.oracle,[*g1,'-XX:TieredStopAtLevel=3']),'oracle25'),
        'c2-only':spec(java(args.oracle,[*g1,'-XX:-TieredCompilation']),'oracle25')}
    head={
        'graal-jit-g1':spec(java(graal,g1),'graal25'),
        'graal-jit-serial':spec(java(graal,['-XX:+UseSerialGC']),'graal25'),
        'graal-c2-g1':spec(java(graal,[*c2,*g1]),'graal25'),
        'graal-c2-shenandoah':spec(java(graal,[*c2,'-XX:+UseShenandoahGC']),'graal25'),
        'ea-g1':spec(java(args.ea,g1),'ea26'),
        'ea-aot-no-code':spec(java(args.ea,[*g1,'-XX:+UnlockDiagnosticVMOptions','-XX:-AOTCodeCaching','-XX:AOTMode=on','-XX:AOTCache='+str(w/'leyden-cache/no-code.aot')]),'ea26'),
        'ea-aot-code':spec(java(args.ea,[*g1,'-XX:AOTMode=on','-XX:AOTCache='+str(w/'leyden-cache/code.aot')]),'ea26'),
        'native-o2-serial':spec([str(w/'native-final-serial/native-compiler'),'-Xms32m','-Xmx768m','-Djava.home='+p['jdk']],'graal25')}
    epsilon={name:spec([str(w/('native-final-'+gc)/'native-compiler'),'-Xms32m','-Xmx768m','-Djava.home='+p['jdk']],'graal25') for name,gc in [('serial','serial'),('epsilon','epsilon')]}
    for name,value in [('flags-config',flags),('head-config',head),('epsilon-config',epsilon)]:write(w/(name+'.json'),value)
    runtimes={}
    for name,jdk in [('oracle25',args.oracle),('graal25',graal),('ea26',args.ea)]:
        runtimes[name]=dict(p,jdk=str(jdk),target_sdk=p['jdk'],jdk_modules_sha256=hashlib.sha256((jdk/'lib/modules').read_bytes()).hexdigest(),target_sdk_modules_sha256=p['jdk_modules_sha256'])
    write(w/'runtime-fixtures.json',runtimes)
    print('configs written')


if __name__=='__main__':main()

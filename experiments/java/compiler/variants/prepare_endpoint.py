#!/usr/bin/env python3
"""References, actual-compiler GC probes and one recording for two EA caches."""
import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from run_variants import VM, RUN_ENV, cli_reference, write
from run_native import run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,required=True)
    args=parser.parse_args();w=args.data;fixtures=json.loads((w/'runtime-fixtures.json').read_text());refs={}
    for name,p in fixtures.items():
        refs[name]={str(i):cli_reference(p,i,w/'references'/name/str(i)) for i in (0,1)}
    write(w/'endpoint-references.json',refs)
    p=fixtures['ea26'];cache=w/'leyden-cache';cache.mkdir(exist_ok=True);config=cache/'training.aotconfig';out=cache/'training-outputs';out.mkdir(exist_ok=True)
    command=[str(Path(p['jdk'])/'bin/java'),*VM,'-XX:+UseG1GC','-XX:AOTMode=record','-XX:AOTConfiguration='+str(config),'-cp',p['app'],'NativeCompiler',p['source'],p['second_source'],p['target_sdk'],str(out),str(w/'platform-sdk')]
    training=run(command,['first','warm','warm','warm','warm']);write(cache/'training.json',training)
    if any(not r['ok'] or r['sha256']!=refs['ea26']['0']['sha256'] for r in training['requests']):raise ValueError('training differs')
    for name,flags in [('code',[]),('no-code',['-XX:+UnlockDiagnosticVMOptions','-XX:-AOTCodeCaching'])]:
        image=cache/(name+'.aot');cmd=[str(Path(p['jdk'])/'bin/java'),*VM,'-XX:+UseG1GC',*flags,'-XX:AOTMode=create','-XX:AOTConfiguration='+str(config),'-XX:AOTCache='+str(image),'-cp',p['app']];begin=time.perf_counter();r=subprocess.run(cmd,capture_output=True,text=True,env=RUN_ENV);row=dict(command=cmd,seconds=time.perf_counter()-begin,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr,bytes=image.stat().st_size if image.exists() else 0);write(cache/(name+'-setup.json'),row)
        if r.returncode:raise RuntimeError(row)
    diagnostics={};head=json.loads((w/'head-config.json').read_text())
    for name,key in [('code','ea-aot-code'),('no-code','ea-aot-no-code')]:
        spec=head[key];log=cache/('diagnostic-'+name+'.log');prefix=spec['prefix'];index=prefix.index('-cp');cmd=[*prefix[:index],'-Xlog:aot*=info:file='+str(log),*prefix[index:],p['source'],p['second_source'],p['target_sdk'],str(out),str(w/'platform-sdk')];result=run(cmd,['first']);text=log.read_text();diagnostics[name]=dict(result=result,loaded_code_entries=re.findall(r'Loaded (\d+) AOT code entries',text),unable_to_use_code='Unable to use AOT Code Cache' in text)
    diagnostics['code_usable']=any(int(n)>0 for n in diagnostics['code']['loaded_code_entries']) and not diagnostics['code']['unable_to_use_code'];write(cache/'diagnostics.json',diagnostics)
    if not diagnostics['code_usable']:raise RuntimeError('AOT code cache not proven usable; inspect diagnostics')
    # Probe actual compiler work under every requested JVM configuration; java -version is insufficient.
    all_specs={**json.loads((w/'flags-config.json').read_text()),**head};probes={};flags={}
    for name,spec in all_specs.items():
        p=fixtures[spec['reference']];out=w/'endpoint-probes'/name;(out/'broken').mkdir(parents=True,exist_ok=True);(out/'broken/Broken.java').write_text('class Broken { this is invalid; }\n')
        cmd=[*spec['prefix'],p['source'],p['second_source'],p['target_sdk'],str(out),str(w/'platform-sdk')];result=run(cmd,['first','warm']);probes[name]=result
        if any(not r['ok'] or r['sha256']!=refs[spec['reference']]['0']['sha256'] for r in result['requests']):raise ValueError(('GC endpoint',name,result))
        if '-cp' in spec['prefix']:
            prefix=spec['prefix'][:-1];r=subprocess.run([*prefix,'-XX:+PrintFlagsFinal','-version'],capture_output=True,text=True,env=RUN_ENV)
            flags[name]=dict(returncode=r.returncode,effective_lines=[line.strip() for line in r.stdout.splitlines() if any(re.search(r'\b'+key+r'\b',line) for key in ('UseJVMCICompiler','EnableJVMCI','TieredCompilation','TieredStopAtLevel','UseG1GC','UseSerialGC','UseParallelGC','UseZGC','UseShenandoahGC'))],stderr=r.stderr)
        write(w/'endpoint-probes.json',probes);write(w/'effective-flags.json',flags)
    print('references, code admission and endpoint GC probes passed')


if __name__=='__main__':main()

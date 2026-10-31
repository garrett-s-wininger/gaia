#!/usr/bin/env python3
"""Correctness and bounded Epsilon growth diagnostics, separate from primary clocks."""
import argparse
import json
import os
import subprocess
from pathlib import Path
from run_variants import VM, AFFINITY, RUN_ENV, write
from run_native import run


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',type=Path,required=True);args=parser.parse_args();w=args.data;p=json.loads((w/'prepared-instrumented/prepared.json').read_text());specs=json.loads((w/'epsilon-config.json').read_text());refs=json.loads((w/'endpoint-references.json').read_text())['graal25'];base=Path(__file__).parent
    for name in ('serial','epsilon'):
        output=w/('native-correctness-'+name);(output/'broken').mkdir(parents=True,exist_ok=True);(output/'broken/Broken.java').write_text('class Broken { this is invalid; }\n');spec=specs[name];command=[*spec['prefix'],p['source'],p['second_source'],p['jdk'],str(output),str(w/'platform-sdk')];result=run(command,['edit','fail','warm'])
        for row in result['requests']:
            if row['request']=='fail':assert row['ok'] is False
            else:assert row['sha256']==refs['1' if row['request']=='edit' else '0']['sha256']
        write(w/('native-correctness-'+name+'.json'),result)
    # The native default jrt filesystem cannot supply target SDK bytecode; this must fail visibly.
    output=w/'instrumented-jrt-boundary';output.mkdir(exist_ok=True);command=[*specs['serial']['prefix'],p['source'],p['second_source'],p['jdk'],str(output)];boundary=run(command,['first']);assert boundary['requests'][0]['ok'] is False;write(w/'instrumented-runtime-boundaries.json',boundary)
    # Stop on first failure or at16 attempts. Never increase Epsilon's768MiB heap cap.
    output=w/'epsilon-growth-output';output.mkdir(exist_ok=True);command=[*specs['epsilon']['prefix'],p['source'],p['second_source'],p['jdk'],str(output),str(w/'platform-sdk')];proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=RUN_ENV,preexec_fn=lambda:os.sched_setaffinity(0,AFFINITY));ready=proc.stdout.readline();assert ready=='READY\n';rows=[]
    for index in range(16):
        proc.stdin.write('warm\n');proc.stdin.flush();line=proc.stdout.readline()
        if not line:break
        row=json.loads(line)
        for status in Path('/proc/'+str(proc.pid)+'/status').read_text().splitlines():
            if status.startswith('VmRSS:'):row['rss_bytes']=int(status.split()[1])*1024
        rows.append(row)
        if not row['ok']:break
    try:proc.stdin.write('stop\n');proc.stdin.flush()
    except BrokenPipeError:pass
    _,stderr=proc.communicate(timeout=30);write(w/'epsilon-growth.json',dict(command=command,max_attempts=16,successful_compilations=sum(bool(r['ok']) for r in rows),requests=rows,exit_code=proc.returncode,stderr=stderr))
    # Independent JVM consumption is outside native/compiler timing.
    checks=w/'consumer-classes';checks.mkdir(exist_ok=True);javac=[str(Path(p['jdk'])/'bin/javac'),'-J-XX:-UsePerfData','-proc:none','-cp',p['app'],'-d',str(checks),str(base/'NativeOutputCheck.java')];subprocess.run(javac,check=True,env=RUN_ENV)
    consumers=[]
    for name in ('serial','epsilon'):
        for token,version in [('warm','4.7.7'),('edit','4.7.7-gaia-probe')]:
            directory=w/('native-correctness-'+name)/token;command=[str(Path(p['jdk'])/'bin/java'),*VM,'-cp',p['app']+os.pathsep+str(checks),'NativeOutputCheck',str(directory),version];r=subprocess.run(command,capture_output=True,text=True,env=RUN_ENV);consumers.append(dict(command=command,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr));assert r.returncode==0
    write(w/'native-consumers.json',consumers)
    print('native output consumers, recovery, visible SDK boundary and bounded Epsilon growth complete')


if __name__=='__main__':main()

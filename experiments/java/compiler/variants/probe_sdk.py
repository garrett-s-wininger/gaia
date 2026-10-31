#!/usr/bin/env python3
"""Public-module export/readability probes for the alternate SDK representation."""
import argparse,json,subprocess,sys
from pathlib import Path
from run_variants import VM,write
from run_native import run
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));from benchmark import hashes
p=argparse.ArgumentParser();p.add_argument('--prepared',type=Path,required=True);p.add_argument('--modules',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--native',type=Path);a=p.parse_args();d=json.loads(a.prepared.read_text());w=a.output;w.mkdir(parents=True,exist_ok=True);rows=[]
fixtures={
 'sql':{'module-info.java':'module probe { requires java.sql; }','probe/Probe.java':'package probe; public class Probe { public java.sql.Connection value; }'},
 'unreadable':{'module-info.java':'module probe {}','probe/Probe.java':'package probe; public class Probe { public java.sql.Connection value; }'},
 'unexported':{'probe/Probe.java':'package probe; public class Probe { public jdk.internal.misc.Unsafe value; }'}
}
for name,files in fixtures.items():
 source=w/(name+'-source');source.mkdir(exist_ok=True)
 for rel,text in files.items():dest=source/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
 cliout=w/(name+'-cli');cliout.mkdir(exist_ok=True);cmd=[str(Path(d['jdk'])/'bin/javac'),'-proc:none','-g:none','--system',d['jdk'],'-d',str(cliout),*[str(source/n) for n in files]];r=subprocess.run(cmd,capture_output=True,text=True)
 row=dict(name=name,cli=dict(command=cmd,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr),endpoints={})
 for engine in (['jvm-jrt','jvm-modules','native-modules'] if a.native else ['jvm-jrt','jvm-modules']):
  output=w/(name+'-'+engine);output.mkdir(exist_ok=True);prefix=[str(a.native),'-Xms32m','-Xmx768m','-Djava.home='+d['jdk']] if engine.startswith('native') else [str(Path(d['jdk'])/'bin/java'),*VM,'-cp',d['app'],'NativeCompiler']
  cmd=[*prefix,str(source),str(source),d['jdk'],str(output)]+([str(a.modules)] if engine.endswith('modules') else [])
  result=run(cmd,['first']);row['endpoints'][engine]=result
  if result['requests'][0]['ok']!=(r.returncode==0):raise ValueError((name,engine,row))
  if r.returncode==0:
   expected=hashes(cliout)
   if any(result['requests'][0][k]!=expected[k] for k in ('classes','bytes','sha256')):raise ValueError(('module bytecode',name,engine,result,expected))
 rows.append(row);write(w/'probes.json',rows)
print('module probes passed',len(rows))

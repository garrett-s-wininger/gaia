#!/usr/bin/env python3
"""Real stock Roslyn csc CLI versus application-only composite R2R; same IL/JIT."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import time
from pe_info import inspect

HERE=Path(__file__).resolve().parent
MODES=('stock-r2r','composite-r2r')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def environment(tools):
    env=dict(os.environ)
    for key in list(env):
        if key.startswith('COMPlus_') or key in ['DOTNET_ReadyToRun','DOTNET_TieredCompilation','DOTNET_TieredPGO','DOTNET_TC_QuickJit']:
            env.pop(key)
    env.update(DOTNET_ROOT=str(tools/'sdk'),DOTNET_CLI_HOME=str(tools/'cli-home'),NUGET_PACKAGES=str(tools/'nuget'),
               DOTNET_CLI_TELEMETRY_OPTOUT='1',DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1',LANG='C.UTF-8')
    return env

def run(args):
    args.tools=args.tools.resolve();args.prepared=args.prepared.resolve();args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=True)
    sdk=args.tools/'sdk';dotnet=sdk/'dotnet';env=environment(args.tools);work=args.output/'work';work.mkdir()
    project=work/'project';project.mkdir()
    for source in (HERE/'fixture').glob('*.cs'):shutil.copyfile(source,project/source.name)
    references=sorted((sdk/'packs/Microsoft.NETCore.App.Ref/10.0.14/ref/net10.0').glob('*.dll'))
    flags=['/nologo','/nostdlib+','/target:exe','/optimize+','/nullable:enable','/deterministic+',
      '/debug:portable','/out:Application.dll','/pdb:Application.pdb','/refout:Application.ref.dll',
      '/preferreduilang:en-US','/pathmap:'+str(project)+'=/gaia']
    flags+=['/reference:'+str(p) for p in references]
    flags+=['Program.cs','Statistics.cs','Request.cs'];response=project/'compile.rsp';response.write_text('\n'.join(flags)+'\n')
    write(project/'Application.runtimeconfig.json',dict(runtimeOptions=dict(tfm='net10.0',framework=dict(name='Microsoft.NETCore.App',version='10.0.14'))))
    commands={'stock-r2r':[str(dotnet),str(args.prepared/'stock/csc.dll'),'/noconfig','@compile.rsp'],
              'composite-r2r':[str(dotnet),str(args.prepared/'composite/csc.dll'),'/noconfig','@compile.rsp']}
    def input_for(sequence,error=False):
        (project/'Request.cs').write_text('namespace GaiaFixture; public static class Request { public const int Sequence = '+('"bad"' if error else str(sequence))+'; }\n')
    def clean():
        for name in ('Application.dll','Application.pdb','Application.ref.dll'):(project/name).unlink(missing_ok=True)
    def artifacts():return {name:dict(bytes=(project/name).stat().st_size,sha256=sha(project/name)) for name in ('Application.dll','Application.pdb','Application.ref.dll') if (project/name).exists()}
    def call(mode,extra=None,monitor=False):
        start=time.perf_counter()
        if monitor:
            p=subprocess.Popen(commands[mode]+(extra or []),cwd=project,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);mapped=set()
            while p.poll() is None:
                try:mapped.update(line.rsplit(None,1)[-1] for line in Path(f'/proc/{p.pid}/maps').read_text().splitlines() if '.r2r.dll' in line and 'x' in line.split()[1])
                except FileNotFoundError:pass
                time.sleep(0.002)
            stdout,stderr=p.communicate();code=p.returncode
        else:
            p=subprocess.run(commands[mode]+(extra or []),cwd=project,env=env,capture_output=True,text=True,timeout=60);stdout,stderr,code=p.stdout,p.stderr,p.returncode;mapped=set()
        return dict(seconds=time.perf_counter()-start,status=code,stdout=stdout,stderr=stderr,mapped_composites=sorted(mapped))
    def validate(sample,sequence,error=False,expected=None):
        files=artifacts();sample['artifacts']=files
        if sample['stderr'] or sample['status']!=(1 if error else 0):raise ValueError(str(sample))
        semantic=(sample['status'],sample['stdout'],files)
        if expected is not None and semantic!=expected:raise ValueError('compiler diagnostics or deterministic artifacts differ')
        if error:
            if files or 'CS0029' not in sample['stdout']:raise ValueError('wrong error behavior')
        else:
            p=subprocess.run([str(dotnet),'Application.dll'],cwd=project,env=env,capture_output=True,text=True,check=True)
            result=json.loads(p.stdout)
            if result!=dict(request=sequence,names=['alpha','beta'],sum=6) or p.stderr:raise ValueError('emitted program differs')
        sample['validated']=True;return semantic
    preparation=json.loads((args.prepared/'preparation.json').read_text())
    data=dict(run_id=datetime.now(timezone.utc).isoformat(),trials=args.trials,preparation=preparation,
      sdk_provenance=json.loads((args.tools/'sdk-provenance.json').read_text()),crossgen_provenance=json.loads((args.tools/'crossgen-provenance.json').read_text()),
      source_sha256={p.name:sha(p) for p in [HERE/'benchmark.py',HERE/'prepare.py',HERE/'pe_info.py']},
      fixture_sha256={p.name:sha(p) for p in (HERE/'fixture').glob('*.cs')},references={p.name:sha(p) for p in references},
      scope='Fresh dotnet host+stock csc CLI+source/reference loading+full semantic compilation+deterministic PE/PDB/ref assembly writes+normal exit; warm page cache. Runtime R2R/tiering defaults unchanged.',
      warmups=[],cases=[],boundaries=[],memory=[])
    frozen=work/'sources';frozen.mkdir()
    for name in data['source_sha256']:shutil.copyfile(HERE/name,frozen/name)
    data['source_snapshots']=str(frozen)
    input_for(-1);expected=None
    for mode in MODES:
        clean();sample=call(mode,monitor=True);sample['mode']=mode;expected=validate(sample,-1,expected=expected);data['warmups'].append(sample)
    if not data['warmups'][1]['mapped_composites']:raise ValueError('composite image was not mapped by the real runtime')
    samples={m:[] for m in MODES};rng=random.Random(123)
    for block in range(args.trials):
        input_for(block);expected=None;order=list(MODES);rng.shuffle(order)
        for mode in order:
            clean();sample=call(mode);sample.update(mode=mode,block=block);expected=validate(sample,block,expected=expected);samples[mode].append(sample)
            print(block,mode,round(sample['seconds']*1000,2),'ms',flush=True)
        data['cases']=[dict(mode=m,samples=ss) for m,ss in samples.items()];write(args.output/'results.json',data)
    input_for(99,True);expected=None
    for mode in MODES:
        clean();sample=call(mode);sample['mode']=mode;expected=validate(sample,99,error=True,expected=expected);data['boundaries'].append(sample)
    input_for(100)
    for mode in MODES:
        clean();stdout_path=work/(mode+'-memory.stdout');stderr_path=work/(mode+'-memory.stderr')
        stdout_fd=os.open(stdout_path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600);stderr_fd=os.open(stderr_path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        pid=os.fork()
        if pid==0:
            try:
                os.chdir(project);os.dup2(stdout_fd,1);os.dup2(stderr_fd,2)
                os.execve(commands[mode][0],commands[mode],env)
            except BaseException:os._exit(127)
        os.close(stdout_fd);os.close(stderr_fd);_,status,usage=os.wait4(pid,0)
        validate(dict(status=os.waitstatus_to_exitcode(status),stdout=stdout_path.read_text(),stderr=stderr_path.read_text()),100)
        data['memory'].append(dict(mode=mode,peak_rss_kib=usage.ru_maxrss,user_seconds=usage.ru_utime,system_seconds=usage.ru_stime))
    write(args.output/'results.json',data)
    summary={k:v for k,v in data.items() if k not in ('cases','warmups','boundaries','source_snapshots')};summary['raw_sha256']=sha(args.output/'results.json');summary['cases']=[]
    for mode,ss in samples.items():
        summary['cases'].append(dict(mode=mode,median_ms=statistics.median(s['seconds'] for s in ss)*1000,
          min_ms=min(s['seconds'] for s in ss)*1000,max_ms=max(s['seconds'] for s in ss)*1000,
          wins_vs_stock=sum(a['seconds']<b['seconds'] for a,b in zip(ss,samples['stock-r2r'])),blocks=len(ss)))
    write(args.output/'summary.json',summary);write(args.output/'validation.json',dict(passed=True,operations=args.trials*2,warmups=2,error_checks=2,
      all_assemblies_pdbs_diagnostics_and_execution_match=True,composite_mapping_proved=True,raw_sha256=summary['raw_sha256']))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tools',type=Path,default=HERE/'_work');p.add_argument('--prepared',type=Path,default=HERE/'_work/prepared')
    p.add_argument('--trials',type=int,default=7);p.add_argument('--output',type=Path,default=HERE/'_work/results');run(p.parse_args())

"""Production Ninja C++ graph through shared source generations, one worker."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import shlex
import shutil
import subprocess
import tarfile
import time
from run_ir import Host,save,sha

def sha_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()

def run(args):
    args.output.mkdir(parents=True,exist_ok=False);project=args.output/'project';project.mkdir()
    with tarfile.open(args.archive) as archive:
        archive.extractall(project,filter='data')
    roots=list(project.iterdir());assert len(roots)==1;project=roots[0]
    env=dict(os.environ,CXX=str(args.clang),CXXFLAGS='-Werror=date-time',LD_LIBRARY_PATH=str(args.ccache.parent.parent/'lib')+':'+os.environ.get('LD_LIBRARY_PATH',''),CCACHE_DIR=str(args.output/'ccache'),CCACHE_COMPILERCHECK='content',CCACHE_BASEDIR='')
    def checked(command,**kw):
        p=subprocess.run(command,cwd=project,env=env,capture_output=True,text=True,timeout=240,**kw)
        if p.returncode:raise RuntimeError(p.stdout+p.stderr)
        return p
    start=time.perf_counter();configured=checked(['python3','configure.py']);config_seconds=time.perf_counter()-start
    compdb=json.loads(checked([str(args.ninja),'-t','compdb','cxx']).stdout);commands=checked([str(args.ninja),'-t','commands','ninja']).stdout.splitlines()
    compile_commands=[shlex.split(c) for c in commands if ' -c ' in c];assert len(compile_commands)>20
    other_commands=[c for c in commands if ' -c ' not in c];generated=[c for c in other_commands if 'inline.sh' in c];final_commands=[c for c in other_commands if c not in generated]
    build=project/'build';build.mkdir(exist_ok=True)
    for command in generated:checked(command,shell=True)
    ninja_file=project/'build.ninja';body=ninja_file.read_text();ninja_file.write_text(body.replace('cxx = '+str(args.clang),'cxx = '+str(args.ccache)+' '+str(args.clang)))
    start=time.perf_counter();initial=checked([str(args.ninja),'-j1','-d','keepdepfile','ninja']);initial_seconds=time.perf_counter()-start
    seed_cache=args.output/'seed-cache';shutil.copytree(args.output/'ccache',seed_cache)
    outputs=[project/c[c.index('-o')+1] for c in compile_commands];baseline_objects={str(p):sha(p.read_bytes()) for p in outputs};baseline_binary=sha((project/'ninja').read_bytes())
    dependency_map={}
    for command,output in zip(compile_commands,outputs):
        path=project/command[command.index('-MF')+1];text=path.read_text().replace('\\\n',' ');assert '\\' not in text
        dependency_map[str(output)]={str((project/p).resolve()) for p in text.split(':',1)[1].split()}
    fixed_paths={Path(p) for deps in dependency_map.values() for p in deps if not Path(p).is_relative_to(project)}
    fixed_paths.update(p.resolve() for p in (args.host,args.clang,args.ninja,args.ccache))
    for executable in (args.host,args.clang,args.ninja,args.ccache):
        linkage=checked(['ldd',str(executable)]).stdout
        for line in linkage.splitlines():
            for value in line.split():
                if value.startswith('/') and Path(value).is_file():fixed_paths.add(Path(value).resolve())
    fixed={str(p):sha_file(p) for p in sorted(fixed_paths)}
    host=Host(args.host,args.output);source_files={str(p):p.read_text() for p in (project/'src').rglob('*') if p.is_file() and p.suffix in ('.cc','.h','.hpp','.inc','.c','.py','.sh')}
    # Actual baseline project dependencies are authoritative, not a suffix guess.
    for deps in dependency_map.values():
        for name in deps:
            path=Path(name)
            if path.is_relative_to(project):source_files[name]=path.read_text()
    source_files[str(build/'browse_py.h')]=(build/'browse_py.h').read_text()
    start=time.perf_counter();admission=host.request(dict(edits=source_files,source_root=str(project),expected_generation=0));assert admission['ok'];admission_seconds=time.perf_counter()-start;generation=admission['generation']
    hashes={p.name:sha(p.read_bytes()) for p in (Path(__file__),Path(__file__).with_name('run_ir.py'),Path(__file__).with_name('ir_host.cpp'))};frozen=args.output/'frozen';frozen.mkdir()
    for name in hashes:shutil.copyfile(Path(__file__).with_name(name),frozen/name)
    data=dict(status='running',project='Ninja 1.13.2',cache_policy='baseline-only ccache seed restored outside every operation; no changed-result history hits',source_archive_sha256=sha(args.archive.read_bytes()),implementation_sha256=hashes,host_sha256=sha(args.host.read_bytes()),fixed_sdk_tool_files=fixed,environment_sha256=sha(json.dumps(env,sort_keys=True).encode()),compile_units=len(compile_commands),commands=compile_commands,dependency_entries=sum(map(len,dependency_map.values())),initial_ninja_ccache_seconds=initial_seconds,configure_seconds=config_seconds,admission=admission,admission_seconds=admission_seconds,source_files=len(source_files),source_bytes=sum(len(s.encode()) for s in source_files.values()),cases=[],editor=[],scope='One compiler worker versus Ninja+ccache -j1; source namespace authoritative in memory, SDK remains physical; explicit generated-header adapter, target list from upstream Ninja graph. In-memory mtimes0; date/time builtins rejected by -Werror=date-time. Baseline positive SDK closure and tool linkage hashed before/after; no hostile/racing writer or arbitrary new SDK lookup claim.')
    try:
      start=time.perf_counter();native=[]
      for command,output in zip(compile_commands,outputs):
        row=host.call(command,project,output,mode='native',logical=True,generation=generation);assert row['ok'],row;assert sha(output.read_bytes())==baseline_objects[str(output)],str(output);native.append(row)
      for command in final_commands:checked(command,shell=True)
      assert sha((project/'ninja').read_bytes())==baseline_binary;data['initial_shared_seconds']=time.perf_counter()-start;data['initial_shared']=native
      # Later mutations remain labelled probes appended to unchanged upstream code.
      source=project/'src/version.cc';header=project/'src/version.h';browse=project/'src/browse.py'
      original={str(p):p.read_text() for p in (source,header,browse)};original_generated=(build/'browse_py.h').read_text()
      scenarios={'noop':{},'source':{str(source):original[str(source)]+'\nextern "C" int gaia_probe(void){return 17;}\n'},'header':{str(header):original[str(header)]+'\nstatic __attribute__((used)) int gaia_header_probe(void){return 23;}\n'},'generated':{str(browse):original[str(browse)]+'\n# Gaia generated-input probe\n'},'configuration':{}}
      rng=random.Random(1917)
      for block in range(args.trials):
        for scenario,edits in scenarios.items():
          # Restore logical/physical baseline outside the operation clock.
          for p,b in original.items():Path(p).write_text(b)
          (build/'browse_py.h').write_text(original_generated);ninja_file.write_text(body.replace('cxx = '+str(args.clang),'cxx = '+str(args.ccache)+' '+str(args.clang)))
          checked([str(args.ninja),'-j1','ninja']);reset=host.request(dict(edits={**original,str(build/'browse_py.h'):original_generated},source_root=str(project),expected_generation=generation));assert reset['ok'];generation=reset['generation']
          modes=['shared','ninja-ccache'];rng.shuffle(modes);references=None
          for mode in modes:
            for p,b in original.items():Path(p).write_text(b)
            (build/'browse_py.h').write_text(original_generated);ninja_file.write_text(body.replace('cxx = '+str(args.clang),'cxx = '+str(args.ccache)+' '+str(args.clang)));checked([str(args.ninja),'-j1','ninja'])
            shutil.rmtree(args.output/'ccache');shutil.copytree(seed_cache,args.output/'ccache')
            start=time.perf_counter();actual_edits=dict(edits)
            for p,b in edits.items():Path(p).write_text(b)
            config=scenario=='configuration'
            if config:ninja_file.write_text(ninja_file.read_text().replace('-DNDEBUG','-UNDEBUG'))
            if mode=='ninja-ccache':result=checked([str(args.ninja),'-j1','ninja']);rows=[]
            else:
              if scenario=='generated':
                for command in generated:checked(command,shell=True)
                actual_edits[str(build/'browse_py.h')]=(build/'browse_py.h').read_text()
              update=host.request(dict(edits=actual_edits,source_root=str(project),expected_generation=generation));assert update['ok'];generation=update['generation'];rows=[]
              dirty=set(actual_edits)
              for command,output in zip(compile_commands,outputs):
                if config or dependency_map[str(output)]&dirty:
                  current=list(command)
                  if config:current=['-UNDEBUG' if arg=='-DNDEBUG' else arg for arg in current]
                  row=host.call(current,project,output,mode='native',logical=True,generation=generation);assert row['ok'],row;rows.append(row)
              if rows:
                for command in final_commands:checked(command,shell=True)
            elapsed=time.perf_counter()-start
            identities={str(p.relative_to(project)):sha(p.read_bytes()) for p in outputs};identities['ninja']=sha((project/'ninja').read_bytes())
            if references is None:references=identities
            else:assert references==identities,(scenario,mode)
            runtime=checked([str(project/'ninja'),'--version']).stdout.strip();assert runtime.startswith('1.13.2')
            data['cases'].append(dict(block=block,scenario=scenario,mode=mode,seconds=elapsed,compilations=len(rows) if mode=='shared' else None,objects=identities,host_rows=rows,correct=True,runtime=runtime));save(args.output/'results.json',data);print(block,scenario,mode,round(elapsed*1000,2),flush=True)
      # Admitted edits and editor lookup refer to the same generation; no physical edit.
      virtual=original[str(source)]+'\nextern "C" int gaia_editor_probe(void){return 31;}\n';edit=host.request(dict(edits={str(source):virtual},source_root=str(project),expected_generation=generation));assert edit['ok'];generation=edit['generation'];inspection=host.request(dict(inspect=str(source)));assert inspection['sha256']==sha(virtual.encode())
      i=next(i for i,c in enumerate(compile_commands) if 'src/version.cc' in c);row=host.call(compile_commands[i],project,outputs[i],mode='native',logical=True,generation=generation);assert row['ok'];virtual_object=outputs[i].read_bytes();source.write_text(virtual);checked(compile_commands[i]);assert virtual_object==outputs[i].read_bytes()
      stale=host.call(compile_commands[i],project,outputs[i],mode='native',logical=True,generation=generation-1);assert not stale['ok']
      conflict=host.request(dict(edits={str(source):virtual},source_root=str(project),expected_generation=generation-1));assert not conflict['ok']
      data['editor'].append(dict(edit=edit,inspection=inspection,compile=row,stale_compile=stale,conflicting_edit=conflict,correct=True))
      assert hashes=={name:sha(Path(__file__).with_name(name).read_bytes()) for name in hashes};assert data['host_sha256']==sha(args.host.read_bytes());assert fixed=={name:sha_file(name) for name in fixed};data['frozen_inputs_verified_after']=True;data['status']='complete';save(args.output/'results.json',data);save(args.output/'validation.json',dict(passed=True,initial_objects=len(outputs),paired_operations=len(data['cases']),editor_cases=len(data['editor']),raw_sha256=sha((args.output/'results.json').read_bytes())))
    finally:host.close()

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('host','archive','clang','ninja','ccache','output','measurement-lock'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--trials',type=int,default=3);a=p.parse_args()
 with a.measurement_lock.open('a') as lock:fcntl.flock(lock,fcntl.LOCK_EX);run(a)

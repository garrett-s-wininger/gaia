"""Configure pinned, unmodified upstream CMake projects; builds stay ignored."""
import argparse, hashlib, json, os, subprocess
from pathlib import Path

REPO=Path(__file__).resolve().parents[3]
WORK=REPO/'experiments/_work/generalization'
TOOLS=REPO/'experiments/compiler/_work/comparison-tools/usr'
PROJECTS={
 'xxhash':('xxHash-0.8.3','cmake_unofficial',['-DBUILD_SHARED_LIBS=OFF'],'xxhsum'),
 'spdlog':('spdlog-1.16.0','',['-DSPDLOG_BUILD_EXAMPLE=ON','-DSPDLOG_BUILD_TESTS=OFF'],'example'),
 're2c':('re2c-4.2','',['-DRE2C_REBUILD_SYNTAX=ON'],'re2c'),
 'curl':('curl-8.16.0','',['-DBUILD_SHARED_LIBS=OFF','-DBUILD_TESTING=OFF','-DBUILD_EXAMPLES=OFF'],'curl'),
}

def run(command,cwd,log):
 with log.open('w') as f:
  p=subprocess.run([str(x) for x in command],cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
 if p.returncode:raise RuntimeError(f'{command[0]} failed: {log}')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('projects',nargs='*',default=list(PROJECTS));a=p.parse_args()
 cmake=WORK/'sources/cmake-4.1.2-linux-x86_64/bin/cmake';ninja=TOOLS/'bin/ninja'
 for name in a.projects:
  folder,sub,options,target=PROJECTS[name];source=WORK/'sources'/folder;build=WORK/'build'/name;build.mkdir(parents=True,exist_ok=True)
  command=[cmake,'-S',source/sub,'-B',build,'-G','Ninja',f'-DCMAKE_MAKE_PROGRAM={ninja}','-DCMAKE_C_COMPILER=/usr/lib/llvm22/bin/clang','-DCMAKE_CXX_COMPILER=/usr/lib/llvm22/bin/clang++','-DCMAKE_BUILD_TYPE=Release','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',*options]
  run(command,WORK,build/'configure.log')
  run([ninja,'-j2',target],build,build/'build.log')
  commands=json.loads((build/'compile_commands.json').read_text())
  (build/'setup.json').write_text(json.dumps(dict(project=name,target=target,configure=list(map(str,command)),compile_entries=len(commands),source=str(source),build=str(build)),indent=2)+'\n')
  print(name,len(commands),flush=True)

if __name__=='__main__':main()

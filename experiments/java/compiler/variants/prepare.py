#!/usr/bin/env python3
"""Create independent immutable fixture and compile the unchanged shared harness."""
import argparse,hashlib,json,shutil,subprocess,time,zipfile
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
def main():
 a=argparse.ArgumentParser();a.add_argument('--jdk',type=Path,required=True);a.add_argument('--target-sdk',type=Path);a.add_argument('--fixture',type=Path);a.add_argument('--sources',type=Path);a.add_argument('--output',type=Path,required=True);args=a.parse_args();w=args.output.resolve();w.mkdir(parents=True,exist_ok=True);p={}
 if args.fixture:old=json.loads(args.fixture.read_text())
 elif args.sources:
  pin=hashlib.sha256(args.sources.read_bytes()).hexdigest()
  if pin!='87916611c616588b20d987868f96e622de6ed447e4b1ff5b662ebd947773e9a6':raise ValueError('Picocli source archive differs')
  old=dict(source_files=['picocli/AutoComplete.java','picocli/CommandLine.java','picocli/package-info.java'],target_versions=['4.7.7','4.7.7-gaia-probe'])
  with zipfile.ZipFile(args.sources) as z:
   for key in ('source','second_source'):
    for rel in old['source_files']:
     text=z.read(rel).decode()
     if key=='second_source' and rel.endswith('/CommandLine.java'):
      needle='String VERSION = \"4.7.7\"';assert text.count(needle)==1;text=text.replace(needle,'String VERSION = \"4.7.7-gaia-probe\"')
     dst=w/key/rel;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_text(text)
  old.update(source=str(w/'source'),second_source=str(w/'second_source'))
 else:a.error('--sources or --fixture required')
 for key in ('source','second_source'):
  dst=w/key
  if not dst.exists():shutil.copytree(old[key],dst)
  p[key]=str(dst)
 p.update(target_sdk=str((args.target_sdk or args.jdk).resolve()),jdk=str(args.jdk.resolve()),image=str(args.jdk.resolve()),app=str(w/'compiler-harness.jar'),outputs=str(w/'outputs'),compilation_classpath=str(w/'empty-classpath'),source_files=old['source_files'],target_versions=old['target_versions'],work=str(w))
 classes=w/'harness-classes';classes.mkdir(exist_ok=True);begin=time.perf_counter()
 subprocess.run([args.jdk/'bin/javac','-J-XX:-UsePerfData','-proc:none','-source','25','-target','25','-d',classes,BASE/'CompilerHarness.java',Path(__file__).parent/'NativeCompiler.java'],check=True)
 subprocess.run([args.jdk/'bin/jar','-J-XX:-UsePerfData','--create','--file',p['app'],'-C',classes,'.'],check=True)
 (w/'broken').mkdir(exist_ok=True);(w/'broken/Broken.java').write_text('class Broken { this is invalid; }\n')
 p['source_sha256']={str(q.relative_to(Path(p['source']))):hashlib.sha256(q.read_bytes()).hexdigest() for q in Path(p['source']).rglob('*.java')};p['second_source_sha256']={str(q.relative_to(Path(p['second_source']))):hashlib.sha256(q.read_bytes()).hexdigest() for q in Path(p['second_source']).rglob('*.java')};p['jdk_modules_sha256']=hashlib.sha256((args.jdk/'lib/modules').read_bytes()).hexdigest()
 p['target_sdk_modules_sha256']=hashlib.sha256((Path(p['target_sdk'])/'lib/modules').read_bytes()).hexdigest()
 p['native_endpoint_source_sha256']=hashlib.sha256((Path(__file__).parent/'NativeCompiler.java').read_bytes()).hexdigest();p['app_sha256']=hashlib.sha256(Path(p['app']).read_bytes()).hexdigest()
 frozen=w/'build-sources';frozen.mkdir(exist_ok=True)
 for q in (BASE/'CompilerHarness.java',Path(__file__).parent/'NativeCompiler.java'):shutil.copyfile(q,frozen/q.name)
 p['setup_seconds']=time.perf_counter()-begin;p['toolchain_version']=subprocess.run([args.jdk/'bin/java','-version'],text=True,capture_output=True).stderr;p['harness_sha256']=hashlib.sha256((BASE/'CompilerHarness.java').read_bytes()).hexdigest()
 (w/'prepared.json').write_text(json.dumps(p,indent=2)+'\n');print(w/'prepared.json')
if __name__=='__main__':main()

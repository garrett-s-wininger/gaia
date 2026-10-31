#!/usr/bin/env python3
"""Real Picocli bytecode compilation: jlink, fresh/resident API and private pools."""
import argparse,hashlib,json,os,platform,random,select,shutil,statistics,subprocess,time,zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent
VM=['-Xms32m','-Xmx768m','-XX:ActiveProcessorCount=4']
PICO='f86e30fffd10d2b13b8caa8d4b237a7ee61f2ffccf5b1941de718b765d235bf8'
SOURCE='87916611c616588b20d987868f96e622de6ed447e4b1ff5b662ebd947773e9a6'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
def checked(cmd,**kwargs):
 b=time.perf_counter();p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True,**kwargs);e=time.perf_counter()
 if p.returncode:raise RuntimeError(str(cmd)+'\n'+p.stdout+'\n'+p.stderr)
 return p,e-b

def hashes(folder):
 result={}
 for p in sorted(folder.rglob('*.class')):result[p.relative_to(folder).as_posix()[:-6].replace('/','.')]=p.read_bytes()
 overall=hashlib.sha256()
 for name,body in sorted(result.items()):overall.update(name.encode()+b'\0'+hashlib.sha256(body).digest())
 return dict(classes=len(result),bytes=sum(map(len,result.values())),sha256=overall.hexdigest())

def prepare_targets(data):
 work=Path(data['work']);empty=work/'empty-classpath';empty.mkdir(exist_ok=True);second=work/'source-version-edit'
 if not second.exists():
  shutil.copytree(data['source'],second)
  p=second/'picocli/CommandLine.java';text=p.read_bytes();needle=b'public static final String VERSION = "4.7.7";'
  if text.count(needle)!=1:raise ValueError('version-edit fixture anchor changed')
  p.write_bytes(text.replace(needle,b'public static final String VERSION = "4.7.7-gaia-probe";'))
 data['compilation_classpath']=str(empty);data['second_source']=str(second);data['target_versions']=['4.7.7','4.7.7-gaia-probe']
 data['second_source_sha256']={name:sha(second/name) for name in data['source_files']}
 return data

def prepare(args,work):
 work.mkdir(parents=True);jdk=args.jdk.resolve();jar=args.picocli_jar.resolve();sourcejar=args.sources.resolve()
 if sha(jar)!=PICO or sha(sourcejar)!=SOURCE:raise ValueError('pinned Picocli artifact mismatch')
 source=work/'source';source.mkdir();pins={}
 with zipfile.ZipFile(sourcejar) as z:
  for info in z.infolist():
   if not info.filename.endswith('.java'):continue
   p=Path(info.filename)
   if p.is_absolute() or '..' in p.parts:raise ValueError('unsafe source path')
   target=source/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(info));pins[p.as_posix()]=sha(target)
 (source/'empty-sourcepath').mkdir();(work/'broken').mkdir();(work/'broken/Broken.java').write_text('class Broken { void broken( }\n')
 classes=work/'harness-classes';classes.mkdir();_,host_seconds=checked([jdk/'bin/javac','-proc:none','-d',classes,HERE/'CompilerHarness.java']);app=work/'compiler-harness.jar';checked([jdk/'bin/jar','--create','--file',app,'-C',classes,'.'])
 image=work/'image';p,image_seconds=checked([jdk/'bin/jlink','--module-path',jdk/'jmods','--add-modules','java.compiler,jdk.compiler,jdk.zipfs','--strip-debug','--no-header-files','--no-man-pages','--compress=zip-6','--output',image])
 # jlink does not promise a prebuilt default CDS image. Supply the known JDK
 # list and build a compatible image before comparing startup.
 if not (image/'lib/classlist').exists():shutil.copy2(jdk/'lib/classlist',image/'lib/classlist')
 p,cds_seconds=checked([image/'bin/java',*VM,'-Xshare:dump']);(work/'image-cds.log').write_text(p.stdout+p.stderr)
 modules=checked([image/'bin/java','--list-modules'])[0].stdout.splitlines()
 data=dict(jdk=str(jdk),image=str(image),jar=str(jar),source=str(source),app=str(app),outputs=str(work/'outputs'),source_sha256=pins,
  input_pins=dict(picocli_jar_sha256=sha(jar),sources_sha256=sha(sourcejar),jdk_java_sha256=sha(jdk/'bin/java'),jdk_modules_sha256=sha(jdk/'lib/modules'),harness_jar_sha256=sha(app)),
  harness_source_sha256=sha(HERE/'CompilerHarness.java'),setup=dict(harness_compile_seconds=host_seconds,jlink_seconds=image_seconds,image_bytes=sum(p.stat().st_size for p in image.rglob('*') if p.is_file()),default_cds_seconds=cds_seconds,default_cds_bytes=(image/'lib/server/classes.jsa').stat().st_size,image_modules=modules),
  java=checked([jdk/'bin/java','-version'])[0].stderr,source_files=list(pins),work=str(work))
 prepare_targets(data);write(work/'prepared.json',data);return data

class Session:
 def __init__(self,prepared,*,full=False,pool=False,memory=False,aot=False):
  self.data=prepared;java=Path(prepared['jdk'] if full else prepared['image'])/'bin/java';cmd=[str(java),*VM]
  if aot:cmd+=['-XX:AOTMode=on','-XX:AOTCache='+prepared['aot_cache']]
  cmd+=['-cp',prepared['app'],'CompilerHarness','pool' if pool else 'batch','2' if pool else '1',prepared['source'],prepared['compilation_classpath'],prepared['jdk'],prepared['outputs'],'false' if memory else 'true',prepared['second_source']]
  self.cmd=cmd;begin=time.perf_counter();self.p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);line=self.line();self.start_seconds=time.perf_counter()-begin
  if not line.startswith('READY '):raise RuntimeError('bad ready: '+line)
  self.ready=json.loads(line[6:])
 def line(self):
  if not select.select([self.p.stdout],[],[],90)[0]:self.p.kill();raise RuntimeError('compiler reply timeout')
  line=self.p.stdout.readline()
  if not line:raise RuntimeError('compiler terminated: '+self.p.stderr.read())
  return line
 def call(self,token):
  begin=time.perf_counter();self.p.stdin.write(token+'\n');self.p.stdin.flush();line=self.line();end=time.perf_counter();result=json.loads(line);result['seconds']=end-begin;return result
 def close(self):
  begin=time.perf_counter();self.p.stdin.write('stop\n');self.p.stdin.flush();out,err=self.p.communicate(timeout=90);elapsed=time.perf_counter()-begin
  if self.p.returncode or out:raise RuntimeError('compiler shutdown: '+out+err)
  return dict(seconds=elapsed,stderr=err)

def cli(prepared,token,full,target=0,output=None,hash_output=True):
 jdk=Path(prepared['jdk']);runtime=jdk if full else Path(prepared['image']);output=Path(output) if output else Path(prepared['outputs'])/token;output.mkdir(parents=True)
 source=Path(prepared['source'] if target==0 else prepared['second_source'])
 flags=['-encoding','UTF-8','-g:none','-proc:none','-implicit:none','-source','25','-target','25','--system',prepared['jdk'],'-classpath',prepared['compilation_classpath'],'-sourcepath',str(Path(prepared['source'])/'empty-sourcepath'),'-d',str(output)]
 files=sorted(prepared['source_files'],key=lambda name:-Path(source/name).stat().st_size)
 cmd=[str(runtime/'bin/javac'),*['-J'+v for v in VM],*flags,*[str(source/name) for name in files]]
 begin=time.perf_counter();p=subprocess.run(cmd,capture_output=True,text=True);result=hashes(output) if hash_output else {};end=time.perf_counter()
 if p.returncode:raise RuntimeError(p.stdout+p.stderr)
 return dict(ok=True,token=token,targets=1,units=len(prepared['source_files']),seconds=end-begin,diagnostics=p.stderr,**result)

def cli_pair(prepared,token):
 output=Path(prepared['outputs'])/token;begin=time.perf_counter()
 with ThreadPoolExecutor(max_workers=2) as pool:
  futures=[pool.submit(cli,prepared,token,True,index,output/('target'+str(index)),False) for index in range(2)]
  diagnostics=[future.result()['diagnostics'] for future in futures]
 result=hashes(output);end=time.perf_counter()
 return dict(ok=True,token=token,targets=2,units=2*len(prepared['source_files']),seconds=end-begin,diagnostics=diagnostics,**result)

def train(prepared):
 cache=Path(prepared['work'])/('compiler-'+prepared['input_pins']['harness_jar_sha256'][:12]+'.aot');java=Path(prepared['image'])/'bin/java'
 cmd=[java,*VM,'-XX:AOTCacheOutput='+str(cache),'-cp',prepared['app'],'CompilerHarness','batch','1',prepared['source'],prepared['compilation_classpath'],prepared['jdk'],prepared['outputs'],'true',prepared['second_source']]
 p,seconds=checked(cmd,input='training\nstop\n');result=next(json.loads(line) for line in p.stdout.splitlines() if line.startswith('{'))
 if not result['ok']:raise ValueError('training compile failed')
 prepared['aot_cache']=str(cache);prepared['setup']['aot']=dict(seconds=seconds,bytes=cache.stat().st_size,sha256=sha(cache),training_compile=result,stderr=p.stderr)
 write(Path(prepared['work'])/'prepared.json',prepared)

def run(args):
 if args.prepared:
  prepared=json.loads(args.prepared.read_text())
  if args.rebuild_harness:
   prepare_targets(prepared)
   classes=Path(prepared['work'])/'harness-classes';_,seconds=checked([Path(prepared['jdk'])/'bin/javac','-proc:none','-d',classes,HERE/'CompilerHarness.java']);checked([Path(prepared['jdk'])/'bin/jar','--create','--file',prepared['app'],'-C',classes,'.']);prepared['harness_source_sha256']=sha(HERE/'CompilerHarness.java');prepared['input_pins']['harness_jar_sha256']=sha(prepared['app']);prepared['setup']['harness_rebuild_seconds']=seconds;prepared.pop('aot_cache',None);prepared['setup'].pop('aot',None);write(args.prepared,prepared)
 else:
  runid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');prepared=prepare(args,HERE/'_work'/runid)
 if prepared.get('harness_source_sha256')!=sha(HERE/'CompilerHarness.java'):raise ValueError('prepared harness source differs; rebuild preparation')
 for root,pins in ((prepared['source'],prepared['source_sha256']),(prepared['second_source'],prepared['second_source_sha256'])):
  for name,pin in pins.items():
   if sha(Path(root)/name)!=pin:raise ValueError('source changed since admission')
 if sha(prepared['jar'])!=PICO or sha(prepared['app'])!=prepared['input_pins']['harness_jar_sha256']:raise ValueError('prepared artifact changed')
 if args.train and 'aot_cache' not in prepared:train(prepared)
 if args.prepare_only:print(Path(prepared['work'])/'prepared.json');return
 args.output.mkdir(parents=True,exist_ok=True);runid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
 engines=['full-cli','image-cli','full-api-cold','image-api-cold','image-api-resident','image-api-memory-resident','full-cli-pair','image-api-sequential-pair-resident','image-pool2-pair-resident']
 if 'aot_cache' in prepared:engines.insert(4,'image-api-aot-cold')
 data=dict(run_id=runid,trials=args.trials,status='running',scope='Actual Picocli compilation, -proc:none, pinned immutable sources/target SDK. Fresh CLI/API include normal shutdown. Resident requests retain private compiler/filemanager contexts; class bytes/hashes must match CLI exactly.',environment=dict(platform=platform.platform(),cpu_count=os.cpu_count()),prepared=prepared,cases=[],residents={},source_sha256={p.name:sha(p) for p in (HERE/'CompilerHarness.java',HERE/'benchmark.py')},pair_trials=args.pair_trials)
 frozen=Path(prepared['work'])/('measurement-sources-'+runid);frozen.mkdir()
 for name in data['source_sha256']:shutil.copyfile(HERE/name,frozen/name)
 data['source_snapshots']=str(frozen);reference=cli(prepared,'reference-'+runid,True);expected={k:reference[k] for k in ('classes','bytes','sha256')};pair_reference=cli_pair(prepared,'reference-pair-'+runid);pair_expected={k:pair_reference[k] for k in ('classes','bytes','sha256')};data['expected_outputs']={'single':expected,'pair':pair_expected};samples={e:[] for e in engines};sessions={};rng=random.Random(7961)
 def validate(result):
  target=pair_expected if result.get('targets')==2 else expected
  if not result.get('ok') or any(result[k]!=value for k,value in target.items()):raise ValueError('compiler output differs: '+str(result))
 try:
  for engine in engines:
   if not engine.endswith('-resident'):continue
   session=Session(prepared,pool='pool2' in engine,memory='memory' in engine);sessions[engine]=session;first=session.call(('pair-first-' if 'pair' in engine else 'first-')+engine);validate(first);data['residents'][engine]=dict(start_seconds=session.start_seconds,ready=session.ready,first_request=first)
  for block in range(-1,max(args.trials,args.pair_trials)):
   order=list(engines);rng.shuffle(order)
   for engine in order:
    if block>= (args.pair_trials if 'pair' in engine else args.trials):continue
    token=('pair-' if 'pair' in engine else '')+f'b{block+1}-{engine}'
    if engine=='full-cli-pair':result=cli_pair(prepared,token)
    elif engine.endswith('-cli'):result=cli(prepared,token,engine.startswith('full'))
    elif engine.endswith('-resident'):result=sessions[engine].call(token)
    else:
     begin=time.perf_counter();session=Session(prepared,full=engine.startswith('full'),aot='aot' in engine);result=session.call(token);shutdown=session.close();result.update(seconds=time.perf_counter()-begin,worker_start_seconds=session.start_seconds,normal_shutdown=shutdown)
    validate(result)
    if block>=0:result.update(block=block,validated=True);samples[engine].append(result)
    print(block,engine,f"{result['seconds']*1000:.2f}ms",flush=True)
  for engine,session in sessions.items():
   value=session.call('check')
   if not value.get('ok') or value.get('versions')!=(prepared['target_versions'] if 'pair' in engine else prepared['target_versions'][:1]):raise ValueError('in-memory consumer failed')
   data['residents'][engine]['in_memory_consumer']=value
  data['status']='complete'
 finally:
  for engine,session in sessions.items():data['residents'][engine]['normal_shutdown']=session.close()
  data['cases']=[dict(engine=e,samples=ss) for e,ss in samples.items()];write(args.output/'results.json',data)
 summary=dict(run_id=runid,raw_sha256=sha(args.output/'results.json'),trials=args.trials,reference=expected,cases=[],residents=data['residents'],setup=prepared['setup'])
 for engine,ss in samples.items():
  times=[s['seconds']*1000 for s in ss];base=samples['full-cli-pair' if 'pair' in engine else 'full-cli'];row=dict(engine=engine,targets=2 if 'pair' in engine else 1,median_ms=statistics.median(times),min_ms=min(times),max_ms=max(times),paired_wins_vs_full_cli=sum(a['seconds']<b['seconds'] for a,b in zip(ss,base)),blocks=len(ss))
  for key in ('compile_ns','materialize_ns','hash_ns','rss_bytes','heap_used_bytes'):
   if key in ss[0]:row[key+'_median']=statistics.median(s[key] for s in ss)
  summary['cases'].append(row)
 write(args.output/'summary.json',summary);write(args.output/'validation.json',dict(passed=True,timed_operations=sum(len(ss) for ss in samples.values()),all_compiled_class_counts_bytes_and_hashes_match_reference=True,all_resident_in_memory_consumers_pass=True,raw_sha256=summary['raw_sha256']))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--jdk',type=Path);p.add_argument('--picocli-jar',type=Path);p.add_argument('--sources',type=Path);p.add_argument('--prepared',type=Path);p.add_argument('--prepare-only',action='store_true');p.add_argument('--rebuild-harness',action='store_true');p.add_argument('--train',action='store_true');p.add_argument('--trials',type=int,default=5);p.add_argument('--pair-trials',type=int,default=3);p.add_argument('--output',type=Path,default=HERE/'_work/results');a=p.parse_args()
 if a.trials<1 or (not a.prepared and not all((a.jdk,a.picocli_jar,a.sources))):p.error('positive trials and either --prepared or three input paths required')
 run(a)

"""Actual native PGO preparation and fixed-budget endpoint comparison."""
import argparse,hashlib,json,os,pathlib,random,resource,statistics,subprocess,time
HERE=pathlib.Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2)+'\n')
def timed(cmd,stdin=None,env=None):
    begin=time.perf_counter_ns();p=subprocess.run(list(map(str,cmd)),input=stdin,capture_output=True,text=True,env=env);elapsed=time.perf_counter_ns()-begin
    return dict(command=list(map(str,cmd)),returncode=p.returncode,stdout=p.stdout,stderr=p.stderr,wall_ns=elapsed)
def run(a):
    a.work.mkdir(parents=True,exist_ok=True);a.output.mkdir(parents=True,exist_ok=True)
    p=json.loads(a.prepared.read_text());build=json.loads(a.baseline.with_name('build.json').read_text());config=a.baseline.parent/'reachability'
    env=dict(os.environ)
    for key in ('JDK_JAVA_OPTIONS','JAVA_TOOL_OPTIONS','_JAVA_OPTIONS'):env.pop(key,None)
    result=dict(schema='GAIA-NATIVE-COMPILER-PGO-1',prepared_sha256=sha(a.prepared),baseline_sha256=sha(a.baseline),builds=[],measurements=[])
    def compile_image(name,flags):
        binary=a.work/name;cmd=[a.native_image,'-J-Xmx4g','-J-XX:-UsePerfData','--parallelism=4','--no-fallback','-O2','--gc=serial','--add-modules=jdk.compiler,jdk.zipfs','-H:ConfigurationFileDirectories='+str(config),*flags,'-cp',p['app'],'NativeCompiler',binary]
        row=timed(cmd,env=env);result['builds'].append(row);save(a.output/'results.json',result)
        if row['returncode']:raise RuntimeError(row['stderr']+row['stdout'])
        row['binary_bytes']=binary.stat().st_size;row['binary_sha256']=sha(binary)
        return binary
    try:
        instrumented=compile_image('instrumented',['--pgo-instrument'])
        output=a.work/'training-outputs';(output/'broken').mkdir(parents=True,exist_ok=True);(output/'broken/Broken.java').write_text('class Broken { invalid }')
        profile=a.work/'compiler.iprof'
        cmd=[instrumented,'-Xms32m','-Xmx768m','-XX:ProfilesDumpFile='+str(profile),'-Djava.home='+p['jdk'],p['source'],p['second_source'],p['jdk'],output,a.modules]
        training=timed(cmd,'first\nwarm\nedit\nwarm\nfail\nwarm\nstop\n',env=env);result['training']=training
        if training['returncode'] or not profile.is_file():raise RuntimeError(training['stderr']+' profile absent')
        result['profile']=dict(bytes=profile.stat().st_size,sha256=sha(profile))
        optimized=compile_image('pgo',['--pgo='+str(profile)])
        refs=json.loads(a.references.read_text())['graal25']
        for block in range(a.trials):
            variants=[('o2',a.baseline),('pgo',optimized)];random.Random(block+982).shuffle(variants)
            for name,binary in variants:
                output=a.work/f'run-{block}-{name}';(output/'broken').mkdir(parents=True,exist_ok=True);(output/'broken/Broken.java').write_text('class Broken { invalid }')
                cmd=[binary,'-Xms32m','-Xmx768m','-Djava.home='+p['jdk'],p['source'],p['second_source'],p['jdk'],output,a.modules]
                row=timed(cmd,'first\n'+('warm\n'*16)+'edit\nfail\nwarm\nstop\n',env=env)
                if row['returncode']:raise RuntimeError(row['stderr'])
                values=[json.loads(line) for line in row['stdout'].splitlines() if line.startswith('{')]
                for value in values:
                    if value['ok']:assert any(value['sha256']==ref['sha256'] for ref in refs.values())
                assert sum(not v['ok'] for v in values)==1
                row.update(block=block,variant=name,responses=values);result['measurements'].append(row);save(a.output/'results.json',result)
        result['status']='complete'
    except Exception as error:result['status']='blocked';result['error']=str(error)
    save(a.output/'results.json',result);raw=a.output/'results.json'
    summary=dict(status=result['status'],raw_sha256=sha(raw),raw_bytes=raw.stat().st_size,build_seconds=[r['wall_ns']/1e9 for r in result['builds']],profile=result.get('profile'),error=result.get('error'),cases=[])
    for name in ['o2','pgo']:
        rows=[r for r in result['measurements'] if r['variant']==name]
        if rows:summary['cases'].append(dict(variant=name,process_median_ms=statistics.median(r['wall_ns']/1e6 for r in rows),first_compile_median_ms=statistics.median(r['responses'][0]['compile_ns']/1e6 for r in rows),late_compile_median_ms=statistics.median(v['compile_ns']/1e6 for r in rows for v in r['responses'][9:17])))
    save(a.output/'summary.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native-image',type=pathlib.Path,required=True);p.add_argument('--prepared',type=pathlib.Path,required=True);p.add_argument('--baseline',type=pathlib.Path,required=True);p.add_argument('--references',type=pathlib.Path,required=True);p.add_argument('--modules',type=pathlib.Path,required=True);p.add_argument('--work',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--trials',type=int,default=3);run(p.parse_args())

"""Separate no-user-profile O3 control for Native Image's PGO level promotion."""
import argparse,json,pathlib,random,statistics
from pgo import sha,save,timed

def run(a):
    a.work.mkdir(parents=True,exist_ok=True);a.output.mkdir(parents=True,exist_ok=True);p=json.loads(a.prepared.read_text());refs=json.loads(a.references.read_text())['graal25'];native=a.work/'o3';config=a.o2.parent/'reachability'
    command=[a.native_image,'-J-Xmx4g','-J-XX:-UsePerfData','--parallelism=4','--no-fallback','-O3','--gc=serial','--add-modules=jdk.compiler,jdk.zipfs','-H:ConfigurationFileDirectories='+str(config),'-cp',p['app'],'NativeCompiler',native]
    build=timed(command);result=dict(schema='GAIA-NATIVE-O3-CONTROL-1',build=build,measurements=[],prior_pgo_result_sha256=sha(a.prior_results),prepared_sha256=sha(a.prepared))
    save(a.output/'results.json',result)
    if build['returncode']:raise RuntimeError(build['stderr']+build['stdout'])
    build.update(binary_bytes=native.stat().st_size,binary_sha256=sha(native))
    for block in range(a.trials):
        cases=[('o2',a.o2),('o3-no-user-profile',native),('o3-user-profile',a.pgo)];random.Random(762+block).shuffle(cases)
        for name,binary in cases:
            folder=a.work/f'run-{block}-{name}';(folder/'broken').mkdir(parents=True,exist_ok=True);(folder/'broken/Broken.java').write_text('class Broken { invalid }')
            cmd=[binary,'-Xms32m','-Xmx768m','-Djava.home='+p['jdk'],p['source'],p['second_source'],p['jdk'],folder,a.modules]
            row=timed(cmd,'first\n'+'warm\n'*16+'edit\nfail\nwarm\nstop\n')
            if row['returncode']:raise RuntimeError(row['stderr'])
            values=[json.loads(line) for line in row['stdout'].splitlines() if line.startswith('{')]
            assert len(values)==20 and sum(not v['ok'] for v in values)==1
            for value in values:
                if value['ok']:assert any(value['sha256']==ref['sha256'] for ref in refs.values())
            assert values[-1]['ok']
            row.update(variant=name,block=block,responses=values);result['measurements'].append(row);save(a.output/'results.json',result)
    result['status']='complete';save(a.output/'results.json',result);raw=a.output/'results.json';summary=[]
    for name in ['o2','o3-no-user-profile','o3-user-profile']:
        rows=[r for r in result['measurements'] if r['variant']==name];summary.append(dict(variant=name,median_process_ms=statistics.median(r['wall_ns']/1e6 for r in rows),first_compile_median_ms=statistics.median(r['responses'][0]['compile_ns']/1e6 for r in rows),late_compile_median_ms=statistics.median(v['compile_ns']/1e6 for r in rows for v in r['responses'][9:17])))
    save(a.output/'summary.json',dict(raw_sha256=sha(raw),raw_bytes=raw.stat().st_size,build_seconds=build['wall_ns']/1e9,cases=summary));print(json.dumps(summary,indent=2))
if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--native-image',type=pathlib.Path,required=True);q.add_argument('--prepared',type=pathlib.Path,required=True);q.add_argument('--o2',type=pathlib.Path,required=True);q.add_argument('--pgo',type=pathlib.Path,required=True);q.add_argument('--prior-results',type=pathlib.Path,required=True);q.add_argument('--references',type=pathlib.Path,required=True);q.add_argument('--modules',type=pathlib.Path,required=True);q.add_argument('--work',type=pathlib.Path,required=True);q.add_argument('--output',type=pathlib.Path,required=True);q.add_argument('--trials',type=int,default=3);run(q.parse_args())

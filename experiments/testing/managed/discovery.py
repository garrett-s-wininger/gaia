"""Real JUnit discovery: three consumer views and one actual execution."""
import argparse, hashlib, json, os, pathlib, random, statistics, subprocess, time
HERE=pathlib.Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def checked(cmd):
    p=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    return p

def class_identity(root):return {p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*.class'))}
def require_current(root,pins):
    if class_identity(root)!=pins:raise ValueError('test input generation changed; rediscovery required')

def run(a):
    a.output.mkdir(parents=True,exist_ok=True);work=a.work;work.mkdir(parents=True,exist_ok=True);sources=work/'sources';sources.mkdir(exist_ok=True);classes=work/'classes';classes.mkdir(exist_ok=True)
    for c in range(a.classes):
        methods='\n'.join(f'@org.junit.jupiter.api.Test void test{i}() {{org.junit.jupiter.api.Assertions.assertEquals({i+c}, {i}+{c});}}' for i in range(10))
        dynamic='@org.junit.jupiter.api.TestFactory java.util.stream.Stream<org.junit.jupiter.api.DynamicTest> generated(){int epoch=Integer.parseInt(System.getProperty("fixture.epoch"));return java.util.stream.IntStream.range(0,epoch).mapToObj(i->org.junit.jupiter.api.DynamicTest.dynamicTest("current-"+epoch+"-"+i,()->org.junit.jupiter.api.Assertions.assertTrue(i<epoch)));}'
        (sources/f'Fixture{c}Test.java').write_text(f'package gaiafixtures; public class Fixture{c}Test{{{methods}\n{dynamic}}}')
    start=time.perf_counter_ns();checked([a.jdk/'bin/javac','--release','25','-cp',a.junit,'-d',classes,HERE/'DiscoveryHarness.java',*sorted(sources.glob('*.java'))]);prep=time.perf_counter_ns()-start
    pins=class_identity(classes);probe=classes/'gaiafixtures/Fixture0Test.class';old=probe.read_bytes();probe.write_bytes(old+b'x')
    try:
        try:require_current(classes,pins)
        except ValueError:pass
        else:raise AssertionError('stale plan input accepted')
    finally:probe.write_bytes(old)
    probe.unlink()
    try:
        try:require_current(classes,pins)
        except ValueError:pass
        else:raise AssertionError('removed test class accepted')
    finally:probe.write_bytes(old)
    rows=[];rng=random.Random(222)
    for block in range(-1,a.trials):
        modes=['independent','independent-parallel','shared','direct'];rng.shuffle(modes)
        for mode in modes:
            epoch=1+max(0,block)%3;require_current(classes,pins);start=time.perf_counter_ns();p=checked([a.jdk/'bin/java','-XX:-UsePerfData','-Xshare:on','-cp',str(a.junit)+os.pathsep+str(classes),'DiscoveryHarness',mode,a.classes,epoch]);elapsed=time.perf_counter_ns()-start;value=json.loads(p.stdout)
            if block>=0:rows.append(dict(block=block,wall_ns=elapsed,result=value))
    require_current(classes,pins)
    raw=dict(schema='GAIA-SHARED-TEST-PLAN-1',scope='Generated JUnit fixture using real Jupiter engine; no application startup; same JVM request plan baseline; dynamic tests materialize during execution, not discovery.',preparation_ns=prep,junit_sha256=sha(a.junit),java_sha256=sha(a.jdk/'bin/java'),fixture_class_sha256=pins,rows=rows,guards=dict(changed_classfile_rejected=True,removed_classfile_rejected=True,dynamic_count_changes_per_epoch=True))
    path=a.output/'results.json';path.write_text(json.dumps(raw,indent=2)+'\n');summary=[]
    for mode in ['independent','independent-parallel','shared','direct']:
        samples=[r for r in rows if r['result']['mode']==mode];summary.append(dict(mode=mode,process_median_ms=statistics.median(r['wall_ns']/1e6 for r in samples),operation_median_ms=statistics.median(r['result']['whole_ns']/1e6 for r in samples),discovery_median_ms=statistics.median(r['result']['discovery_ns']/1e6 for r in samples),execution_median_ms=statistics.median(r['result']['execution_ns']/1e6 for r in samples)))
    (a.output/'summary.json').write_text(json.dumps(dict(cases=summary,raw_sha256=sha(path),raw_bytes=path.stat().st_size),indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--jdk',type=pathlib.Path,required=True);p.add_argument('--junit',type=pathlib.Path,required=True);p.add_argument('--work',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--classes',type=int,default=40);p.add_argument('--trials',type=int,default=5);run(p.parse_args())

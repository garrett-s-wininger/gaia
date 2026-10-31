"""Publish small raw identities and an explicit implementation/provenance inventory."""
import hashlib,json,pathlib,subprocess,statistics
ROOT=pathlib.Path(__file__).resolve().parents[3]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    artifacts=[]
    o3raw=ROOT/'experiments/java/followthrough/results/o3-control/results.json'
    if o3raw.exists():
        run=json.loads(o3raw.read_text());cases=[]
        for name in ['o2','o3-no-user-profile','o3-user-profile']:
            rows=[r for r in run['measurements'] if r['variant']==name]
            if not rows:continue
            values=[r['wall_ns']/1e6 for r in rows]
            cases.append(dict(variant=name,median_process_ms=statistics.median(values),min_process_ms=min(values),max_process_ms=max(values),first_compile_median_ms=statistics.median(r['responses'][0]['compile_ns']/1e6 for r in rows),late_compile_median_ms=statistics.median(v['compile_ns']/1e6 for r in rows for v in r['responses'][9:17]),late_compile_thread_cpu_median_ms=statistics.median(v['compile_thread_cpu_ns']/1e6 for r in rows for v in r['responses'][9:17])))
        pairs=[]
        for block in sorted({r['block'] for r in run['measurements']}):
            rows={r['variant']:r for r in run['measurements'] if r['block']==block}
            if len(rows)==3:pairs.append(dict(block=block,user_profile_wins_vs_o2=rows['o3-user-profile']['wall_ns']<rows['o2']['wall_ns'],user_profile_wins_vs_o3=rows['o3-user-profile']['wall_ns']<rows['o3-no-user-profile']['wall_ns'],ratio_user_profile_to_o3=rows['o3-user-profile']['wall_ns']/rows['o3-no-user-profile']['wall_ns']))
        o3raw.with_name('summary.json').write_text(json.dumps(dict(raw_sha256=sha(o3raw),raw_bytes=o3raw.stat().st_size,build_seconds=run['build']['wall_ns']/1e9,cases=cases,paired_blocks=pairs),indent=2)+'\n')
    roots=[ROOT/'experiments/java/followthrough',ROOT/'experiments/testing/managed']
    implementation={p.relative_to(ROOT).as_posix():sha(p) for folder in roots for p in sorted(folder.glob('*')) if p.suffix in ('.py','.java')}
    for folder in roots:
        for raw in sorted((folder/'results').glob('*/results.json')):
            entry=dict(path=raw.relative_to(ROOT).as_posix(),bytes=raw.stat().st_size,sha256=sha(raw));artifacts.append(entry)
            data=json.loads(raw.read_text())
            validation=dict(raw_identity=entry,scope='Successful operations guarded by harness assertions; failed diagnostic exit is separately retained in primary queue summary.',schema=data.get('schema'))
            if 'cases' in data and data.get('schema')=='GAIA-JVM-RESIDENT-BUDGET-1':
                validation['completed_target_compilations']=sum(8*len(c['batches']) for c in data['cases'])
                validation['actual_class_consumers']=sum(c.get('consumer',{}).get('targets',0) for c in data['cases'])
            elif 'measurements' in data:
                validation['successful_compilations']=sum(v['ok'] for r in data['measurements'] for v in r['responses'])
                validation['expected_invalid_requests']=sum(not v['ok'] for r in data['measurements'] for v in r['responses'])
            elif data.get('schema')=='GAIA-SHARED-TEST-PLAN-1':validation['successful_test_executions']=sum(r['result']['executed'] for r in data['rows'])
            elif data.get('schema')=='GAIA-TEST-FIXTURE-1':validation['isolated_database_operations']=sum(len(r['operations']) for r in data['rows'])
            elif 'validation' in data:validation['semantic_controls']=data['validation']
            raw.with_name('validation.json').write_text(json.dumps(validation,indent=2)+'\n')
            provenance=dict(raw_identity=entry,base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),published_implementation_sha256=implementation,note='Published implementation includes corrected NMT exit-stdout handling and additional admission guards. Initial primary JVM trace preceded that diagnostic fix; its saved timings/outputs remain intact. This inventory is not a frozen per-process source snapshot.')
            raw.with_name('provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    db=json.loads((ROOT/'experiments/testing/managed/results/database/summary.json').read_text())['cases']
    junit=json.loads((ROOT/'experiments/testing/managed/results/discovery/summary.json').read_text())['cases']
    text='''# Sharing preparation in test workflows

The first passes establish reusable boundaries with real SQLite and JUnit APIs, using generated fixtures. They do not establish production-suite speedups or a new test-runner architecture.

## Prepared SQLite fixtures remove repeated schema work

The fixture has twelve tables, twelve thousand seed rows and twelve indexes, serialized into 495,616 bytes. Three blocks each run sixteen independent test operations with one or four workers. Every operation changes private rows, adds a current-request value, asserts it and rolls back; injected SQL failures must also leave the fixture intact.

| Mode | Workers | Complete charged session median |
| --- | ---: | ---: |
'''
    for row in db:text+=f"| {row['mode']} | {row['workers']} | {row['median_charged_session_ms']:.1f} ms |\n"
    text+='''
Prepared modes include necessary seed construction and teardown; deserialize additionally charges serialized-image construction. Required private connection closes and executor shutdown are included. Full logical-dump correctness oracles are separate from performance clocks. Replay does not pay for a template constructed only as the harness's independent oracle.

The gain comes from amortizing construction over sixteen tests. Copying a prepared database is not copy-on-write, and the fixture is only about half a megabyte. The four-worker replay result also includes this SQLite/Python workload's contention; it does not imply that parallel test execution is generally slower. No PostgreSQL server or physical storage/durability behavior is measured.

Rollback requires a narrower contract than cloning: a test cannot commit the fixture transaction or depend on external effects. A negative control proves committed changes escape rollback. Isolated backup/deserialize copies allow independent database transactions but still do not restore filesystem or network side effects. Three database tests cover success/error recovery, parallel private state and commit escape.

## JUnit already supports sharing a discovered plan

Forty generated test classes contain four hundred ordinary tests plus dynamic factories. A request discovers between forty and one hundred twenty additional dynamic tests during actual execution. Three consumers enumerate stable discovered IDs and verify deterministic shard coverage; then the plan executes real tests.

| Arrangement | Complete fresh-process median |
| --- | ---: |
'''
    for row in junit:text+=f"| {row['mode']} | {row['process_median_ms']:.0f} ms |\n"
    text+='''
Five blocks execute 9,440 measured tests successfully, with changing dynamic counts. One shared plan improves on three redundant discovery operations, including the concurrent control. The existing direct JUnit API remains the faster lower-work control; it does not supply the three pre-execution consumer views. We have demonstrated useful existing API composition, not a novel discovery algorithm or a win over a competent single runner.

Dynamic leaves appear during execution and cannot be fully pre-sharded from discovery alone. Changed, added and removed class files invalidate the external input-generation guard. That check runs outside process clocks and is not a complete persistent-plan invalidation protocol for arbitrary classpath resources, engines or extensions. The prototype uses one process per request and shares objects within it, not across JVMs or machines.

Read the [reproduction guide](../../experiments/testing/managed/README.md) and [run index](experiments.json). The database and discovery summaries record exact raw hashes, preparation boundaries and successful-operation evidence.
'''
    (ROOT/'research/testing/findings.md').write_text(text)
    destination=ROOT/'experiments/java/followthrough/evidence-additions.json';destination.write_text(json.dumps(dict(artifacts=artifacts),indent=2)+'\n');print(destination)
if __name__=='__main__':main()

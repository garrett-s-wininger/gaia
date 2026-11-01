"""Replay historical diagnosis/regression/fix cycles with native test controls."""
import argparse
from datetime import datetime,timezone
import fcntl
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import sys
import tarfile
import time

from evidence import EvidenceStore,digest,generation,source_snapshot

HERE=Path(__file__).resolve().parent
MODES=('full_suite','native_testmon','shared_evidence')


def write(path,data):
    path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')


def git(repo,*args):
    return subprocess.check_output(['git',*args],cwd=repo)


def checkout(repo,revision,destination):
    destination.mkdir(parents=True)
    data=git(repo,'archive',revision)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(destination,filter='data')
    return hashlib.sha256(data).hexdigest()


def changed_files(repo,task,prefix):
    return git(repo,'diff','--name-only',task['commit']+'^1',task['commit'],'--',prefix).decode().splitlines()


def apply_files(repo,root,task,prefix,original=False):
    revision=task['commit']+'^1' if original else task['commit']
    for name in changed_files(repo,task,prefix):
        path=root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(git(repo,'show',revision+':'+name))
    if prefix=='tests' and task.get('additional_regression'):
        (root/'tests/test_gaia_issue_reproduction.py').write_text(task['additional_regression'])


def run_tests(root,state,mode,context,label,extra=None):
    result=state/(label+'.json');log=state/(label+'.log')
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
             PYTHONPATH=os.pathsep.join([str(HERE),str(root/'src'),str(root/'tests')]),
             GAIA_CONTEXT=context,GAIA_RESULT=str(result),GAIA_EXPORT='1' if mode=='shared_evidence' else '0',
             COVERAGE_CORE='ctrace',
             TESTMON_DATAFILE=str(state/'testmon.sqlite3'))
    cmd=[sys.executable,'-m','pytest','-q','-o','cache_dir='+str(state/'pytest-cache'),'-p','observer','--rootdir',str(root)]
    if mode in ('native_testmon','shared_evidence'):
        cmd+=['-p','testmon.pytest_testmon','--testmon']
    if extra:cmd+=extra
    start=time.perf_counter_ns()
    with log.open('w') as stream:
        proc=subprocess.run(cmd,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=90)
    ns=time.perf_counter_ns()-start
    if not result.exists():raise RuntimeError(log.read_text())
    data=json.loads(result.read_text())
    assert proc.returncode in (0,1,5),log.read_text()
    assert data['unchanged_during_run'],label
    data['wall_ns']=ns
    return data


def outcome_summary(run):
    return {'exit':run['exit'],'generation':run['generation'],'wall_ns':run['wall_ns'],
            'executed':len(run['outcomes']),'failed':sorted(n for n,v in run['outcomes'].items() if v=='failed'),
            'outcomes':run['outcomes'],'observed_tests':len(run['observed']),
            'function_test_pairs':sum(len(x) for x in run['observed'].values()),
            'process_peak_rss_kib':run['process_peak_rss_kib']}


def queries(store,task):
    start=time.perf_counter_ns()
    result={'search':store.search(task['query']),
            'inspect':[store.inspect(item['file'],item['symbol'],focus=task['query']) for item in task['inspect']]}
    result['wall_ns']=time.perf_counter_ns()-start
    return result


def check_stale(store,task,old_run):
    original=store.root/task['inspect'][0]['file'];content=original.read_bytes()
    old=store.inspect(task['inspect'][0]['file'],task['inspect'][0]['symbol'])
    original.write_bytes(b'# location shift for admission check\n'+content)
    try:
        shifted=store.inspect(task['inspect'][0]['file'],task['inspect'][0]['symbol'])
        assert shifted['line']==old['line']+1
        assert shifted['observations'] and all(o['status']=='historical' for o in shifted['observations'])
        try:store.publish(old_run)
        except ValueError:pass
        else:raise AssertionError('stale result published')
        try:store.inspect(task['inspect'][0]['file'],task['inspect'][0]['symbol'],old['generation'])
        except ValueError:pass
        else:raise AssertionError('stale query accepted')
        original.write_bytes(b'def incomplete(')
        assert store.inspect(task['inspect'][0]['file'],task['inspect'][0]['symbol'])['status']=='incomplete-source'
    finally:original.write_bytes(content)
    changed=EvidenceStore(store.root,store.context+'-changed')
    try:changed.publish(old_run)
    except ValueError:pass
    else:raise AssertionError('configuration mismatch published')
    return {'location_remapped':True,'old_links_historical':True,'late_result_rejected':True,
            'stale_query_rejected':True,'configuration_mismatch_rejected':True,'incomplete_source_withheld':True}


def trial(repo,work,mode,task,context,keep=False):
    start=time.perf_counter_ns();root=work/'project';state=work/'state'
    archive_sha=checkout(repo,task['commit']+'^1',root);state.mkdir()
    store=EvidenceStore(root,context)
    stages=[];diagnostic=None
    for label in ('initial','regression','fixed','unchanged','reverted','restored'):
        stage_start=time.perf_counter_ns()
        if label=='regression':apply_files(repo,root,task,'tests')
        if label in ('fixed','restored'):apply_files(repo,root,task,'src')
        if label=='reverted':apply_files(repo,root,task,'src',original=True)
        before=queries(store,task)
        run=run_tests(root,state,mode,context,label)
        failures={n for n,v in run['outcomes'].items() if v=='failed'}
        expected=set()
        if label in ('regression','reverted'):
            expected={task['upstream_regression']} if task['id']!='overlay-async' else {'tests/test_gaia_issue_reproduction.py::test_overlay_inherits_async_mode'}
        assert failures==expected,(task['id'],mode,label,failures,(state/(label+'.log')).read_text()[-4000:])
        if label!='unchanged':assert run['outcomes'],(label,run)
        if mode=='shared_evidence':store.publish(run)
        after=queries(store,task)
        if mode=='shared_evidence':
            assert all(i['observations'] for i in after['inspect'])
            assert all(any(o['status']=='current' for o in i['observations']) for i in after['inspect'])
        stage_ns=time.perf_counter_ns()-stage_start
        stages.append({'stage':label,'wall_ns':stage_ns,'tests':outcome_summary(run),'before':before,'after':after})
    if mode=='shared_evidence':
        save_start=time.perf_counter_ns();store.save(state/'evidence.json')
        stages[-1]['wall_ns']+=time.perf_counter_ns()-save_start
    size=sum(p.stat().st_size for p in state.rglob('*') if p.is_file())
    session_ns=time.perf_counter_ns()-start
    # Diagnostics deliberately outside the measured workflow.
    if mode=='shared_evidence':diagnostic=check_stale(store,task,run)
    if not keep:shutil.rmtree(work)
    return {'task':task['id'],'mode':mode,'session_ns':session_ns,'stages':stages,'state_bytes':size,
            'evidence_bytes':(state/'evidence.json').stat().st_size if keep and mode=='shared_evidence' else None,
            'archive_sha256':archive_sha,'boundary_checks':diagnostic,'retained_workspace':str(work) if keep else None}


def summarize(rows):
    out={}
    for task in sorted({r['task'] for r in rows}):
        group={mode:sorted([r for r in rows if r['task']==task and r['mode']==mode],key=lambda r:r['block']) for mode in MODES}
        groups={m:rs for m,rs in group.items() if rs}
        out[task]={'modes':{mode:{'session_s_median':statistics.median(r['session_ns']/1e9 for r in rs),
                                'session_s_range':[min(r['session_ns']/1e9 for r in rs),max(r['session_ns']/1e9 for r in rs)],
                                'initial_s_median':statistics.median(r['stages'][0]['wall_ns']/1e9 for r in rs),
                                'after_initial_s_median':statistics.median(sum(s['wall_ns'] for s in r['stages'][1:])/1e9 for r in rs),
                                'executed_by_stage':{s['stage']:s['tests']['executed'] for s in rs[0]['stages']},
                                'state_bytes_median':statistics.median(r['state_bytes'] for r in rs)} for mode,rs in groups.items()}}
        if 'shared_evidence' in groups and 'native_testmon' in groups:
            ratios=[100*(a['session_ns']/b['session_ns']-1) for a,b in zip(groups['shared_evidence'],groups['native_testmon'])]
            out[task]['shared_overhead_vs_native_percent']={'median':statistics.median(ratios),'by_block':ratios}
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--blocks',type=int,default=3)
    p.add_argument('--modes',nargs='+',choices=MODES,default=list(MODES));p.add_argument('--tasks',nargs='+')
    p.add_argument('--lock',type=Path);a=p.parse_args()
    a.repo=a.repo.resolve();a.work=a.work.resolve();a.output=a.output.resolve()
    a.work.mkdir(parents=True,exist_ok=False);a.output.mkdir(parents=True,exist_ok=False)
    specification=json.loads((HERE/'tasks.json').read_text())
    tasks=[t for t in specification['tasks'] if not a.tasks or t['id'] in a.tasks]
    packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}
    import testmon.testmon_core, testmon.process_code, coverage.control
    tool_paths=[Path(m.__file__) for m in (testmon.testmon_core,testmon.process_code,coverage.control)]
    tool_identity={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in tool_paths}
    context=digest({'packages':packages,'python':sys.version,'pytest_plugins':['observer','testmon.pytest_testmon'],
                    'tool_identity':tool_identity,'coverage_core':'ctrace',
                    'environment':'no external services; native Jinja fixtures; local async event loops'})
    inputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir() if p.suffix in ('.py','.json')}
    raw={'schema_version':1,'context':context,'blocks':a.blocks,'trials':[]}
    lock=a.lock.open('a+') if a.lock else None
    if lock:print('Waiting for cooperative timing lock',flush=True);fcntl.flock(lock,fcntl.LOCK_EX)
    try:
        for block in range(a.blocks):
            order=[(task,mode) for task in tasks for mode in a.modes];random.Random(81304+block).shuffle(order)
            for task,mode in order:
                print(f"block {block+1}/{a.blocks}: {task['id']} {mode}",flush=True)
                row=trial(a.repo,a.work/f"b{block}-{task['id']}-{mode}",mode,task,context,
                          keep=block==0 and mode=='shared_evidence')
                row['block']=block;raw['trials'].append(row);write(a.output/'results.json',raw)
    finally:
        if lock:fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
    assert inputs=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir() if p.suffix in ('.py','.json')}
    assert tool_identity=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in tool_paths}
    # Native and shared use identical selection and outcomes; full-suite checks the complete failure set.
    for task in tasks:
        for block in range(a.blocks):
            matches={r['mode']:r for r in raw['trials'] if r['task']==task['id'] and r['block']==block}
            if 'native_testmon' in matches and 'shared_evidence' in matches:
                for n,s in zip(matches['native_testmon']['stages'],matches['shared_evidence']['stages']):
                    assert n['tests']['outcomes']==s['tests']['outcomes'],(task['id'],n['stage'])
            if 'full_suite' in matches:
                full=matches['full_suite']
                for r in matches.values():
                    for f,s in zip(full['stages'],r['stages']):assert f['tests']['failed']==s['tests']['failed']
    write(a.output/'summary.json',summarize(raw['trials']))
    write(a.output/'validation.json',{'trials':len(raw['trials']),'validation_runs':len(raw['trials'])*6,
          'expected_failures_verified':True,'native_and_shared_selection_identical':all(m in a.modes for m in ('native_testmon','shared_evidence')),
          'full_suite_failure_sets_match': 'full_suite' in a.modes,
          'boundaries':[r['boundary_checks'] for r in raw['trials'] if r['boundary_checks']],
          'human_or_agent_task_completion_measured':False})
    write(a.output/'provenance.json',{'python':sys.version,'platform':platform.platform(),'packages':packages,'context':context,
          'harness_sha256':inputs,'tool_sha256':tool_identity,'tasks':tasks,'parent_commits':{t['id']:git(a.repo,'rev-parse',t['commit']+'^1').decode().strip() for t in tasks},
          'finished_utc':datetime.now(timezone.utc).isoformat(),'lock':str(a.lock),'random_seed_base':81304,
          'clock':'session includes checkout, initial collection, all edits, queries and subprocess waits, evidence persistence; excludes diagnostics and final workspace cleanup'})
    path=a.output/'results.json';write(a.output/'raw-identity.json',{'path':'results.json','bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    print(json.dumps(summarize(raw['trials']),indent=2))


if __name__=='__main__':main()

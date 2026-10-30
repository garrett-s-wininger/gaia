"""Untimed compile-error/link-publication check for the sorted queue."""
import json
from pathlib import Path
import subprocess
import benchmark as base
import project_benchmark as project

HERE=base.HERE

if __name__=='__main__':
    path=HERE/'_work/runs/cost-scheduling/results.json';d=json.loads(path.read_text())
    if d['status']!='complete':raise ValueError('finish timing before failure checks')
    c=next(c for c in d['cases'] if c['name']=='release-direct-cost')
    cmd=c['command'].copy();work=Path(d['work']);out=work/'compile-error-check';out.mkdir()
    cmd[6]=str(out);commands=[x.copy() for x in d['costs']['release']['commands']]
    longest=d['costs']['release']['longest'];missing=work/'missing-required-header.h'
    if missing.exists():raise ValueError('failure fixture unexpectedly exists')
    commands[longest].extend(['-include',str(missing)])
    plan=work/'compile-error.gcr';plan.write_bytes(project.encode_requests(commands));cmd[7]=str(plan)
    sentinel=b'previous published library';(out/'libzstd.so').write_bytes(sentinel)
    p=subprocess.run(cmd,cwd=out,capture_output=True,text=True,timeout=180);s=json.loads(p.stdout)
    if not p.returncode or s['correct'] or not s['errors'] or s['link_calls'] or (out/'libzstd.so').read_bytes()!=sentinel:
        raise ValueError('sorted compile failure reached linker/published output')
    if s['schedule']!=d['costs']['release']['order'] or s['jobs'][longest][0]<=0 or s['jobs'][longest][1]<=0:
        raise ValueError('failure did not exercise the sorted priority job')
    if base.sha(Path(cmd[0]))!=d['host_sha256']:raise ValueError('host changed')
    check=dict(check='sorted-compile-error-suppresses-link-preserves-output',passed=True,result=s,
        command=cmd,stderr=p.stderr,checker_sha256=base.sha(Path(__file__)))
    d['checks'].append(check);base.save(path,d)
    base.save(path.with_name('compile-error-check.json'),dict(run_id=d['run_id'],timed=False,**check))
    print('verified sorted queue compile-error publication gate')

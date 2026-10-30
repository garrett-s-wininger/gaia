#!/usr/bin/env python3
"""Solve the real Django corpus offline; validate against fresh pip reports."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import benchmark
import solver


def run(args):
    provenance=json.loads(args.provenance.read_text())
    wheelhouses={Path(a['path']).parent for a in provenance['artifacts']}
    if len(wheelhouses)!=1:raise ValueError('expected one pinned wheel directory')
    wheels=wheelhouses.pop()
    for artifact in provenance['artifacts']:
        if hashlib.sha256(Path(artifact['path']).read_bytes()).hexdigest()!=artifact['sha256']:
            raise ValueError('published artifact digest differs')
    if {p.name for p in wheels.glob('*.whl')}!={a['filename'] for a in provenance['artifacts']}:
        raise ValueError('unexpected/unpinned wheel candidates')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work=benchmark.HERE/'_work'/('django-'+run_id);work.mkdir(parents=True)
    args.output.mkdir(parents=True,exist_ok=True)
    admission=solver.admit(wheels,work/'snapshot');target=solver.target_default()
    seed=dict(run_id=run_id,target=target,datasets=[],cases=[])
    references={}
    for name,roots in [('django-core',['Django>=6.1,<6.2']),
                       ('django-rest',['Django>=6.1,<6.2','djangorestframework>=3.18,<3.19','django-filter>=26,<27'])]:
        report=args.output/(name+'-pip-reference.json')
        code='''import sys
sys.path.insert(0,sys.argv.pop(1))
def offline(event,args):
    if event in ('socket.connect','socket.getaddrinfo','socket.bind'):
        raise RuntimeError('network attempted')
sys.addaudithook(offline)
from pip._internal.cli.main import main
raise SystemExit(main())
'''
        # pip receives argv after the bundled-wheel location has been removed.
        command=[sys.executable,'-I','-S','-B','-c',code,str(solver.PIP_WHEEL),'--isolated',
                 '--disable-pip-version-check','--no-input','--no-cache-dir','install','--dry-run',
                 '--ignore-installed','--no-index','--find-links',str(wheels),'--report',str(report),*roots]
        child=subprocess.run(command,text=True,capture_output=True,timeout=120)
        if child.returncode:raise RuntimeError(child.stdout+child.stderr)
        pip=json.loads(report.read_text())
        expected=sorted([solver.canonicalize_name(r['metadata']['name']),r['metadata']['version']] for r in pip['install'])
        references[name]={solver.canonicalize_name(r['metadata']['name']):r['download_info']['archive_info']['hashes']['sha256']
                          for r in pip['install']}
        dataset=dict(name=name,wheelhouse=str(wheels),roots=roots,admission=admission,expected=expected,expected_status='solved')
        request=work/(name+'-request.json');benchmark.measurements.write_json(request,dict(**dataset,constraints=[],prereleases=False,max_rounds=10000))
        seed['datasets'].append(dataset);seed['cases'].append(dict(dataset=name,command=['--request',str(request)]))
        print('fresh offline pip verified',name,expected,flush=True)
    inputs=work/'inputs.json';benchmark.measurements.write_json(inputs,seed)
    command=[sys.executable,'-B',str(benchmark.HERE/'benchmark.py'),'--inputs',str(inputs),
             '--variants','wheel-uncached','wheel-cached','catalog-trail','--trials',str(args.trials),'--output',str(args.output)]
    subprocess.run(command,check=True)
    path=args.output/'results.json';result=json.loads(path.read_text())
    for case in result['cases']:
        for sample in case['samples']:
            for solve in sample['passes']:
                if {row[0]:row[2] for row in solve['selected']}!=references[case['dataset']]:
                    raise RuntimeError('artifact IDs differ from pip report')
    result['published_artifacts']=provenance
    result['pip_reference_artifact_ids']=references
    path.write_text(json.dumps(result,indent=2)+'\n')
    benchmark.measurements.write_json(args.output/'provenance.json',provenance)
    print('Every solve matches fresh pip artifact hashes; report:',args.output/'REPORT.md')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provenance',type=Path,default=benchmark.HERE.parent/'dependency_bundles/_work/django-corpus/provenance.json')
    parser.add_argument('--trials',type=int,default=15)
    parser.add_argument('--output',type=Path,default=benchmark.HERE/'_work/runs/django')
    args=parser.parse_args()
    if args.trials<1:parser.error('positive trials required')
    run(args)

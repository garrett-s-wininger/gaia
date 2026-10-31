"""Retain portable compact graph evidence; full exact-path observations stay ignored."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent


def publish(source,destination,policy):
    destination.mkdir(parents=True,exist_ok=True)
    data=json.loads((source/'results.json').read_text());summary=json.loads((source/'summary.json').read_text());shutil.copy2(source/'results.json',destination/'results.json');shutil.copy2(source/'validation.json',destination/'validation.json')
    for name in ('ccache-stats.txt',):
        if (source/name).exists():shutil.copy2(source/name,destination/name)
    shutil.copy2(HERE/'_work/correctness-tests.log',destination/'correctness-tests.txt')
    ccache=next(p for p in data['external_input_sha256'] if Path(p).name=='ccache');lld=next(p for p in data['external_input_sha256'] if Path(p).name=='ld.lld')
    rows=[]
    for row in summary['rows']:
        copied=dict(row)
        if row['engine']=='ninja-ccache':
            samples=[s for s in data['cases'] if s['scenario']==row['scenario'] and s['engine']=='ninja-ccache'];copied['native_compiler_executions']=None;copied['native_link_calls']=None
            copied['scheduled_ccache_commands']=[s['messages'].count(ccache) for s in samples];copied['scheduled_link_commands']=[s['messages'].count(lld) for s in samples]
        rows.append(copied)
    boundaries=[dict(engine=b['engine'],engine_setup_ms=b['engine_setup_seconds']*1000,clean_ms=b['clean']['seconds']*1000,native_compiler_executions=sum(t['compiler_executions'] for t in b['clean']['targets']) if b['clean']['targets'] else None,native_link_calls=sum(t['link_calls'] for t in b['clean']['targets']) if b['clean']['targets'] else None) for b in data['boundaries']]
    retained=dict(run_id=data['run_id'],cache_policy=policy,cache_lifetimes=data.get('cache_lifetimes',dict(object_cache='retained through repeated trace',input_session='resident sealed inputs retained',linked_history='disabled')),trials=data['trials'],rows=rows,paired=summary['paired'],boundaries=boundaries,admitted_files=data['admitted_files'],admitted_bytes=data['admitted_bytes'],external_input_pins=len(data['external_input_sha256']),graph=[dict(name=t['name'],translation_units=len(t['sources']),output=t['output'],deps=t['deps']) for t in data['graph']],versions=data['versions'],source_sha256=data['implementation_sha256'],common_source_sha256=data['common_sources_sha256'])
    (destination/'summary.json').write_text(json.dumps(retained,indent=2)+'\n')
    provenance=dict(project='fmt',version='12.2.0',source_url=data['source_url'],source_archive_sha256=data['source_sha256'],upstream_release='https://github.com/fmtlib/fmt/releases/tag/12.2.0',scope='Unmodified upstream compiled library with labelled four-TU integration fixture; six translation units total',tools=[dict(name=Path(path).name,sha256=pin) for path,pin in data['external_input_sha256'].items()],crt_alias_proof=data['crt_alias_proof'])
    (destination/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    raw=(destination/'results.json').read_bytes();print(json.dumps(dict(report=str(destination/'REPORT.md'),run_id=data['run_id'],raw=str(destination/'results.json'),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),source_snapshots_verified=verify_sources(data,policy)),indent=2))


def verify_sources(data,policy):
    frozen=Path(data['source_snapshots'])
    for relative,pin in data['implementation_sha256'].items():
        if hashlib.sha256((frozen/relative).read_bytes()).hexdigest()!=pin:raise ValueError('frozen source identity')
        if policy=='baseline-seeded' and hashlib.sha256((HERE/relative).read_bytes()).hexdigest()!=pin:raise ValueError('current source differs')
    for name,pin in data['common_sources_sha256'].items():
        if hashlib.sha256((frozen/name).read_bytes()).hexdigest()!=pin or hashlib.sha256((HERE.parent/name).read_bytes()).hexdigest()!=pin:raise ValueError('common source identity')
    return True


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path);parser.add_argument('--policy',required=True,choices=('baseline-seeded','repeated-trace'));a=parser.parse_args();publish(a.source,a.destination,a.policy)

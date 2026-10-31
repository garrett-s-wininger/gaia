"""Derive review summaries and an ignored raw-evidence bundle from local captures."""
import argparse,collections,json,shutil
from pathlib import Path
from profile import sha,checked
HERE=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser();p.add_argument('--profile',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--confirm',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=True)
 overhead=json.loads((a.profile/'results.json').read_text());candidate=json.loads((a.candidate/'results.json').read_text());summary=json.loads((a.candidate/'summary.json').read_text());validation=json.loads((a.candidate/'semantic-validation.json').read_text());confirm=json.loads((a.confirm/'results.json').read_text()) if a.confirm else None
 captures={p.name:json.loads(p.read_text()) for p in a.profile.glob('*.json') if p.name not in ['results.json','checkpoint.json','results-pre-parser-fix.json']};logs={p.name:p.read_text() for p in a.profile.glob('*.log')};initial={p.name:json.loads(p.read_text()) for p in (HERE/'_work/smoke').glob('*.json')}
 raw=dict(overhead=overhead,candidate=candidate,confirmation=confirm);(out/'results.json').write_text(json.dumps(raw,indent=2));(out/'profiles.json').write_text(json.dumps(dict(final=captures,logs=logs,initial_diagnostic=initial),indent=2))
 attribution=[]
 for workload in ['registry','basic']:
  for mode,field in [('cpu','cpu_stacks'),('alloc','allocation_stacks')]:
   weights=collections.Counter();counts=collections.Counter();runs=[v for k,v in captures.items() if k[0].isdigit() and k.endswith('-'+mode+'-'+workload+'.json')]
   for run in runs:
    for row in run[field]:
     frames=row['stack'].splitlines()[1:] if mode=='alloc' else row['stack'].splitlines();key=next((f for f in frames if f.startswith(('Lgroovy/','Lorg/codehaus/groovy/','Lorg/apache/groovy/','Lpicocli/'))),'other');weights[key]+=row['weight'];counts[key]+=row['samples']
   attribution.append(dict(workload=workload,mode=mode,runs=len(runs),unit='observed thread CPU delta ns attributed to endpoint stack' if mode=='cpu' else 'sum sampled object sizes in bytes, not total allocation',closest_framework_frame=[dict(frame=k,weight=v,samples=counts[k]) for k,v in weights.most_common(20)]))
 for value in summary['preparation']['variants'].values():value.pop('jar',None)
 result=dict(schema='GAIA-JVMTI-REVIEW-1',overhead=overhead['summary'],sharing=overhead['sharing'],attribution=attribution,candidate=summary,confirmation=confirm and {k:v for k,v in confirm.items() if k!='rows'},uncertainty='Initial candidate matrix has extreme outliers and strong between-block drift; preserve all blocks and do not claim broad startup win.',errors={k:v['errors'] for k,v in captures.items() if v.get('errors')},capabilities={m:captures['0-'+m+'-registry.json']['capabilities'] for m in ['idle','classes','cpu','alloc']},raw_sha256=sha(out/'results.json'),profiles_sha256=sha(out/'profiles.json'))
 (out/'summary.json').write_text(json.dumps(result,indent=2));(out/'validation.json').write_text(json.dumps(validation,indent=2));provenance=dict(platform=overhead['platform'],jdk=overhead['jdk'],inputs={Path(k).name:v for k,v in overhead['inputs'].items()},native_compiler=checked(['c++','--version']).stdout,measured_agent_binary_sha256=sha(a.profile/'libgaia_jvmti.so'),measured_agent_source_sha256=sha(a.profile/'sources/agent.cpp'),measured_profiler_source_sha256=sha(a.profile/'sources/profile.py'),class_init_parser_correction=overhead.get('postprocessing'),initial_diagnostic_agent_binary_sha256=sha(HERE/'_work/libgaia_jvmti.so'),sources={p.name:sha(p) for p in HERE.iterdir() if p.suffix in ['.py','.cpp','.java']},raw_evidence='Ignored local captures; no downloadable evidence archive published.')
 (out/'provenance.json').write_text(json.dumps(provenance,indent=2));print('Published',out)
if __name__=='__main__':main()

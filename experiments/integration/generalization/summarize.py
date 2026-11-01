"""Export portable per-project tables from successful replay rows."""
import argparse,collections,hashlib,json,statistics
from pathlib import Path

def stats(values):return dict(median=statistics.median(values),minimum=min(values),maximum=max(values),observations=len(values))
def main(a):
 raw=json.loads((a.input/'results.json').read_text());groups=collections.defaultdict(list);traces=collections.defaultdict(lambda:collections.defaultdict(float));setups={};counts=collections.Counter()
 for r in raw['rows']:
  groups[(r['project'],r['case'],r['mode'])].append(r);traces[(r['project'],r['mode'])][r['trial']]+=r['seconds'];setups[(r['project'],r['mode'],r['trial'])]=r['setup_seconds']
  for c in r['rows']:
   counts[(r['project'],r['mode'],'compiled_responses')]+=1
   for field in ['projection_supported','projection_safe','backend_pending','queue_fallback']:
    counts[(r['project'],r['mode'],field)]+=bool(c.get(field))
   counts[(r['project'],r['mode'],'diagnostic_responses')]+=c.get('diagnostic_messages',0)>0
   counts[(r['project'],r['mode'],'ir_hit_responses')]+=bool(c.get('hit'))
   counts[(r['project'],r['mode'],'validation_hit_responses')]+=bool(c.get('validation_hit'))
   if c.get('projection_reason'):counts[(r['project'],r['mode'],'projection_reason:'+c['projection_reason'])]+=1
 summary=dict(schema_version=1,units='seconds',primary_rows=len(raw['rows']),operations=[],traces=[],projects=[],scope='Controlled invalidation probes on selected upstream target closures; descriptive three-trial ranges, not a natural edit distribution or cross-project speedup.')
 for (project,case,mode),rows in groups.items():
  record=dict(project=project,case=case,mode=mode,whole_operation=stats([r['seconds'] for r in rows]),facts_component=stats([r['facts_seconds'] for r in rows]),dirty_targets=stats([len(r['dirty']) for r in rows]),restored_targets=stats([len(r['restored']) for r in rows]),projected_targets=stats([len(r['projected']) for r in rows]))
  if mode=='ninja-ccache':record['physical_build_only_reference']=stats([r['physical_build']['seconds'] for r in rows])
  summary['operations'].append(record)
 for (project,mode),trialvalues in traces.items():
  setup=[v for (p,m,t),v in setups.items() if (p,m)==(project,mode)]
  summary['traces'].append(dict(project=project,mode=mode,trace=stats(list(trialvalues.values())),setup=stats(setup),compiled_response_counts={key:v for (p,m,key),v in counts.items() if (p,m)==(project,mode)}))
 for p in sorted({r['project'] for r in raw['rows']}):
  g=json.loads((a.input/(p+'-graph.json')).read_text());g.pop('setup');summary['projects'].append(g)
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 labels={'no_op':'No change','single_source_comment':'Source comment','single_source_semantic':'Source declaration addition','observed_header_comment':'Shared-header comment','observed_header_semantic':'Shared-header declaration addition','unused_numeric_definition':'Unused numeric definition','widely_used_definition':'Enable assertions (remove NDEBUG)','compiler_option_change':'Optimization O3 → O1','return_to_seen_state':'Return to initial state','explicit_generated_input_change':'Upstream generator input change'}
 lines=['# Per-operation results','','Milliseconds; median [minimum–maximum]. Whole operations include admission and required archive/link work. These are controlled probes, not natural edit frequencies. Observation counts and component clocks are in [the summary](summary.json); control and fallback qualifications are in [the report](README.md).','', '| Project / operation | Shared serial | Shared queue | Ninja + ccache + independent index |','| --- | ---: | ---: | ---: |']
 for p in sorted({r['project'] for r in raw['rows']}):
  cases=list(dict.fromkeys(r['case'] for r in raw['rows'] if r['project']==p))
  for case in cases:
   cells=[]
   for mode in ['serial','queue','ninja-ccache']:
    v=stats([r['seconds']*1000 for r in groups[(p,case,mode)]]);cells.append(f"{v['median']:,.2f} [{v['minimum']:,.2f}–{v['maximum']:,.2f}]")
   lines.append('| '+p+' / '+labels[case]+' | '+' | '.join(cells)+' |')
 (a.output/'TABLES.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);main(p.parse_args())

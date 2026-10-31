"""Keep machine observations ignored; publish compact comparisons and provenance."""
import argparse,json,statistics
from pathlib import Path
from semantic_cache import sha

def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def summarize(raw,output):
 data=json.loads(raw.read_text());save(output/'results.json',data);cases=[]
 for source in data['preparation']:
  for scenario in data['scenarios'] if 'scenarios' in data else sorted({r['scenario'] for r in data['cases']}):
   baseline=[r for r in data['cases'] if r['source']==source and r['scenario']==scenario and r['mode']=='text']
   for mode in data['modes']:
    rows=[r for r in data['cases'] if r['source']==source and r['scenario']==scenario and r['mode']==mode]
    phases={}
    for name in ['ast','ir','full']:
     values=[r[name] for r in rows if r[name]]
     if values:
      phases[name]=dict(compiler_or_tool_ms=statistics.median(v['seconds']*1000 for v in values),normalization_ms=statistics.median(v.get('canonical_seconds',0)*1000 for v in values))
      for key in ['parse_ns','walk_ns','frontend_ns','ast_raw_bytes','ast_canonical_bytes','ir_bytes']:
       if key in values[0]:phases[name][key]=statistics.median(v[key] for v in values)
    cases.append(dict(source=source,scenario=scenario,mode=mode,blocks=len(rows),median_ms=statistics.median(r['seconds']*1000 for r in rows),min_ms=min(r['seconds']*1000 for r in rows),max_ms=max(r['seconds']*1000 for r in rows),paired_wins_vs_text=sum(r['seconds']<b['seconds'] for r,b in zip(rows,baseline)),hits=sum(r['hit'] for r in rows),correct=sum(r['correct'] for r in rows),phases=phases,ccache_counters={key:sum(r.get('ccache_counters',{}).get(key,0) for r in rows) for key in sorted({k for r in rows for k in r.get('ccache_counters',{})})}))
 prep={name:dict(source_bytes=v['source_bytes'],seed=v['seed'],context_before=v['context_before'],context_after=v['context_after'],context_policy=v['fixed_context']['policy'],context_sha256=sha(json.dumps(v['fixed_context'],sort_keys=True).encode()),baseline_object_sha256=v['baseline_object_sha256'],reference_sha256=v['reference_sha256'],baseline_preprocessor_sha256=v.get('baseline_preprocessor_sha256'),preprocessor_sha256=v.get('preprocessor_sha256'),reference_compile_seconds=sum(r['seconds'] for r in v['reference_stats'].values())) for name,v in data['preparation'].items()}
 for name,item in prep.items():
  if 'ccache' in data['preparation'][name]:item['ccache']=data['preparation'][name]['ccache']
  for stage in item['seed'].values():stage.pop('stderr',None)
 summary=dict(schema='GAIA-SEMANTIC-INVALIDATION-1',run_id=data['run_id'],status=data['status'],trials=data['trials'],cases=cases,preparation=prep,ast_helper_sha256=data.get('ast_helper_sha256'),direct_ast_helper_sha256=data.get('direct_ast_helper_sha256'),source_sha256=data['source_sha256'],source_archive_sha256=data['source_archive_sha256'],raw_sha256=sha((output/'results.json').read_bytes()),scope='Fixed compiler/tool/SDK/options/environment; private project, warm pages, same baseline candidate per operation, normal compiler/helper exit. Correctness oracle and context admission outside request timing.')
 save(output/'summary.json',summary);save(output/'validation.json',dict(passed=all(r['correct'] for r in data['cases'] if r['mode']!='ast'),objects_checked=len(data['cases']),unsafe_ast_mismatches=sum(not r['correct'] for r in data['cases'] if r['mode']=='ast'),fixed_context_unchanged=all(v['context_after']['passed'] for v in data['preparation'].values()),raw_sha256=summary['raw_sha256']))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();summarize(a.raw,a.output)

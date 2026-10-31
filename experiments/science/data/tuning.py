"""Equal-budget policy searches over a declared cache/service-cost trace model."""
import argparse,json,random,statistics,time
from pathlib import Path
from common import HERE,digest,measured,pins,publish
from locality import model

SPACE=[(width,budget) for width in (1,4,8,16) for budget in (32,64,128)]
def score(sequence,meta,config,profile):
    width,budget=config;value=model(sequence,meta,width,budget*65536)
    latency,bandwidth=profile
    return 1000*(value['reads']*latency+value['read_bytes']/bandwidth),value

def search(kind,sequence,meta,seed,evaluations=6):
    rng=random.Random(seed);seen=[];best=None;begin=time.perf_counter_ns()
    if kind=='grid':schedule=SPACE[::2][:evaluations]
    elif kind=='random':schedule=rng.sample(SPACE,evaluations)
    else:schedule=[rng.choice(SPACE)]
    for step in range(evaluations):
        if kind=='evolution' and step>0:
            parent=best[1];candidates=[c for c in SPACE if (c[0]==parent[0])!=(c[1]==parent[1])];schedule.append(rng.choice(candidates))
        config=schedule[step];value,counts=score(sequence,meta,config,(.003,16*1024*1024));seen.append({'config':config,'training_score_ms':value,'counts':counts})
        if best is None or value<best[0]:best=(value,config)
    return best[1],seen,time.perf_counter_ns()-begin

def run(args):
    sources=[Path(__file__),HERE/'locality.py',HERE/'common.py'];before=pins(sources);body=args.input.read_bytes();data=json.loads(body);rows=[]
    for block in range(args.trials):
        for strategy in ('fixed','grid','random','evolution'):
            with measured(args.lock):
                if strategy=='fixed':selected=(8,128);history=[];training_ns=0
                else:selected,history,training_ns=search(strategy,data['training'],data['chunks'],block+513,6)
                heldout={}
                for phase,profile in [('heldout',(.003,16*1024*1024)),('reverse_synthetic',(.0001,8*1024*1024))]:
                    value,counts=score(data[phase],data['chunks'],selected,profile);heldout[phase]={'score_ms':value,**counts}
            rows.append({'block':block,'strategy':strategy,'selected':selected,'evaluations':len(history),'training_wall_ns':training_ns,'training_modeled_ms':sum(r['training_score_ms'] for r in history),'history':history,'heldout':heldout})
    assert before==pins(sources)
    summary=[]
    for strategy in ('fixed','grid','random','evolution'):
        chosen=[r for r in rows if r['strategy']==strategy]
        summary.append({'strategy':strategy,'evaluations_per_search':chosen[0]['evaluations'],'median_search_wall_ms':statistics.median(r['training_wall_ns']/1e6 for r in chosen),'median_training_modeled_ms':statistics.median(r['training_modeled_ms'] for r in chosen),'median_normal_heldout_model_ms':statistics.median(r['heldout']['heldout']['score_ms'] for r in chosen),'median_reversal_heldout_model_ms':statistics.median(r['heldout']['reverse_synthetic']['score_ms'] for r in chosen)})
    result={'schema':'GAIA-SCIENCE-TUNING-1','scope':'Offline Python cache/service-cost model over actualrange-derivedchunktrace; reversal+profilechange explicitlysynthetic. Six equallycharged evaluations forgrid/random/evolution, fixeddefaultno training. Search CPU and modeledtrainingcost bothreported; no actualnetwork/evolutionaryspeedup claim. Sixneighbor mutations are a bounded policysearch surrogate, not biologicalsimulation.','input_sha256':digest(body),'sources':before,'space':SPACE,'rows':rows}
    print(publish(args.output,result,{'cases':summary},{'passed':True,'searches':len(rows),'bounded_evaluations':all(r['evaluations'] in (0,6) for r in rows),'heldout_not_used_for_selection':True},sources))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--trials',type=int,default=5);p.add_argument('--lock',type=Path);run(p.parse_args())

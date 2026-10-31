#!/usr/bin/env python3
"""Real RuboCop CLI: ordinary require, warmed Bootsnap and pinned ISeq pack."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import time

HERE=Path(__file__).resolve().parent
MODES=('normal','bootsnap','packed','packed-openssl')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,indent=2)+'\n')
def env_for(args):
    env=dict(os.environ);env.update(GEM_HOME=str(args.gems),GEM_PATH=str(args.gems),RUBOCOP_SERVER='false')
    for key in ('RUBYOPT','RUBOCOP_OPTS','RUBOCOP_CONFIG','RUBOCOP_CACHE_ROOT'):env.pop(key,None)
    return env

def run(args):
    args.output=args.output.resolve();args.gems=args.gems.resolve();args.output.mkdir(parents=True,exist_ok=True)
    work=args.output/'work';work.mkdir();pack=work/'code.pack';env=env_for(args)
    started=time.perf_counter();p=subprocess.run([args.ruby,str(HERE/'build_pack.rb'),str(pack)],env=env,capture_output=True,text=True,check=True)
    if p.stderr:raise RuntimeError(p.stderr)
    producer=dict(seconds=time.perf_counter()-started,**json.loads(Path(str(pack)+'.json').read_text()))
    exe=args.gems/'gems/rubocop-1.92.2/exe/rubocop';project=work/'project';project.mkdir()
    (project/'.rubocop.yml').write_text('AllCops:\n  NewCops: disable\n  TargetRubyVersion: 3.4\n  SuggestExtensions: false\n')
    def prepare(sequence):
        (project/'example.rb').write_text(f'''class Example
  def double(items, unused_{sequence})
    items.map {{|value| value*2}}.sum
  end
end
puts Example.new.double([1,2], 9)
''')
    def call(mode,token):
        marker=work/(token+'.exit');local=dict(env,GAIA_RUBY_MODE=mode,GAIA_RUBY_SHA256_PROVIDER=('openssl' if mode=='packed-openssl' else 'digest'),GAIA_RUBY_PACK=str(pack),GAIA_RUBY_PACK_SHA256=producer['sha256'],
          GAIA_BOOTSNAP_CACHE=str(work/'bootsnap-cache'),RUBOCOP_CACHE_ROOT=str(work/'lint-cache'),GAIA_REQUEST_TOKEN=token,GAIA_EXIT_MARKER=str(marker))
        cmd=[args.ruby,'-r',str(HERE/'bootstrap.rb'),str(exe),'--no-server','--cache','false','--format','json','--config','.rubocop.yml','example.rb']
        begin=time.perf_counter();p=subprocess.run(cmd,cwd=project,env=local,capture_output=True,text=True,timeout=30);elapsed=time.perf_counter()-begin
        if p.returncode not in (0,1) or p.stderr:raise RuntimeError(str((mode,p.returncode,p.stderr,p.stdout[:300])))
        result=json.loads(p.stdout);exit_info=json.loads(marker.read_text())
        if exit_info['status']!=p.returncode or exit_info['token']!=token or exit_info['cwd']!=str(project):raise ValueError('lifecycle identity differs')
        if result['summary']['inspected_file_count']!=1 or result['summary']['offense_count']==0:raise ValueError('lint operation missing')
        tool_features=[path for path in exit_info['features'] if '/rubocop-1.92.2/' in path]
        return dict(seconds=elapsed,status=p.returncode,result=result,tool_features=tool_features,exit=exit_info)
    prepare(0);cold=call('bootsnap','cold-bootsnap');expected=None;warmups=[]
    for mode in MODES:
        sample=call(mode,'warmup-'+mode)
        if expected is None:expected=(sample['result'],sample['tool_features'])
        elif (sample['result'],sample['tool_features'])!=expected:raise ValueError('warmup offenses differ')
        warmups.append(sample)
    samples={m:[] for m in MODES};rng=random.Random(511)
    data=dict(run_id=datetime.now(timezone.utc).isoformat(),ruby=subprocess.check_output([args.ruby,'--version'],text=True).strip(),
      ruby_sha256=sha(shutil.which(args.ruby)),gem_archives={p.name:sha(p) for p in sorted((args.gems/'cache').glob('*.gem'))},producer=producer,source_sha256={p.name:sha(p) for p in HERE.glob('*.rb')},
      trials=args.trials,cold_bootsnap=cold,warmups=warmups,cases=[])
    data['source_sha256']['benchmark.py']=sha(Path(__file__))
    frozen=work/'sources';frozen.mkdir()
    for name in data['source_sha256']:shutil.copyfile(HERE/name,frozen/name)
    data['source_snapshots']=str(frozen)
    for block in range(args.trials):
        prepare(block+1);expected=None;order=list(MODES);rng.shuffle(order)
        for mode in order:
            sample=call(mode,f'{block}-{mode}');sample['block']=block
            if expected is None:expected=(sample['result'],sample['tool_features'])
            elif (sample['result'],sample['tool_features'])!=expected:raise ValueError('changing-input offenses differ')
            samples[mode].append(sample);print(block,mode,round(sample['seconds']*1000,2),'ms',flush=True)
        data['cases']=[dict(mode=m,samples=ss) for m,ss in samples.items()];write(args.output/'results.json',data)
    native_crypto = [Path('/usr/lib/libcrypto.so.3')]
    native_crypto += [Path(path) for path in samples['packed-openssl'][-1]['exit']['features'] if path.endswith('/openssl.so')]
    data['native_crypto_sha256']={str(path):sha(path) for path in native_crypto if path.exists()}
    data['crypto']=samples['packed-openssl'][-1]['exit']['crypto']
    data['bootsnap_cache_bytes']= sum(p.stat().st_size for p in (work/'bootsnap-cache').rglob('*') if p.is_file());write(args.output/'results.json',data)
    summary={k:v for k,v in data.items() if k not in ('cases','warmups','cold_bootsnap','source_snapshots')};summary['cold_bootsnap_ms']=cold['seconds']*1000;summary['raw_sha256']=sha(args.output/'results.json');summary['cases']=[]
    for mode,ss in samples.items():
        summary['cases'].append(dict(mode=mode,median_ms=statistics.median(s['seconds'] for s in ss)*1000,
          rss_peak_median=statistics.median(s['exit']['rss_peak_bytes'] for s in ss),
          wins_vs_bootsnap=sum(a['seconds']<b['seconds'] for a,b in zip(ss,samples['bootsnap'])),blocks=len(ss),
          representative_pack=ss[0]['exit']['pack']))
    write(args.output/'summary.json',summary);write(args.output/'validation.json',dict(passed=True,operations=args.trials*len(MODES),
      all_offenses_tool_features_exit_statuses_and_request_identities_match=True,raw_sha256=summary['raw_sha256']))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ruby',default='ruby');p.add_argument('--trials',type=int,default=7)
    p.add_argument('--gems',type=Path,default=HERE/'_work/gems');p.add_argument('--output',type=Path,default=HERE/'_work/results')
    run(p.parse_args())

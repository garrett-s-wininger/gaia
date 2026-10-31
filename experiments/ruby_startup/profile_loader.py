#!/usr/bin/env python3
"""Intrusive loader-stage diagnosis, separate from whole-operation samples."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def run(args):
    args.source=args.source.resolve();args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=True)
    source=json.loads((args.source/'results.json').read_text());pack=args.source/'work/code.pack';gems=args.gems.resolve();project=args.source/'work/project'
    clock="Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond)"
    loader=(HERE/'packed_loader.rb').read_text()
    loader=loader.replace("      raw = File.open(path, 'rb') do |file|", "      clock0 = "+clock+"\n      raw = File.open(path, 'rb') do |file|")
    loader=loader.replace("      raise 'pack size/header'", "      $gaia_diagnostics[:read_ns] = "+clock+" - clock0\n      raise 'pack size/header'")
    loader=loader.replace("      raise 'pack checksum' unless hash_provider.hexdigest(raw) == pin", "      clock0 = "+clock+"\n      digest = hash_provider.hexdigest(raw)\n      $gaia_diagnostics[:hash_ns] = "+clock+" - clock0\n      raise 'pack checksum' unless digest == pin")
    loader=loader.replace("      index = Marshal.load(raw.byteslice(16, size))", "      clock0 = "+clock+"\n      index = Marshal.load(raw.byteslice(16, size))\n      $gaia_diagnostics[:index_decode_ns] = "+clock+" - clock0")
    diagloader=args.output/'packed_loader.rb';diagloader.write_text(loader)
    bootstrap=(HERE/'bootstrap.rb').read_text();bootstrap=bootstrap.replace("require 'json'", "$gaia_diagnostics = Hash.new(0)\ncommon0 = "+clock+"\nrequire 'json'\n$gaia_diagnostics[:common_ns] = "+clock+" - common0\nsetup0 = "+clock)
    after="""
$gaia_diagnostics[:loader_setup_ns] = Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond) - setup0
module GaiaISeqDiagnostic
  def load_iseq(path)
    clock0 = Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond)
    result = super
    $gaia_diagnostics[:iseq_ns] += Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond) - clock0
    $gaia_diagnostics[:iseq_calls] += 1
    $gaia_diagnostics[:iseq_hits] += 1 if result
    if defined?(GaiaRubyPack) && (row = GaiaRubyPack.instance_variable_get(:@entries)[path.to_s])
      $gaia_diagnostics[:packed_requested_bytes] += row[1]
    end
    result
  end
end
RubyVM::InstructionSequence.singleton_class.prepend(GaiaISeqDiagnostic)
if defined?(GaiaRubyPack)
  module GaiaResolveDiagnostic
    def resolve(feature)
      clock0 = Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond)
      result = super
      $gaia_diagnostics[:resolve_ns] += Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond) - clock0
      $gaia_diagnostics[:resolve_calls] += 1
      result
    end
  end
  GaiaRubyPack.singleton_class.prepend(GaiaResolveDiagnostic)
end
cli0 = Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond)
"""
    bootstrap=bootstrap.replace('at_exit do',after+'\nat_exit do\n  $gaia_diagnostics[:cli_ns] = '+clock+' - cli0')
    bootstrap=bootstrap.replace('{status: status, token:', '{diagnostics: $gaia_diagnostics, status: status, token:')
    boot=args.output/'bootstrap.rb';boot.write_text(bootstrap)
    values=[];expected=None;exe=gems/'gems/rubocop-1.92.2/exe/rubocop'
    for mode in ('bootsnap','packed'):
        marker=args.output/(mode+'.exit');env=dict(os.environ,GEM_HOME=str(gems),GEM_PATH=str(gems),RUBOCOP_SERVER='false',
          RUBOCOP_CACHE_ROOT=str(args.source/'work/lint-cache'),GAIA_RUBY_MODE=mode,GAIA_RUBY_PACK=str(pack),GAIA_RUBY_PACK_SHA256=source['producer']['sha256'],
          GAIA_BOOTSNAP_CACHE=str(args.source/'work/bootsnap-cache'),GAIA_REQUEST_TOKEN='diagnostic',GAIA_EXIT_MARKER=str(marker))
        env.pop('RUBYOPT',None);env.pop('RUBOCOP_OPTS',None)
        cmd=['ruby','-r',str(boot),str(exe),'--no-server','--cache','false','--format','json','--config','.rubocop.yml','example.rb']
        p=subprocess.run(cmd,cwd=project,env=env,capture_output=True,text=True)
        if p.returncode!=1 or p.stderr:raise RuntimeError(str((p.returncode,p.stderr)))
        result=json.loads(p.stdout);meta=json.loads(marker.read_text());features=[f for f in meta['features'] if '/rubocop-1.92.2/' in f]
        actual=(result,features)
        if expected is not None and actual!=expected:raise ValueError('diagnostic operation differs')
        expected=actual;values.append(dict(mode=mode,stages=meta['diagnostics'],pack=meta['pack'],offenses=result['summary']['offense_count']))
    data=dict(scope='Intrusive stage/call diagnostic on existing admitted inputs and warmed caches; not main latency samples.',
       source_run=source['run_id'],source_sha256={p.name:sha(p) for p in [HERE/'packed_loader.rb',HERE/'bootstrap.rb',Path(__file__)]},
       pack_bytes=pack.stat().st_size,wire_and_offenses_match=True,profiles=values)
    (args.output/'profile.json').write_text(json.dumps(data,indent=2)+'\n');print(json.dumps(data,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--gems',type=Path,default=HERE/'_work/gems');p.add_argument('--source',type=Path,default=HERE/'_work/main');p.add_argument('--output',type=Path,default=HERE/'_work/diagnostic');run(p.parse_args())
